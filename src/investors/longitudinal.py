"""Longitudinal dataset schema and outcome separation for shadow research.

Strictly separates model evaluation records from subsequent market outcomes.
Historical evaluations must never be contaminated with future realization data.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from src.investors.contracts import ConfidenceComponents
from src.investors.shadow import FrozenDataSnapshot, MatchedShadowResult


class LongitudinalShadowRecord(BaseModel):
    """Immutable record of an investor strategy evaluation at a specific point in time."""

    snapshot_id: str
    ticker: str
    market_data_date: str | None
    as_of: datetime
    profile_id: str
    profile_version: str
    factor_versions: dict[str, str]

    strategy_score: Decimal | None
    signal: str
    confidence: float
    confidence_components: ConfidenceComponents | None = None

    implemented_factor_coverage: Decimal
    strategy_evidence_coverage: Decimal
    core_coverage: Decimal
    supporting_coverage: Decimal

    quality_status: str
    known_missing_dimensions: tuple[str, ...]
    limitations: tuple[str, ...]

    factor_contributions: list[dict[str, Any]] = Field(default_factory=list)
    signal_reason: str
    reason_code: str | None = None


class OutcomeRecord(BaseModel):
    """Ex-post market realization data linked by snapshot_id and ticker.

    Never embedded directly inside StrategyEvaluationResult to prevent forward-looking bias.
    """

    snapshot_id: str
    ticker: str
    as_of: datetime
    measured_at: datetime
    forward_window: str  # e.g. "1M", "3M", "6M", "12M"
    benchmark_ticker: str = "sh.000300"

    forward_return: Decimal | None = None
    benchmark_return: Decimal | None = None
    excess_return: Decimal | None = None
    realized_volatility: Decimal | None = None
    max_drawdown: Decimal | None = None
    provenance: str = "baostock_daily_unadjusted"


def build_longitudinal_record(
    snapshot: FrozenDataSnapshot,
    matched_result: MatchedShadowResult,
) -> LongitudinalShadowRecord:
    """Transform a matched shadow result and its snapshot into a longitudinal dataset record."""
    new_res = matched_result.new

    market_date = None
    if snapshot.price_history.observation and snapshot.price_history.observation.value:
        market_date = snapshot.price_history.observation.value[-1].trading_date.isoformat()

    is_degraded = (
        snapshot.price_history.observation
        and snapshot.price_history.observation.quality.value == "degraded"
    )

    contribs = [
        c.model_dump(mode="json") for c in new_res.contributions
    ]

    return LongitudinalShadowRecord(
        snapshot_id=snapshot.snapshot_id,
        ticker=snapshot.ticker,
        market_data_date=market_date,
        as_of=snapshot.as_of,
        profile_id=new_res.profile_id,
        profile_version=new_res.profile_version,
        factor_versions={f.factor_id: f.version for f in new_res.used_factors},
        strategy_score=new_res.strategy_score,
        signal=new_res.signal,
        confidence=new_res.confidence,
        confidence_components=new_res.confidence_components,
        implemented_factor_coverage=new_res.implemented_factor_coverage,
        strategy_evidence_coverage=new_res.strategy_evidence_coverage,
        core_coverage=new_res.core_coverage,
        supporting_coverage=new_res.supporting_coverage,
        quality_status="DEGRADED" if is_degraded else "VALIDATED",
        known_missing_dimensions=new_res.known_missing_dimensions,
        limitations=new_res.limitations,
        factor_contributions=contribs,
        signal_reason=new_res.signal_reason,
        reason_code=new_res.signal_explanation.reason_code if new_res.signal_explanation else None,
    )
