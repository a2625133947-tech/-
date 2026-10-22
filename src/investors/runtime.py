"""DataService boundary and compatibility mapping for the three pilot agents."""

from __future__ import annotations

import logging
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from src.data.capabilities import Market
from src.data.domain import Instrument, Unit
from src.data.pipeline import DataService
from src.factors.contracts import FactorContext
from src.factors.engine import FactorEngine
from src.factors.loader import RawMetricLoader
from src.investors.engine import StrategyEvaluator
from src.investors.profiles import SHADOW_PROFILES, get_profile

logger = logging.getLogger(__name__)


def evaluate_ticker(profile_id: str, ticker: str, end_date: str, *,
                    service: DataService | None = None):
    """Run strict point-in-time loading; failed loading yields explicit missing factors."""
    profile = get_profile(profile_id)
    market = Market.CN_SH if ticker.startswith(("6", "9")) else Market.CN_SZ
    instrument = Instrument(ticker=ticker, market=market, currency=Unit.CNY)
    as_of = datetime.combine(date.fromisoformat(end_date), time.max,
                             tzinfo=ZoneInfo("Asia/Shanghai"))
    try:
        context = RawMetricLoader(service or DataService()).load(instrument, as_of)
    except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
        logger.debug("Pilot factor data load failed for %s", ticker, exc_info=True)
        context = FactorContext(ticker=ticker, as_of=as_of)
        load_error = f"数据装载失败：{type(exc).__name__}"
    else:
        load_error = None
    factors = FactorEngine().evaluate(context)
    result = StrategyEvaluator().evaluate(profile, factors)
    if load_error:
        result.limitations += (load_error,)
        result.reasoning += load_error + "。"
    return result


def to_analyst_result(result, *, reasoning: str | None = None) -> dict:
    """Additive fields preserve the existing signal schema for Risk and Portfolio."""
    return {
        "signal": result.signal,
        "confidence": result.confidence,
        "key_metrics": result.key_metrics,
        "strengths": list(result.strengths),
        "risks": list(result.risks),
        "reasoning": reasoning or result.reasoning,
        "confidence_semantics": result.confidence_semantics,
        "signal_reason": result.signal_reason,
        "signal_explanation": (result.signal_explanation.model_dump(mode="json")
                               if result.signal_explanation else None),
        "profile_version": result.profile_version,
        "strategy_score": float(result.strategy_score) if result.strategy_score is not None else None,
        "used_factors": [item.model_dump(mode="json") for item in result.used_factors],
        "factor_contributions": [item.model_dump(mode="json")
                                 for item in result.contributions],
        "data_coverage": {
            "core_coverage": float(result.core_coverage),
            "supporting_coverage": float(result.supporting_coverage),
            "overall_coverage": float(result.overall_coverage),
            "implemented_factor_coverage": float(result.implemented_factor_coverage),
            "strategy_evidence_coverage": float(result.strategy_evidence_coverage),
        },
        "known_missing_dimensions": list(result.known_missing_dimensions),
        "confidence_components": (result.confidence_components.model_dump(mode="json")
                                  if result.confidence_components else None),
        "limitations": list(result.limitations),
    }
