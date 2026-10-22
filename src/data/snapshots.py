"""Local point-in-time archive of observations actually captured by this project."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from pydantic import TypeAdapter

from src.data.capabilities import Capability
from src.data.domain import CompanyProfile, DataEnvelope, DataStatus, DividendEvent, NewsItem, PriceBar, ShareCapitalEvent
from src.data.providers import DataRequest


_TYPES = {
    Capability.NEWS: list[NewsItem],
    Capability.INSTRUMENT_METADATA: CompanyProfile,
    Capability.INDUSTRY: CompanyProfile,
    Capability.SHARE_CAPITAL: list[ShareCapitalEvent],
    Capability.PRICE_ADJUSTED: list[PriceBar],
    Capability.DIVIDEND: list[DividendEvent],
}


class SnapshotStore:
    """Append-only observations; never backdate a capture to an event date."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS data_snapshots (
                    id INTEGER PRIMARY KEY,
                    snapshot_date TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    capability TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    retrieved_at TEXT NOT NULL,
                    raw_hash TEXT NOT NULL,
                    normalized_result TEXT NOT NULL,
                    start_date TEXT,
                    end_date TEXT,
                    adjustment TEXT
                )
            """)
            existing = {row[1] for row in db.execute("PRAGMA table_info(data_snapshots)")}
            for column in ("start_date", "end_date", "adjustment"):
                if column not in existing:
                    db.execute(f"ALTER TABLE data_snapshots ADD COLUMN {column} TEXT")
            db.execute("CREATE INDEX IF NOT EXISTS data_snapshots_lookup ON data_snapshots(ticker, capability, retrieved_at)")
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS data_snapshots_unique ON data_snapshots(provider, capability, ticker, retrieved_at, raw_hash)")

    def _connect(self):
        return sqlite3.connect(self.path)

    def save(self, request: DataRequest, envelope: DataEnvelope) -> int:
        if (request.capability not in _TYPES or envelope.status is not DataStatus.PRESENT
                or envelope.observation is None or not envelope.raw_hash):
            raise ValueError("snapshot requires a supported present observation and source payload hash")
        retrieved = envelope.observation.retrieved_at.astimezone(timezone.utc)
        with self._connect() as db:
            cursor = db.execute("""
                INSERT OR IGNORE INTO data_snapshots
                (snapshot_date, provider, capability, ticker, retrieved_at, raw_hash,
                 normalized_result, start_date, end_date, adjustment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (retrieved.date().isoformat(), envelope.provider, request.capability.value,
                  request.instrument.ticker, retrieved.isoformat(), envelope.raw_hash,
                  envelope.model_dump_json(),
                  request.start_date.isoformat() if request.start_date else None,
                  request.end_date.isoformat() if request.end_date else None,
                  request.adjustment.value))
            return cursor.lastrowid

    def as_of(self, request: DataRequest) -> DataEnvelope | None:
        """Return the last capture known by as_of, with its original provenance."""
        if request.capability not in _TYPES:
            return None
        at = request.as_of.astimezone(timezone.utc)
        clause = "ticker = ? AND capability = ? AND retrieved_at <= ?"
        params = [request.instrument.ticker, request.capability.value, at.isoformat()]
        if request.capability in (Capability.PRICE_ADJUSTED, Capability.DIVIDEND, Capability.SHARE_CAPITAL):
            clause += " AND start_date IS ? AND end_date IS ? AND adjustment = ?"
            params.extend((request.start_date.isoformat() if request.start_date else None,
                           request.end_date.isoformat() if request.end_date else None,
                           request.adjustment.value))
        with self._connect() as db:
            rows = db.execute(f"""
                SELECT normalized_result FROM data_snapshots
                WHERE {clause} ORDER BY retrieved_at DESC, id DESC
            """, params).fetchall()
        if not rows:
            return None
        adapter = TypeAdapter(DataEnvelope[_TYPES[request.capability]])
        envelope = adapter.validate_json(rows[0][0])
        if request.capability is Capability.NEWS:
            # Recent feeds drop older items. The archive keeps every headline
            # already seen by this as_of, not only the latest feed page.
            seen = {}
            for row in rows:
                captured = adapter.validate_json(row[0])
                if captured.provider != envelope.provider:
                    continue
                for item in captured.observation.value:
                    day = item.published_at.date()
                    if item.published_at > at or (request.start_date and day < request.start_date) or (request.end_date and day > request.end_date):
                        continue
                    seen[(item.url, item.title, item.published_at)] = item
            if not seen:
                return DataEnvelope(status=DataStatus.EMPTY_SUCCESS, provider=envelope.provider)
            envelope.observation.value = sorted(seen.values(), key=lambda item: item.published_at, reverse=True)
            if len(rows) > 1:
                envelope.raw_hash = None  # A merged view has no single source payload.
                envelope.is_derived = True
        return envelope.as_of(request.as_of)

    def count(self) -> int:
        with self._connect() as db:
            return db.execute("SELECT COUNT(*) FROM data_snapshots").fetchone()[0]
