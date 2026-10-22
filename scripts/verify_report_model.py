"""Verify the configured real model on cached source chunks; never save credentials."""
import argparse
import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.backend.database.connection import SessionLocal
from src.llm.credentials import configured_credentials
from src.llm.models import get_default_model_choice
from src.research.grounding import report_summary, validate_claim
from src.research.store import ResearchStore


parser = argparse.ArgumentParser()
parser.add_argument("--config-root", default=str(Path(__file__).resolve().parents[1]))
args = parser.parse_args()
config = Path(args.config_root)
load_dotenv(config / ".env", override=False)
logging.getLogger().setLevel(logging.CRITICAL)
engine = create_engine(f"sqlite:///file:{config / 'app/backend/hedge_fund.db'}?mode=ro&uri=true")
with Session(engine) as db:
    name, provider = get_default_model_choice(db)
    credentials = configured_credentials(db)
state = {"metadata": {"model_name": name, "model_provider": provider.value, "request": SimpleNamespace(api_keys=credentials)}}
store = ResearchStore(SessionLocal)
context = store.latest_context("600519")
assert context and context.report_count
doc = store.get_document(context.reports[0]["canonical_report_id"])
metrics = {"llm_calls": 0, "input_characters": 0, "max_prompt_chars": 0}
summary = report_summary(doc, state, metrics)
assert metrics.get("llm_verified_extracts", 0) > 0, "real model did not produce any verified literal extracts"
refs = {c.citation_id: c for c in summary.citations}
assert all(validate_claim(c, refs, {doc.metadata.canonical_report_id: doc}) for c in summary.findings + summary.risks + summary.catalysts)
result = {"model": name, "provider": provider.value, "scope": "all 21 chunks of cached 15-page real report", "metrics": metrics, "summary": summary.model_dump(mode="json")}
out = Path("docs/baselines/research_intelligence_model_live.json")
out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps({"model": name, "provider": provider.value, "metrics": metrics, "verified_citations": len(summary.citations), "output": str(out.resolve())}, ensure_ascii=False))
