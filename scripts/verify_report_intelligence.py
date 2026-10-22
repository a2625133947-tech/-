"""Run real broker research chain and save inspectable evidence without secrets.

poetry run python scripts/verify_report_intelligence.py --ticker 600519 --start 2026-09-01 --end 2026-09-30
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.backend.database.connection import SessionLocal, engine
from app.backend.database.models import Base
from app.backend.services.report_intelligence_service import ReportIntelligenceService
from src.research.grounding import answer_question, validate_claim
from src.research.models import PeriodRange
from src.research.store import ResearchStore


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", default="600519")
    parser.add_argument("--start", default="2026-09-01")
    parser.add_argument("--end", default="2026-09-30")
    parser.add_argument("--output", default="docs/baselines/research_intelligence_live.json")
    args = parser.parse_args()
    Base.metadata.create_all(engine)
    store = ResearchStore(SessionLocal)
    service = ReportIntelligenceService(store=store)
    security = service.resolve(args.ticker)
    period = PeriodRange.resolve("custom", args.start, args.end)
    context = service.pipeline.run(security, period)
    refs = {c.citation_id: c for c in context.citations}
    docs = {r["canonical_report_id"]: store.get_document(r["canonical_report_id"]) for r in context.reports if r["status"] != "FAILED"}
    claims = context.consensus + context.disagreements + context.themes + context.risks + context.catalysts + context.changes
    assert all(validate_claim(c, refs, docs) for c in claims)
    hallucination = answer_question(context, "2027年目标价是多少？")
    assert hallucination["status"] == "INSUFFICIENT_EVIDENCE"
    cached = service.pipeline.run(security, period)
    # Exercise the original graph entry point with the actual persisted context,
    # rather than a fixture or a replacement analyst workflow.
    from src.main import start
    from src.research.context import research_for_agent

    state = start({"messages": [], "data": {"tickers": [args.ticker], "start_date": args.start,
                   "end_date": args.end, "analyst_signals": {}}, "metadata": {}})
    downstream = {}
    for role in ("fundamental", "risk", "portfolio", "technical"):
        payload = research_for_agent(state, args.ticker, role)
        size = len(json.dumps(payload, ensure_ascii=False))
        assert size <= 12000
        if role == "technical":
            assert payload == {}
        else:
            assert payload["report_count"] == context.report_count and payload["citations"]
            assert all(c["citation_id"] in refs for c in payload["citations"])
        downstream[role] = {"characters": size, "citation_count": len(payload.get("citations", [])),
                            "fields": list(payload)}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"context": context.model_dump(mode="json"), "repeat_metrics": cached.metrics, "verified_claim_count": len(claims), "hallucination_question": hallucination, "original_graph_entry_cached_context": downstream, "downstream_scope": "actual graph start and persisted role packages; no full live Portfolio investment run"}, ensure_ascii=False, indent=2))
    print(json.dumps({"output": str(output.resolve()), "ticker": context.ticker, "coverage": context.coverage.model_dump(), "reports": context.report_count, "citations": len(context.citations), "ratings": [v.value for v in context.ratings], "forecasts": len(context.earnings_forecasts), "metrics": context.metrics, "repeat_metrics": cached.metrics, "hallucination": hallucination}, ensure_ascii=False))
    service.executor.shutdown(wait=True)


if __name__ == "__main__":
    main()
