"""Freeze the unmodified legacy investor rules against the synthetic factor fixture."""

import json
from pathlib import Path
from types import SimpleNamespace

from src.agents.a_share_investors import (
    PROFILES, _build_key_metrics, _build_strengths_and_risks, _decision, _factors,
)


ROOT = Path(__file__).resolve().parents[1]
fixture = json.loads((ROOT / "tests/fixtures/factors/golden_v1.json").read_text())
mapping = {
    "return_on_equity": "roe", "net_margin": "net_margin",
    "debt_to_equity": "debt_to_equity", "price_to_earnings_ratio": "pe",
    "price_to_book_ratio": "pb",
}
snapshot = {"source": "synthetic golden_v1 fixture; not observed market data", "tickers": {}}
for ticker, context in fixture["contexts"].items():
    metric = {}
    for target, source in mapping.items():
        points = context["metrics"].get(source, {}).get("points", [])
        metric[target] = float(points[-1]["value"]) if points else None
    for target, source in (("revenue_growth", "revenue"), ("earnings_growth", "net_income")):
        points = context["metrics"].get(source, {}).get("points", [])
        metric[target] = (float(points[-1]["value"]) / float(points[-2]["value"]) - 1
                          if len(points) >= 2 and float(points[-2]["value"]) != 0 else None)
    metric["free_cash_flow_yield"] = None  # Fixture has no reliable dated market cap.
    bars = [SimpleNamespace(time=item["trading_date"], close=float(item["close"]))
            for item in context["prices"]["bars"]]
    scores, raw = _factors(SimpleNamespace(**metric), bars)
    snapshot["tickers"][ticker] = {}
    for profile_id in ("zhang_kun", "feng_liu", "fu_pengbo"):
        profile = PROFILES[profile_id]
        signal, confidence, coverage, _ = _decision(profile, scores)
        strengths, risks = _build_strengths_and_risks(profile, scores)
        snapshot["tickers"][ticker][profile_id] = {
            "factor_scores": scores, "raw_metrics": raw, "signal": signal,
            "confidence": confidence, "coverage": coverage,
            "key_metrics": _build_key_metrics(profile, raw),
            "strengths": strengths, "risks": risks,
        }

output = ROOT / "docs/baselines/b4_legacy_fixture.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")
print(output)
