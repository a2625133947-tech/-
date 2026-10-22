"""Durable research tasks with bounded workers; reuses existing DB/model config."""
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from threading import RLock
from uuid import uuid4

from app.backend.database.connection import SessionLocal
from src.data.security_master import SecurityMaster
from src.research.documents import digest
from src.research.models import PeriodRange
from src.research.pipeline import ResearchPipeline
from src.research.providers import BrokerFeedProvider, EastMoneyProvider
from src.research.store import ResearchStore

logger = logging.getLogger(__name__)


class ReportIntelligenceService:
    def __init__(self, store=None, providers=None, resolver=None):
        self.store = store or ResearchStore(SessionLocal)
        if providers is None:
            providers = [EastMoneyProvider()]
            feed = os.getenv("RESEARCH_FEED_URL")
            if feed:
                hosts = set(filter(None, (h.strip() for h in os.getenv("RESEARCH_DOCUMENT_HOSTS", "").split(","))))
                providers.append(BrokerFeedProvider(feed, hosts))
        self.pipeline = ResearchPipeline(self.store, providers)
        self.resolver = resolver or (lambda query: SecurityMaster.get_instance().resolve(query))
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="research-task")
        self.lock = RLock()
        self.active = {}

    def resolve(self, query):
        result = self.resolver(query)
        if not result.resolved or result.security is None:
            raise ValueError(result.message or "unresolved or ambiguous security")
        return result.security

    def start(self, query, period: PeriodRange, *, limit=100, refresh=False, regenerate=False, llm_state=None):
        security = self.resolve(query)
        model = "extractive" if llm_state is None else str(llm_state["metadata"].get("model_name")) + ":" + str(llm_state["metadata"].get("model_provider"))
        key = digest(f"{security.canonical_symbol}|{period.model_dump_json()}|{limit}|{refresh}|{regenerate}|{model}")
        with self.lock:
            if key in self.active:
                return self.store.task(self.active[key])
            if len(self.active) >= 8:
                raise RuntimeError("research queue is full; retry after a running task completes")
            task_id = str(uuid4())
            self.store.create_task(task_id, key, security.canonical_symbol)
            self.active[key] = task_id
            self.executor.submit(self._run, task_id, key, security, period, limit, refresh, regenerate, llm_state)
            return self.store.task(task_id)

    def _run(self, task_id, key, security, period, limit, refresh, regenerate, llm_state):
        try:
            context = self.pipeline.run(security, period, limit=limit, refresh=refresh, regenerate=regenerate, llm_state=llm_state, progress=lambda status, done, total: self.store.update_task(task_id, status, done, total))
            status = "PARTIAL" if context.errors or context.status == "PARTIAL" else "COMPLETED"
            self.store.update_task(task_id, status, context.report_count, context.coverage.unique_reports, result=context.model_dump(mode="json"), errors=context.errors)
        except Exception as exc:
            logger.error("research task=%s ticker=%s error_type=%s", task_id, security.canonical_symbol, type(exc).__name__)
            self.store.update_task(task_id, "FAILED", errors=[{"stage": "task", "error": type(exc).__name__}])
        finally:
            with self.lock:
                self.active.pop(key, None)


_service = None


def get_report_service():
    global _service
    if _service is None:
        _service = ReportIntelligenceService()
    return _service
