"""Frozen-input Legacy/New comparisons; this module never fetches while running."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import re
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator, model_validator

from src.data.capabilities import Capability, Market
from src.data.domain import (
    Adjustment, CompanyProfile, DataEnvelope, DataStatus, DividendEvent,
    FinancialStatement, Instrument, PriceBar, ShareCapitalEvent, Unit,
    ValuationSnapshot,
)
from src.data.pipeline import DataService, capture_data_availability
from src.data.providers import DataRequest
from src.factors.contracts import FactorContext, PriceInput, RawMetricSeries
from src.factors.engine import FactorEngine
from src.factors.loader import RawMetricLoader
from src.investors.contracts import (
    InvestorProfile, StrategyEvaluationResult, UsedFactor,
)
from src.investors.engine import StrategyEvaluator

SHANGHAI = ZoneInfo("Asia/Shanghai")


def _validate_envelope(envelope, as_of, observed_for, available_for=None):
    if envelope.status is not DataStatus.PRESENT:
        return
    observation = envelope.observation
    if observation is None or observation.available_at > as_of:
        raise ValueError("snapshot observation is not available at snapshot as_of")
    rows = observation.value if isinstance(observation.value, list) else [observation.value]
    for row in rows:
        observed = observed_for(row) if observed_for else None
        available = available_for(row) if available_for else None
        if observed is not None and observed > as_of.date():
            raise ValueError("snapshot contains an observation dated after snapshot as_of")
        if available is not None and available > as_of:
            raise ValueError("snapshot contains data published after snapshot as_of")


class FrozenDataSnapshot(BaseModel):
    """All normalized inputs and status/provenance needed for a matched run."""

    schema_version: str = "b4.5-v1"
    ticker: str
    as_of: datetime
    adjustment_mode: Adjustment = Adjustment.BACKWARD
    financial_statements: dict[str, DataEnvelope[list[FinancialStatement]]]
    price_history: DataEnvelope[list[PriceBar]]
    valuation_history: DataEnvelope[list[ValuationSnapshot]]
    share_capital_history: DataEnvelope[list[ShareCapitalEvent]]
    industry: DataEnvelope[CompanyProfile]
    dividends: DataEnvelope[list[DividendEvent]]
    factor_context: FactorContext
    capability_statuses: dict[str, DataStatus] = Field(default_factory=dict)

    @field_validator("as_of")
    @classmethod
    def aware_as_of(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("snapshot as_of must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def aligned_snapshot(self):
        if self.factor_context.ticker != self.ticker or self.factor_context.as_of != self.as_of:
            raise ValueError("snapshot and factor context ticker/as_of must match")
        price_rows = (tuple(self.price_history.observation.value)
                      if self.price_history.observation else ())
        if self.factor_context.prices.bars != price_rows:
            raise ValueError("legacy and new prices must come from the same frozen bars")
        if self.factor_context.prices.status != self.price_history.status:
            raise ValueError("price envelope and factor context status must match")
        if self.factor_context.prices.bars and any(
                bar.adjustment != self.adjustment_mode for bar in self.factor_context.prices.bars):
            raise ValueError("price bars do not match snapshot adjustment mode")
        _validate_envelope(self.price_history, self.as_of,
                           lambda row: row.trading_date)
        _validate_envelope(self.valuation_history, self.as_of,
                           lambda row: row.observed_date, lambda row: row.available_at)
        _validate_envelope(self.share_capital_history, self.as_of,
                           lambda row: row.effective_date, lambda row: row.available_at)
        _validate_envelope(self.dividends, self.as_of,
                           lambda row: row.ex_date, lambda row: row.available_at)
        for envelope in self.financial_statements.values():
            _validate_envelope(envelope, self.as_of,
                               lambda row: row.period_end, lambda row: row.available_at)
            if envelope.observation and any(
                    row.instrument.ticker != self.ticker for row in envelope.observation.value):
                raise ValueError("financial statement ticker does not match frozen snapshot")
        for envelope in (self.price_history, self.valuation_history,
                         self.share_capital_history, self.dividends):
            if envelope.observation:
                rows = envelope.observation.value
                rows = rows if isinstance(rows, list) else [rows]
                if any(row.instrument.ticker != self.ticker for row in rows):
                    raise ValueError("observation ticker does not match frozen snapshot")
        if self.industry.status is DataStatus.PRESENT:
            if self.industry.observation.available_at > self.as_of:
                raise ValueError("industry observation is not visible at snapshot as_of")
            if self.industry.observation.value.instrument.ticker != self.ticker:
                raise ValueError("industry ticker does not match frozen snapshot")
        for series in self.factor_context.metrics.values():
            if any(not point.provenance.visible_as_of(self.as_of)
                   or point.observed_date > self.as_of.date() for point in series.points):
                raise ValueError("factor context contains a metric published after snapshot as_of")
        price_provenance = self.factor_context.prices.provenance
        if price_provenance and not price_provenance.visible_as_of(self.as_of):
            raise ValueError("adjusted prices were captured after snapshot as_of")
        if any(bar.trading_date > self.as_of.date() for bar in price_rows):
            raise ValueError("snapshot contains prices after snapshot as_of")
        return self

    @property
    def snapshot_id(self) -> str:
        return sha256(self.model_dump_json().encode("utf-8")).hexdigest()

    @classmethod
    def capture_current(cls, ticker: str, *, service: DataService | None = None) -> "FrozenDataSnapshot":
        """Capture current data once, then freeze and re-filter at completion time.

        The temporary end-of-day request timestamp lets same-run adjusted-price,
        industry and dividend observations be returned. They are all filtered
        against the actual completion timestamp before the snapshot is built.
        This captures a current snapshot; historical point-in-time replay requires
        an archived provider snapshot rather than today's live endpoints.
        """
        service = service or DataService()
        started = datetime.now(timezone.utc)
        day = started.astimezone(SHANGHAI).date()
        request_as_of = datetime.combine(day, time.max, SHANGHAI)
        instrument = Instrument(ticker=ticker,
            market=Market.CN_SH if ticker.startswith(("6", "9")) else Market.CN_SZ,
            currency=Unit.CNY)
        market_start = day - timedelta(days=430)
        financial_start = date(max(1990, day.year - 6), 1, 1)
        outcomes = {}
        with capture_data_availability() as outcomes:
            context = RawMetricLoader(service).load(instrument, request_as_of,
                financial_start=financial_start, market_start=market_start)
            for capability, start in ((Capability.SHARE_CAPITAL, date(1990, 1, 1)),
                                      (Capability.INDUSTRY, market_start),
                                      (Capability.DIVIDEND, market_start)):
                request = DataRequest(capability=capability, instrument=instrument,
                    as_of=request_as_of, start_date=start, end_date=day,
                    adjustment=Adjustment.BACKWARD, compatibility_mode=False)
                service.fetch(request)

        frozen_at = datetime.now(timezone.utc)
        context = _freeze_context(context, frozen_at)
        def get(capability):
            return outcomes.get((ticker, capability),
                DataEnvelope(status=DataStatus.UNSUPPORTED, provider="snapshot"))

        statements = {capability.value: _freeze_envelope(
            get(capability), frozen_at, lambda item: item.available_at,
            lambda item: item.period_end)
            for capability in (Capability.INCOME_STATEMENT, Capability.BALANCE_SHEET,
                               Capability.CASH_FLOW_STATEMENT)}
        price = _freeze_envelope(get(Capability.PRICE_ADJUSTED), frozen_at,
                                 lambda _item: None, lambda item: item.trading_date)
        valuation = _freeze_envelope(get(Capability.VALUATION_HISTORY), frozen_at,
                                     lambda item: item.available_at, lambda item: item.observed_date)
        shares = _freeze_envelope(get(Capability.SHARE_CAPITAL), frozen_at,
                                  lambda item: item.available_at, lambda item: item.effective_date)
        industry = _freeze_envelope(get(Capability.INDUSTRY), frozen_at,
                                    lambda _item: None, lambda _item: None)
        dividends = _freeze_envelope(get(Capability.DIVIDEND), frozen_at,
                                     lambda item: item.available_at, lambda item: item.ex_date)
        return cls(ticker=ticker, as_of=frozen_at, adjustment_mode=Adjustment.BACKWARD,
            financial_statements=statements, price_history=price,
            valuation_history=valuation, share_capital_history=shares,
            industry=industry, dividends=dividends, factor_context=context,
            capability_statuses={capability.value: get(capability).status
                                 for capability in Capability})


class LegacyEvaluation(BaseModel):
    factor_values: dict[str, float | None]
    factor_scores: dict[str, float | None]
    signal: str
    confidence: float
    coverage: float
    key_metrics: dict[str, dict]
    strengths: list[str]
    risks: list[str]


class ProxyEffect(BaseModel):
    factor_id: str
    status: str
    score: Decimal | None
    limitations: tuple[str, ...]


class ThresholdEffect(BaseModel):
    legacy_bullish_at: Decimal
    legacy_bearish_at: Decimal
    new_bullish_at: Decimal
    new_bearish_at: Decimal
    new_policy_style: str
    new_gate_id: str | None = None
    new_gate_passed: bool | None = None
    new_gate_inputs: dict[str, Decimal | None] = Field(default_factory=dict)
    new_reason_code: str | None = None
    new_signal_reason: str


class MatchedInputManifest(BaseModel):
    adjustment_mode: Adjustment
    price_rows: int
    price_start: date | None = None
    price_end: date | None = None
    financial_period_counts: dict[str, int]
    valuation_rows: int
    share_capital_events: int
    industry_present: bool
    dividend_events: int
    capability_statuses: dict[str, DataStatus]
    provider_ids: dict[str, str]


class DifferenceReport(BaseModel):
    ticker: str
    as_of: datetime
    investor: str
    profile_version: str
    matched_inputs: MatchedInputManifest
    legacy_factor_values: dict[str, float | None]
    legacy_factor_scores: dict[str, float | None]
    legacy_signal: str
    legacy_confidence: float
    new_used_factors: tuple[UsedFactor, ...]
    new_factor_versions: dict[str, str]
    new_factor_scores: dict[str, Decimal | None]
    new_strategy_score: Decimal | None
    new_signal: str
    new_confidence: float
    new_core_coverage: Decimal
    new_supporting_coverage: Decimal
    new_overall_coverage: Decimal
    new_known_missing_dimensions: tuple[str, ...] = Field(default=(), exclude=True)
    new_limitations: tuple[str, ...]
    factors_added: list[str]
    factors_removed: list[str]
    factor_formula_changes: dict[str, str]
    signal_changed: bool
    confidence_delta: float
    missing_data_effect: list[str]
    proxy_effect: ProxyEffect | None = None
    threshold_effect: ThresholdEffect

    @property
    def new_implemented_factor_coverage(self) -> Decimal:
        return self.new_overall_coverage

    @property
    def new_strategy_evidence_coverage(self) -> Decimal:
        dims = len(self.new_used_factors) + len(self.new_known_missing_dimensions)
        if dims > 0:
            return self.new_overall_coverage * Decimal(len(self.new_used_factors)) / Decimal(dims)
        return self.new_overall_coverage


class MatchedShadowResult(BaseModel):
    ticker: str
    as_of: datetime
    investor: str
    profile_version: str
    snapshot_id: str
    legacy: LegacyEvaluation
    new: StrategyEvaluationResult
    difference: DifferenceReport


_LEGACY_TO_NEW = {
    "profitability": "profitability_quality", "revenue_growth": "revenue_growth_yoy",
    "earnings_growth": "earnings_growth_yoy", "cash_flow": "cash_conversion",
    "balance_sheet": "balance_sheet_safety", "valuation": "valuation_level",
    "momentum": "momentum_6m",
}
_FORMULA_CHANGES = {
    "profitability_quality": "Legacy hard grades ROE and net margin; New continuous score also includes optional operating margin.",
    "revenue_growth_yoy": "Legacy hard-grades the latest same-period pair (annual when available); New requires consecutive positive-base annual reports and uses continuous normalization.",
    "earnings_growth_yoy": "Legacy hard-grades the latest same-period pair (annual when available); New requires consecutive positive-base annual reports and uses continuous normalization.",
    "cash_conversion": "Legacy FCF yield; New operating cash flow/net income with optional FCF conversion.",
    "balance_sheet_safety": "Legacy D/E hard grade; New continuous D/E plus available liquidity ratios.",
    "valuation_level": "Legacy PE/PB hard grades; New continuous PE/PB/PS scoring.",
    "momentum_6m": "Both use the same backward-adjusted 126 bars; Legacy applies a hard grade while New uses continuous normalization.",
}


class MatchedShadowRunner:
    """Pure matched evaluator: accepts one frozen snapshot and never a provider."""

    def __init__(self, factor_engine: FactorEngine | None = None,
                 strategy_evaluator: StrategyEvaluator | None = None):
        self.factor_engine = factor_engine or FactorEngine()
        self.strategy_evaluator = strategy_evaluator or StrategyEvaluator()

    def run(self, ticker: str, investor_profile: InvestorProfile, as_of: datetime,
            frozen_data: FrozenDataSnapshot) -> MatchedShadowResult:
        if ticker != frozen_data.ticker or as_of != frozen_data.as_of:
            raise ValueError("runner ticker/as_of must equal frozen snapshot")
        context = frozen_data.factor_context.model_copy(deep=True)
        new_factors = self.factor_engine.evaluate(context)
        new_result = self.strategy_evaluator.evaluate(investor_profile, new_factors)
        legacy_result = _evaluate_legacy(frozen_data, investor_profile, new_factors)
        difference = _compare(ticker, as_of, investor_profile, frozen_data,
                              legacy_result, new_result)
        return MatchedShadowResult(ticker=ticker, as_of=as_of,
            investor=investor_profile.display_name, profile_version=investor_profile.version,
            snapshot_id=frozen_data.snapshot_id, legacy=legacy_result,
            new=new_result, difference=difference)


def _freeze_context(context: FactorContext, as_of: datetime) -> FactorContext:
    metrics = {}
    for name, series in context.metrics.items():
        visible = tuple(point for point in series.points
                        if point.provenance.visible_as_of(as_of)
                        and point.observed_date <= as_of.astimezone(SHANGHAI).date())
        status = series.source_status
        if not visible and status is DataStatus.PRESENT:
            status = DataStatus.NOT_PUBLISHED
        metrics[name] = RawMetricSeries(metric_id=name, points=visible, source_status=status)
    bars = tuple(bar for bar in context.prices.bars
                 if bar.trading_date <= as_of.astimezone(SHANGHAI).date())
    price = context.prices.model_copy(update={"bars": bars})
    if price.provenance and not price.provenance.visible_as_of(as_of):
        price = PriceInput(bars=(), provenance=None, status=DataStatus.NOT_AVAILABLE_FOR_DATE,
                           conflict=price.conflict)
    return FactorContext(ticker=context.ticker, as_of=as_of, metrics=metrics, prices=price)


def _freeze_envelope(envelope, as_of, available_for, observed_for):
    if envelope.status is not DataStatus.PRESENT or envelope.observation is None:
        return envelope
    observation = envelope.observation.model_copy(deep=True)
    value = observation.value
    if isinstance(value, list):
        as_of_date = as_of.astimezone(SHANGHAI).date()
        visible = [item for item in value
                   if ((available_for(item) or observation.available_at) <= as_of)
                   and (observed_for(item) is None or observed_for(item) <= as_of_date)]
        if not visible:
            status = DataStatus.NOT_PUBLISHED if value else DataStatus.EMPTY_SUCCESS
            return DataEnvelope(status=status, provider=envelope.provider,
                                reason="no row visible at frozen as_of")
        observation.value = visible
        availabilities = [available_for(item) for item in visible if available_for(item) is not None]
        if availabilities:
            observation.available_at = max(availabilities)
        dates = [observed_for(item) for item in visible if observed_for(item) is not None]
        if dates:
            observation.observed_date = max(dates)
    elif available_for(value) is not None and available_for(value) > as_of:
        return DataEnvelope(status=DataStatus.NOT_PUBLISHED, provider=envelope.provider,
                            reason="observation was not available at frozen as_of")
    return envelope.model_copy(update={"observation": observation}, deep=True)


def _latest(context, metric_id):
    series = context.series(metric_id)
    return series[-1] if series else None


def _growth_value(context, metric_id):
    series = context.series(metric_id)
    annual = [point for point in series if point.period == "annual"]
    points = annual if len(annual) >= 2 else list(series)
    for current, previous in zip(reversed(points[1:]), reversed(points[:-1])):
        if current.observed_date.year - previous.observed_date.year == 1 and \
                (current.observed_date.month, current.observed_date.day) == \
                (previous.observed_date.month, previous.observed_date.day) and previous.value != 0:
            return float((current.value - previous.value) / abs(previous.value))
    return None


def _legacy_inputs(snapshot: FrozenDataSnapshot, factor_results):
    context = snapshot.factor_context
    latest = lambda key: _latest(context, key)
    valuation_items = (snapshot.valuation_history.observation.value
                       if snapshot.valuation_history.observation else [])
    valuation_items = [item for item in valuation_items
                       if item.available_at <= snapshot.as_of and item.observed_date <= snapshot.as_of.date()]
    valuation = max(valuation_items, key=lambda item: item.observed_date) if valuation_items else None
    share_events = (snapshot.share_capital_history.observation.value
                    if snapshot.share_capital_history.observation else [])
    share_events = [item for item in share_events
                    if item.available_at <= snapshot.as_of and item.effective_date <= snapshot.as_of.date()]
    shares = max(share_events, key=lambda item: item.effective_date) if share_events else None
    market_cap = (valuation.close * shares.total_shares
                  if valuation and valuation.close and shares else None)
    fcf = latest("free_cash_flow")
    fcf_yield = (float(fcf.value / market_cap)
                 if fcf and market_cap and market_cap > 0 else None)
    raw = {
        "return_on_equity": float(latest("roe").value) if latest("roe") else None,
        "net_margin": float(latest("net_margin").value) if latest("net_margin") else None,
        "revenue_growth": _growth_value(context, "revenue"),
        "earnings_growth": _growth_value(context, "net_income"),
        "free_cash_flow_yield": fcf_yield,
        "debt_to_equity": float(latest("debt_to_equity").value)
                            if latest("debt_to_equity") else None,
        "price_to_earnings_ratio": float(valuation.pe)
                                   if valuation and valuation.pe is not None else None,
        "price_to_book_ratio": float(valuation.pb)
                                if valuation and valuation.pb is not None else None,
    }
    metrics = SimpleNamespace(**raw)
    # Reuse the precise date window consumed by New momentum_6m. That factor
    # requires 126 backward-adjusted bars; Legacy uses the same source bars and
    # dates, while retaining its own hard-grade decision formula.
    momentum = factor_results.get("momentum_6m")
    visible_dates = {point.observed_date for point in momentum.inputs} if momentum else set()
    bars = [SimpleNamespace(time=item.trading_date.isoformat(), close=float(item.close))
            for item in context.prices.bars if item.trading_date in visible_dates]
    return raw, metrics, bars


def _evaluate_legacy(snapshot, profile, factor_results):
    # Import locally: matched validation is an explicit tool, not a production dependency.
    from src.agents.a_share_investors import (
        PROFILES as LEGACY_PROFILES, _build_key_metrics,
        _build_strengths_and_risks, _decision, _factors,
    )
    raw, metrics, bars = _legacy_inputs(snapshot, factor_results)
    scores, returned_raw = _factors(metrics, bars)
    legacy_profile = LEGACY_PROFILES[profile.profile_id]
    signal, confidence, coverage, _ = _decision(legacy_profile, scores)
    strengths, risks = _build_strengths_and_risks(legacy_profile, scores)
    return LegacyEvaluation(factor_values=returned_raw, factor_scores=scores,
        signal=signal, confidence=confidence, coverage=coverage,
        key_metrics=_build_key_metrics(legacy_profile, returned_raw),
        strengths=strengths, risks=risks)


def _compare(ticker, as_of, profile, snapshot, legacy, new):
    new_ids = {item.factor_id for item in new.used_factors}
    old_ids = set(legacy.factor_scores)
    overlap = {old: current for old, current in _LEGACY_TO_NEW.items()
               if old in old_ids and current in new_ids}
    additions = sorted(new_ids - set(overlap.values()))
    removals = sorted(old_ids - set(overlap))
    formulas = {old: _FORMULA_CHANGES[current] for old, current in overlap.items()
                if current in _FORMULA_CHANGES}
    missing = [f"{item.factor_id}: {item.status.value}"
               for item in new.used_factors if item.score is None]
    missing.extend(f"legacy {key}: no input" for key, score in legacy.factor_scores.items()
                   if score is None)
    proxy = next((item for item in new.used_factors if item.factor_type.value == "proxy"), None)
    proxy_effect = (ProxyEffect(factor_id=proxy.factor_id, status=proxy.status.value,
                     score=proxy.score, limitations=proxy.limitations)
                    if proxy else None)
    explanation = new.signal_explanation
    threshold_effect = ThresholdEffect(
        legacy_bullish_at=Decimal("0.30"),
        legacy_bearish_at=Decimal("-0.30"),
        new_bullish_at=profile.signal_policy.bullish_at,
        new_bearish_at=profile.signal_policy.bearish_at,
        new_policy_style=profile.signal_policy.style,
        new_gate_id=explanation.gate_id if explanation else None,
        new_gate_passed=explanation.gate_passed if explanation else None,
        new_gate_inputs=explanation.gate_inputs if explanation else {},
        new_reason_code=explanation.reason_code if explanation else None,
        new_signal_reason=new.signal_reason,
    )
    new_scores = {item.factor_id: item.score for item in new.used_factors}
    prices = (snapshot.price_history.observation.value
              if snapshot.price_history.observation else [])
    valuations = (snapshot.valuation_history.observation.value
                  if snapshot.valuation_history.observation else [])
    shares = (snapshot.share_capital_history.observation.value
              if snapshot.share_capital_history.observation else [])
    dividends = (snapshot.dividends.observation.value
                 if snapshot.dividends.observation else [])
    provider_ids = {}
    for key, envelope in (
            ("price_adjusted", snapshot.price_history),
            ("valuation_history", snapshot.valuation_history),
            ("share_capital", snapshot.share_capital_history),
            ("industry", snapshot.industry),
            ("dividend", snapshot.dividends),
            *snapshot.financial_statements.items()):
        if envelope.observation is not None:
            provider_ids[key] = envelope.provider
    matched_inputs = MatchedInputManifest(
        adjustment_mode=snapshot.adjustment_mode,
        price_rows=len(prices),
        price_start=prices[0].trading_date if prices else None,
        price_end=prices[-1].trading_date if prices else None,
        financial_period_counts={key: len(value.observation.value)
                                 if value.observation else 0
                                 for key, value in snapshot.financial_statements.items()},
        valuation_rows=len(valuations), share_capital_events=len(shares),
        industry_present=snapshot.industry.status is DataStatus.PRESENT,
        dividend_events=len(dividends),
        capability_statuses=snapshot.capability_statuses,
        provider_ids=provider_ids,
    )
    return DifferenceReport(
        ticker=ticker, as_of=as_of, investor=profile.display_name,
        profile_version=profile.version,
        matched_inputs=matched_inputs,
        legacy_factor_values=legacy.factor_values,
        legacy_factor_scores=legacy.factor_scores,
        legacy_signal=legacy.signal, legacy_confidence=legacy.confidence,
        new_used_factors=new.used_factors,
        new_factor_versions={item.factor_id: item.version for item in new.used_factors},
        new_factor_scores=new_scores,
        new_strategy_score=new.strategy_score,
        new_signal=new.signal, new_confidence=new.confidence,
        new_core_coverage=new.core_coverage,
        new_supporting_coverage=new.supporting_coverage,
        new_overall_coverage=new.overall_coverage,
        new_known_missing_dimensions=new.known_missing_dimensions,
        new_limitations=new.limitations,
        factors_added=additions, factors_removed=removals,
        factor_formula_changes=formulas, signal_changed=legacy.signal != new.signal,
        confidence_delta=round(new.confidence - legacy.confidence, 1),
        missing_data_effect=missing, proxy_effect=proxy_effect,
        threshold_effect=threshold_effect)


def save_shadow_result(result: MatchedShadowResult, directory: str | Path) -> Path:
    """Persist a credential-free matched result as one atomic JSON record."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = result.as_of.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_ticker = re.sub(r"[^A-Za-z0-9_.-]", "_", result.ticker)
    safe_profile = re.sub(r"[^A-Za-z0-9_.-]", "_", result.profile_version)
    filename = f"{safe_ticker}_{result.new.profile_id}_{safe_profile}_{stamp}_{result.snapshot_id[:12]}.json"
    path = directory / filename
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def save_frozen_snapshot(snapshot: FrozenDataSnapshot, directory: str | Path) -> Path:
    """Persist the full normalized input needed to replay a matched record."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = snapshot.as_of.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_ticker = re.sub(r"[^A-Za-z0-9_.-]", "_", snapshot.ticker)
    path = directory / f"{safe_ticker}_{stamp}_{snapshot.snapshot_id[:12]}.snapshot.json"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(snapshot.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def load_frozen_snapshot(path: str | Path) -> FrozenDataSnapshot:
    """Read a previously captured, versioned snapshot without provider access."""
    return FrozenDataSnapshot.model_validate_json(Path(path).read_text(encoding="utf-8"))
