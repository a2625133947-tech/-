"""Temporal and point-in-time shadow runner for retrospective and prospective validation.

Enforces strict point-in-time safety across historical statement announcements and as_of dates.
Never accesses live providers; operates purely on versioned snapshots and normalized contexts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any, Sequence

from pydantic import BaseModel, Field

from src.data.capabilities import Capability
from src.data.domain import (
    Adjustment, CompanyProfile, DataEnvelope, DataStatus, DividendEvent,
    FinancialStatement, PriceBar, ShareCapitalEvent, ValuationSnapshot,
)
from src.data.temporal import TemporalCapabilityPolicy, filter_context_for_retrospective
from src.factors.contracts import FactorContext, FactorResult, FactorStatus
from src.factors.engine import FactorEngine
from src.investors.contracts import (
    FactorContribution, InvestorProfile, SignalExplanation,
    StrategyEvaluationResult,
)
from src.investors.engine import StrategyEvaluator
from src.investors.shadow import (
    DifferenceReport, FrozenDataSnapshot, LegacyEvaluation,
    MatchedShadowResult, _compare, _evaluate_legacy, _freeze_envelope,
)


class TemporalValidationMode(StrEnum):
    RETROSPECTIVE_PIT_SAFE = "retrospective_pit_safe"
    """Retrospective evaluation without prospective archives; only PIT-safe capabilities
    (financial statements) are visible. Price-adjusted and valuation histories are UNAVAILABLE."""

    PROSPECTIVE_ARCHIVED = "prospective_archived"
    """Evaluation using an archived prospective snapshot captured at or before as_of;
    all capabilities captured at that time are replayed at full fidelity."""


class TemporalDataPolicy(BaseModel):
    mode: TemporalValidationMode = TemporalValidationMode.RETROSPECTIVE_PIT_SAFE
    allow_unadjusted_prices: bool = False
    strict_pit: bool = True


def build_pit_constrained_snapshot(
    source_snapshot: FrozenDataSnapshot,
    as_of: datetime,
    policy: TemporalDataPolicy | None = None,
) -> FrozenDataSnapshot:
    """Build a strictly point-in-time constrained snapshot for a requested historical as_of.

    Enforces that:
    1. No financial statement with available_at > as_of or period_end > as_of.date() is included.
    2. In RETROSPECTIVE_PIT_SAFE mode, non-PIT-safe capabilities (backward-adjusted prices,
       valuation multiples, industry, share capital, dividends) are marked NOT_AVAILABLE_FOR_DATE,
       preventing look-ahead bias from future corporate actions or current vendor states.
    3. FactorContext is filtered synchronously to match the constrained envelopes.
    """
    policy = policy or TemporalDataPolicy()
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    as_of = as_of.astimezone(timezone.utc)
    as_of_date = as_of.date()

    # Filter financial statements
    filtered_statements: dict[str, DataEnvelope[list[FinancialStatement]]] = {}
    for cap_name, env in source_snapshot.financial_statements.items():
        if env.status is not DataStatus.PRESENT or env.observation is None:
            filtered_statements[cap_name] = env
            continue
        visible = [
            stmt for stmt in env.observation.value
            if stmt.available_at <= as_of and stmt.period_end <= as_of_date
        ]
        if visible:
            obs = env.observation.model_copy(update={
                "value": visible,
                "available_at": max(s.available_at for s in visible),
                "observed_date": max(s.period_end for s in visible),
            })
            filtered_statements[cap_name] = env.model_copy(update={"observation": obs})
        else:
            filtered_statements[cap_name] = DataEnvelope(
                status=DataStatus.NOT_PUBLISHED,
                provider=env.provider,
                reason="no financial statement published as of requested date",
            )

    if policy.mode == TemporalValidationMode.RETROSPECTIVE_PIT_SAFE:
        # Non-PIT safe capabilities cannot be safely backfilled retrospectively
        price_history = DataEnvelope(
            status=DataStatus.NOT_AVAILABLE_FOR_DATE,
            provider="pit_policy",
            reason="backward-adjusted price history requires prospective snapshot archive",
        )
        valuation_history = DataEnvelope(
            status=DataStatus.NOT_AVAILABLE_FOR_DATE,
            provider="pit_policy",
            reason="valuation history requires prospective snapshot archive",
        )
        share_capital = DataEnvelope(
            status=DataStatus.NOT_AVAILABLE_FOR_DATE,
            provider="pit_policy",
            reason="share capital requires prospective snapshot archive",
        )
        industry = DataEnvelope(
            status=DataStatus.NOT_AVAILABLE_FOR_DATE,
            provider="pit_policy",
            reason="industry classification is current-only without historical revision archive",
        )
        dividends = DataEnvelope(
            status=DataStatus.NOT_AVAILABLE_FOR_DATE,
            provider="pit_policy",
            reason="dividend history requires prospective snapshot archive",
        )
        factor_context = filter_context_for_retrospective(
            source_snapshot.factor_context,
            as_of,
            allow_unadjusted_prices=policy.allow_unadjusted_prices,
        )
    else:
        # Prospective archived mode: source snapshot was genuinely captured at or before as_of
        price_history = _freeze_envelope(
            source_snapshot.price_history, as_of,
            lambda _item: None, lambda item: item.trading_date,
        )
        valuation_history = _freeze_envelope(
            source_snapshot.valuation_history, as_of,
            lambda item: item.available_at, lambda item: item.observed_date,
        )
        share_capital = _freeze_envelope(
            source_snapshot.share_capital_history, as_of,
            lambda item: item.available_at, lambda item: item.effective_date,
        )
        industry = _freeze_envelope(
            source_snapshot.industry, as_of,
            lambda _item: None, lambda _item: None,
        )
        dividends = _freeze_envelope(
            source_snapshot.dividends, as_of,
            lambda item: item.available_at, lambda item: item.ex_date,
        )
        from src.investors.shadow import _freeze_context
        factor_context = _freeze_context(source_snapshot.factor_context, as_of)

    statuses = {
        Capability.INCOME_STATEMENT.value: filtered_statements.get("income_statement", DataEnvelope(status=DataStatus.UNSUPPORTED, provider="pit_policy")).status,
        Capability.BALANCE_SHEET.value: filtered_statements.get("balance_sheet", DataEnvelope(status=DataStatus.UNSUPPORTED, provider="pit_policy")).status,
        Capability.CASH_FLOW_STATEMENT.value: filtered_statements.get("cash_flow_statement", DataEnvelope(status=DataStatus.UNSUPPORTED, provider="pit_policy")).status,
        Capability.PRICE_ADJUSTED.value: price_history.status,
        Capability.VALUATION_HISTORY.value: valuation_history.status,
        Capability.SHARE_CAPITAL.value: share_capital.status,
        Capability.INDUSTRY.value: industry.status,
        Capability.DIVIDEND.value: dividends.status,
    }

    return FrozenDataSnapshot(
        schema_version="b4.6-pit",
        ticker=source_snapshot.ticker,
        as_of=as_of,
        adjustment_mode=source_snapshot.adjustment_mode,
        financial_statements=filtered_statements,
        price_history=price_history,
        valuation_history=valuation_history,
        share_capital_history=share_capital,
        industry=industry,
        dividends=dividends,
        factor_context=factor_context,
        capability_statuses={k: statuses.get(k, DataStatus.UNSUPPORTED) for k in (c.value for c in Capability)},
    )


class TemporalShadowComparison(BaseModel):
    ticker: str
    as_of: datetime
    investor: str
    profile_version: str
    validation_mode: TemporalValidationMode
    legacy: LegacyEvaluation
    new: StrategyEvaluationResult
    difference: DifferenceReport
    latest_financial_period: str | None = None


class StrategyTracePoint(BaseModel):
    as_of: datetime
    latest_financial_period: str | None
    strategy_score: Decimal | None
    signal: str
    confidence: float
    core_coverage: Decimal
    supporting_coverage: Decimal
    overall_coverage: Decimal
    key_factor_contributions: dict[str, Decimal | None]
    gate_passed: bool | None
    reason_code: str | None
    limitations: tuple[str, ...]


class StrategyTrace(BaseModel):
    ticker: str
    investor: str
    profile_version: str
    points: list[StrategyTracePoint] = Field(default_factory=list)

    def signal_transitions(self) -> list[dict[str, Any]]:
        transitions = []
        for prev, curr in zip(self.points[:-1], self.points[1:]):
            if prev.signal != curr.signal:
                transitions.append({
                    "from_as_of": prev.as_of.isoformat(),
                    "to_as_of": curr.as_of.isoformat(),
                    "from_signal": prev.signal,
                    "to_signal": curr.signal,
                    "from_score": str(prev.strategy_score) if prev.strategy_score is not None else None,
                    "to_score": str(curr.strategy_score) if curr.strategy_score is not None else None,
                    "reason_code": curr.reason_code,
                })
        return transitions

    def confidence_transitions(self) -> list[dict[str, Any]]:
        transitions = []
        for prev, curr in zip(self.points[:-1], self.points[1:]):
            delta = round(curr.confidence - prev.confidence, 1)
            transitions.append({
                "from_as_of": prev.as_of.isoformat(),
                "to_as_of": curr.as_of.isoformat(),
                "from_confidence": prev.confidence,
                "to_confidence": curr.confidence,
                "delta": delta,
                "core_coverage_delta": str(curr.core_coverage - prev.core_coverage),
            })
        return transitions


class TemporalShadowRunner:
    """Evaluates strategy semantic stability across historical as_of dates."""

    def __init__(
        self,
        *,
        factor_engine: FactorEngine | None = None,
        strategy_evaluator: StrategyEvaluator | None = None,
    ):
        self.factor_engine = factor_engine or FactorEngine()
        self.strategy_evaluator = strategy_evaluator or StrategyEvaluator()

    def run(
        self,
        ticker: str,
        profile: InvestorProfile,
        as_of: datetime,
        source_data: FrozenDataSnapshot,
        policy: TemporalDataPolicy | None = None,
    ) -> TemporalShadowComparison:
        policy = policy or TemporalDataPolicy()
        if ticker != source_data.ticker:
            raise ValueError(f"ticker mismatch: {ticker} != {source_data.ticker}")

        # Build PIT constrained snapshot
        pit_snapshot = build_pit_constrained_snapshot(source_data, as_of, policy)

        # Run New evaluation
        new_factors = self.factor_engine.evaluate(pit_snapshot.factor_context)
        new_result = self.strategy_evaluator.evaluate(profile, new_factors)

        # Run Legacy evaluation
        legacy_result = _evaluate_legacy(pit_snapshot, profile, new_factors)

        # Build DifferenceReport
        difference = _compare(
            ticker, as_of, profile, pit_snapshot, legacy_result, new_result,
        )

        # Identify latest reported period end
        latest_period = None
        for env in pit_snapshot.financial_statements.values():
            if env.status is DataStatus.PRESENT and env.observation and env.observation.value:
                periods = [s.period_end for s in env.observation.value]
                if periods:
                    candidate = max(periods).isoformat()
                    if latest_period is None or candidate > latest_period:
                        latest_period = candidate

        return TemporalShadowComparison(
            ticker=ticker,
            as_of=as_of,
            investor=profile.display_name,
            profile_version=profile.version,
            validation_mode=policy.mode,
            legacy=legacy_result,
            new=new_result,
            difference=difference,
            latest_financial_period=latest_period,
        )


def build_strategy_trace(
    ticker: str,
    profile: InvestorProfile,
    as_of_sequence: Sequence[datetime],
    source_data: FrozenDataSnapshot,
    *,
    runner: TemporalShadowRunner | None = None,
    policy: TemporalDataPolicy | None = None,
) -> StrategyTrace:
    """Generate time series of strategy evaluations (StrategyTrace) for one investor and ticker."""
    runner = runner or TemporalShadowRunner()
    policy = policy or TemporalDataPolicy()
    points: list[StrategyTracePoint] = []

    for as_of in as_of_sequence:
        comp = runner.run(ticker, profile, as_of, source_data, policy=policy)
        new_res = comp.new

        key_contribs = {
            c.factor_id: c.weighted_contribution
            for c in new_res.contributions
            if c.weighted_contribution is not None
        }

        explanation = new_res.signal_explanation
        points.append(
            StrategyTracePoint(
                as_of=as_of,
                latest_financial_period=comp.latest_financial_period,
                strategy_score=new_res.strategy_score,
                signal=new_res.signal,
                confidence=new_res.confidence,
                core_coverage=new_res.core_coverage,
                supporting_coverage=new_res.supporting_coverage,
                overall_coverage=new_res.overall_coverage,
                key_factor_contributions=key_contribs,
                gate_passed=explanation.gate_passed if explanation else None,
                reason_code=explanation.reason_code if explanation else None,
                limitations=new_res.limitations,
            )
        )

    return StrategyTrace(
        ticker=ticker,
        investor=profile.display_name,
        profile_version=profile.version,
        points=points,
    )
