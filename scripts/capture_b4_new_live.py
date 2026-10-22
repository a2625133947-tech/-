"""Research-only current DataService probe for the three pilot profiles."""

import json
import warnings
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path

from src.data.capabilities import Market
from src.data.domain import Instrument, Unit
from src.data.pipeline import DataService
from src.factors.engine import FactorEngine
from src.factors.loader import RawMetricLoader
from src.investors import PILOT_PROFILES, StrategyEvaluator


ROOT = Path(__file__).resolve().parents[1]
captured = datetime.now(timezone.utc)
snapshot = {"captured_at": captured.isoformat(),
            "source": "live normalized DataService probe; final as_of set after retrieval and all inputs re-filtered",
            "tickers": {}}
for ticker in ("600519", "000001", "300750"):
    market = Market.CN_SH if ticker.startswith("6") else Market.CN_SZ
    instrument = Instrument(ticker=ticker, market=market, currency=Unit.CNY)
    try:
        with warnings.catch_warnings(), redirect_stdout(StringIO()):
            warnings.simplefilter("ignore")
            # Permit a same-run adjusted snapshot to be captured, then apply the
            # actual completion time as_of before any factor is evaluated.
            context = RawMetricLoader(DataService()).load(
                instrument, datetime.now(timezone.utc) + timedelta(minutes=2))
        context.as_of = datetime.now(timezone.utc)
        factors = FactorEngine().evaluate(context)
        snapshot["tickers"][ticker] = {"as_of": context.as_of.isoformat(), "profiles": {}}
        for profile_id, profile in PILOT_PROFILES.items():
            result = StrategyEvaluator().evaluate(profile, factors)
            snapshot["tickers"][ticker]["profiles"][profile_id] = {
                "profile_version": result.profile_version,
                "strategy_score": float(result.strategy_score) if result.strategy_score is not None else None,
                "signal": result.signal, "confidence": result.confidence,
                "core_coverage": float(result.core_coverage),
                "supporting_coverage": float(result.supporting_coverage),
                "overall_coverage": float(result.overall_coverage),
                "used_factors": [item.model_dump(mode="json") for item in result.used_factors],
                "key_metrics": result.key_metrics, "strengths": result.strengths,
                "risks": result.risks, "limitations": result.limitations,
            }
    except Exception as exc:
        snapshot["tickers"][ticker] = {"error": type(exc).__name__ + ": " + str(exc)[:120]}

output = ROOT / "docs/baselines/b4_new_live_probe.json"
output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")
print(output)
