"""Research persistence reuses the application's SQLAlchemy sessions."""
from datetime import datetime, timedelta, timezone
import logging

from sqlalchemy import select

from app.backend.database.models import ResearchCacheRecord, ResearchDocumentRecord, ResearchTaskRecord
from .models import ParsedDocument, ResearchContext

logger = logging.getLogger(__name__)


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ResearchStore:
    def __init__(self, session_factory):
        self.sessions = session_factory

    def cache_get(self, key):
        with self.sessions() as db:
            row = db.get(ResearchCacheRecord, key)
            if row and (row.expires_at is None or row.expires_at > utcnow()):
                return row.payload

    def cache_put(self, key, ticker, layer, payload, ttl=None):
        with self.sessions() as db:
            db.merge(ResearchCacheRecord(key=key, ticker=ticker, layer=layer, payload=payload, expires_at=utcnow() + timedelta(seconds=ttl) if ttl else None, created_at=utcnow()))
            db.commit()

    def get_document(self, report_id):
        alias = self.cache_get("alias:" + report_id)
        report_id = alias["canonical_report_id"] if alias else report_id
        with self.sessions() as db:
            row = db.get(ResearchDocumentRecord, report_id)
            if row and row.parsed_document:
                return ParsedDocument.model_validate(row.parsed_document)

    def raw_source(self, report_id):
        alias = self.cache_get("alias:" + report_id)
        report_id = alias["canonical_report_id"] if alias else report_id
        with self.sessions() as db:
            row = db.get(ResearchDocumentRecord, report_id)
            if row and row.raw_document:
                return row.raw_document, row.content_type

    def document_detail(self, report_id):
        with self.sessions() as db:
            row = db.get(ResearchDocumentRecord, report_id)
            if row:
                return {"metadata": row.metadata_json, "document": row.parsed_document, "error": row.error, "raw_bytes": len(row.raw_document or b"")}

    def save_document(self, metadata, raw, content_type, parsed=None, error=None):
        with self.sessions() as db:
            rid = metadata.canonical_report_id
            old = db.get(ResearchDocumentRecord, rid)
            if old:
                old.metadata_json = metadata.model_dump(mode="json")
                if parsed:
                    old.parsed_document = parsed.model_dump(mode="json")
                    if raw is not None:
                        old.raw_document, old.content_type = raw, content_type
                    old.error = None
                elif not old.parsed_document:
                    old.raw_document, old.content_type, old.error = raw, content_type, error
            else:
                db.add(ResearchDocumentRecord(report_id=rid, ticker=metadata.ticker, metadata_json=metadata.model_dump(mode="json"), raw_document=raw, content_type=content_type, parsed_document=parsed.model_dump(mode="json") if parsed else None, error=error))
            db.commit()

    def create_task(self, task_id, request_key, ticker):
        with self.sessions() as db:
            db.add(ResearchTaskRecord(task_id=task_id, request_key=request_key, ticker=ticker, status="PENDING", progress={"completed": 0, "total": 0}, errors=[]))
            db.commit()

    def task(self, task_id):
        with self.sessions() as db:
            row = db.get(ResearchTaskRecord, task_id)
            if row:
                return {"task_id": row.task_id, "ticker": row.ticker, "status": row.status, "progress": row.progress, "result": row.result, "errors": row.errors}

    def update_task(self, task_id, status, completed=0, total=0, result=None, errors=None):
        logger.info("research task=%s stage=%s completed=%s total=%s", task_id, status, completed, total)
        with self.sessions() as db:
            row = db.get(ResearchTaskRecord, task_id)
            if row:
                row.status, row.progress = status, {"completed": completed, "total": total}
                row.updated_at = utcnow()
                if result is not None:
                    row.result = result
                if errors is not None:
                    row.errors = errors
                db.commit()

    def recover_interrupted_tasks(self):
        with self.sessions() as db:
            rows = db.scalars(select(ResearchTaskRecord).where(ResearchTaskRecord.status.notin_(["COMPLETED", "PARTIAL", "FAILED"]))).all()
            for row in rows:
                row.status = "FAILED"
                row.errors = [{"stage": "restart", "error": "worker interrupted; refresh to retry using cached documents"}]
            db.commit()

    def latest_context(self, ticker, period=None, end_date=None, start_date=None):
        with self.sessions() as db:
            rows = db.scalars(select(ResearchCacheRecord).where(ResearchCacheRecord.ticker == ticker, ResearchCacheRecord.layer == "period_summary").order_by(ResearchCacheRecord.created_at.desc()).limit(100)).all()
            for row in rows:
                if row.expires_at and row.expires_at <= utcnow():
                    continue
                ctx = ResearchContext.model_validate(row.payload)
                if period and ctx.period != period:
                    continue
                if end_date and str(ctx.period.end) > end_date:
                    continue
                if start_date and str(ctx.period.end) < start_date:
                    continue
                if ctx.report_count:
                    return ctx
