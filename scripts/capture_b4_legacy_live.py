"""Capture current legacy rules for three real tickers without calling an LLM."""

import json
import warnings
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

from src.agents.a_share_investors import (
    PROFILES, _build_key_metrics, _build_strengths_and_risks, _decision, _factors,
)
from src.tools.api import get_financial_metrics, get_prices


END_DATE = "2026-09-25"
START_DATE = "2026-03-25"
ROOT = Path(__file__).resolve().parents[1]
snapshot = {"captured_at": datetime.now(timezone.utc).isoformat(),
            "source": "live legacy API data; end_date is a requested upper bound",
            "requested_start": START_DATE, "requested_end": END_DATE, "tickers": {}}
for ticker in ("600519", "000001", "300750"):
    with warnings.catch_warnings(), redirect_stdout(StringIO()):
        warnings.simplefilter("ignore")
        metrics = get_financial_metrics(ticker, END_DATE, period="ttm", limit=1)
        prices = get_prices(ticker, START_DATE, END_DATE)
    scores, raw = _factors(metrics[0], prices) if metrics else ({}, {})
    entry = {"last_price_date": str(prices[-1].time)[:10] if prices else None,
             "price_count": len(prices), "financial_metric_count": len(metrics),
             "profiles": {}}
    for profile_id in ("zhang_kun", "feng_liu", "fu_pengbo"):
        profile = PROFILES[profile_id]
        signal, confidence, coverage, _ = (_decision(profile, scores) if metrics else
                                            ("neutral", 0.0, 0.0, 0))
        strengths, risks = _build_strengths_and_risks(profile, scores)
        entry["profiles"][profile_id] = {
            "factor_scores": scores, "raw_metrics": raw, "signal": signal,
            "confidence": confidence, "coverage": coverage,
            "key_metrics": _build_key_metrics(profile, raw),
            "strengths": strengths, "risks": risks,
        }
    snapshot["tickers"][ticker] = entry

output = ROOT / "docs/baselines/b4_legacy_live_2026-09-25.json"
output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")
print(output)
