"""Offline throughput benchmark with synthetic long reports; never a live-source count."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.backend.database.models import Base
from src.research.pipeline import ResearchPipeline
from src.research.store import ResearchStore
from tests.test_report_intelligence import FixtureProvider, metadata, body, SECURITY, PERIOD
from src.research.providers import AcquiredDocument


class LongReports(FixtureProvider):
    def acquire(self, meta):
        self.downloads += 1
        text = body(meta) + (("这是来自研报正文的渠道库存与需求观点，需要持续跟踪公司的盈利变化。" * 4000).encode())
        return AcquiredDocument(text, "text/plain", meta.source_url)


rows = []
with tempfile.TemporaryDirectory() as directory:
    for count in (10, 50, 100):
        engine = create_engine(f"sqlite:///{directory}/{count}.db", connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        store = ResearchStore(sessionmaker(bind=engine))
        provider = LongReports([metadata(i) for i in range(count)])
        pipeline = ResearchPipeline(store, [provider])
        first = pipeline.run(SECURITY, PERIOD)
        repeated = pipeline.run(SECURITY, PERIOD)
        assert first.report_count == count and repeated.metrics["period_cache_hit"] and provider.downloads == count
        rows.append({"reports": count, "first": first.metrics, "repeat": repeated.metrics, "downstream_characters": len(json.dumps(__import__("src.research.context", fromlist=["select_research_context"]).select_research_context(first, "portfolio"), ensure_ascii=False))})
        engine.dispose()
output = Path("docs/baselines/research_intelligence_benchmark.json")
output.write_text(json.dumps({"mode": "offline synthetic 128k-character reports, verified extractive mode, no network or LLM", "results": rows}, ensure_ascii=False, indent=2))
print(output.read_text())
