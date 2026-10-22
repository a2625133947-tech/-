"""Reproducible synthetic Legacy vs pilot Profile shadow comparison."""

import json
from pathlib import Path

from src.factors.contracts import FactorContext
from src.factors.engine import FactorEngine
from src.investors import PILOT_PROFILES, StrategyEvaluator


ROOT = Path(__file__).resolve().parents[1]
fixture = json.loads((ROOT / "tests/fixtures/factors/golden_v1.json").read_text())
legacy = json.loads((ROOT / "docs/baselines/b4_legacy_fixture.json").read_text())
comparison = {"source": "synthetic golden_v1 fixture; not observed market data", "tickers": {}}
for ticker, context in fixture["contexts"].items():
    available = FactorEngine().evaluate(FactorContext.model_validate(context))
    comparison["tickers"][ticker] = {}
    for profile_id, profile in PILOT_PROFILES.items():
        old = legacy["tickers"][ticker][profile_id]
        new = StrategyEvaluator().evaluate(profile, available)
        comparison["tickers"][ticker][profile_id] = {
            "legacy": {"factor_scores": old["factor_scores"], "signal": old["signal"],
                       "confidence": old["confidence"], "key_metrics": old["key_metrics"],
                       "strengths": old["strengths"], "risks": old["risks"]},
            "new": new.model_dump(mode="json"),
            "difference": {
                "new_factor_set": list(profile.factor_ids),
                "removed_legacy_factors": list(old["factor_scores"]),
                "signal_changed": old["signal"] != new.signal,
                "confidence_delta_points": round(new.confidence - old["confidence"], 1),
                "why": ("New uses normalized statement history, price-adjusted factors, profile-specific "
                        "roles and missing-data policy; Legacy uses one-period metrics and hard grades."),
            },
        }

output = ROOT / "docs/baselines/b4_shadow_fixture.json"
output.write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + "\n")
print(output)
