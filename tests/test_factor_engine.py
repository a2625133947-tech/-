import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.data.capabilities import Capability
from src.data.domain import Adjustment, DataStatus, PriceBar, Provenance, Quality, Unit
from src.factors.contracts import (FactorCategory, FactorContext, FactorResult, FactorStatus,
                                   FactorType, RawMetricPoint, RawMetricSeries)
from src.factors.engine import FactorEngine, FactorRegistry, default_registry


FIXTURE = json.loads((Path(__file__).parent / "fixtures/factors/golden_v1.json").read_text())


def context(ticker="600519"):
    return FactorContext.model_validate(FIXTURE["contexts"][ticker])


def point(metric, value, day=date(2025, 12, 31), *, available=None, quality=Quality.VALIDATED,
          period="annual"):
    available = available or datetime(2026, 3, 31, tzinfo=timezone.utc)
    return RawMetricPoint(metric_id=metric, value=Decimal(str(value)), observed_date=day,
        period=period, provenance=Provenance(provider="fixture", period=period,
            observed_date=day, available_at=available, retrieved_at=available + timedelta(days=1),
            unit=Unit.FRACTION if "margin" in metric or metric == "roe" else Unit.CNY,
            quality=quality))


def replace_metric(ctx, name, points, status=DataStatus.PRESENT):
    clone = ctx.model_copy(deep=True)
    clone.metrics[name] = RawMetricSeries(metric_id=name, points=tuple(points), source_status=status)
    return clone


@pytest.mark.parametrize("ticker", ["600519", "000001", "300750"])
def test_golden_all_registered_factors_are_deterministic_and_versioned(ticker):
    ctx = context(ticker)
    first = FactorEngine().evaluate(ctx)
    second = FactorEngine().evaluate(ctx)
    assert first == second and len(first) == 16
    for factor_id, result in first.items():
        assert result.factor_id == factor_id and result.version == "v1"
        assert result.as_of == ctx.as_of and Decimal(0) <= result.coverage <= Decimal(1)
        if result.normalized_score is not None:
            assert Decimal(-1) <= result.normalized_score <= Decimal(1)
            assert result.raw_value is not None
            assert result.provenance
    assert first["revenue_growth_yoy"].status is FactorStatus.AVAILABLE
    assert first["valuation_percentile"].status is FactorStatus.INSUFFICIENT_HISTORY
    assert first["momentum_1m"].status is FactorStatus.AVAILABLE
    assert first["momentum_6m"].status is FactorStatus.INSUFFICIENT_HISTORY


def test_registry_filter_duplicate_unknown_dependency_and_cycle():
    registry = default_registry()
    assert len(registry.list(FactorCategory.GROWTH)) == 4
    factor = registry.get("revenue_growth_yoy")
    with pytest.raises(ValueError, match="duplicate"):
        registry.register(factor)
    from dataclasses import replace
    registry = FactorRegistry()
    registry.register(replace(factor, factor_id="a", dependencies=("b",)))
    with pytest.raises(ValueError, match="unknown"):
        registry.validate_dependencies()
    with pytest.raises(ValueError, match="cycle"):
        registry.register(replace(factor, factor_id="b", dependencies=("a",)))


def test_missing_optional_partial_and_missing_required_no_fabricated_zero():
    ctx = replace_metric(context(), "roe", [])
    result = FactorEngine().evaluate(ctx, ("profitability_quality",))["profitability_quality"]
    assert result.status is FactorStatus.PARTIAL
    assert result.coverage == Decimal(2) / 3
    assert result.normalized_score is not None
    missing = replace_metric(ctx, "net_margin", [], DataStatus.MISSING)
    result = FactorEngine().evaluate(missing, ("profitability_quality",))["profitability_quality"]
    assert result.status is FactorStatus.UNAVAILABLE
    assert result.raw_value is None and result.normalized_score is None


def test_optional_metric_from_different_period_is_reported_as_partial():
    ctx = context()
    ctx = replace_metric(ctx, "roe", [point("roe", "0.2", date(2024, 12, 31))])
    result = FactorEngine().evaluate(ctx, ("profitability_quality",))["profitability_quality"]
    assert result.status is FactorStatus.PARTIAL
    assert result.coverage == Decimal(2) / 3
    assert any("roe" in limitation for limitation in result.limitations)


@pytest.mark.parametrize("factor_id", [factor.factor_id for factor in default_registry().list()])
def test_every_factor_refuses_missing_required_input(factor_id):
    factor = default_registry().get(factor_id)
    ctx = context()
    if factor.required_metrics:
        name = factor.required_metrics[0]
        ctx = replace_metric(ctx, name, [], DataStatus.MISSING)
    else:
        ctx.prices.bars = ()
        ctx.prices.provenance = None
        ctx.prices.status = DataStatus.MISSING
    result = factor.evaluate(ctx)
    assert result.status is FactorStatus.UNAVAILABLE
    assert result.raw_value is None and result.normalized_score is None


def test_continuous_profitability_score_has_no_threshold_jump():
    original = context()
    low = replace_metric(original, "roe", [point("roe", "0.1999")])
    high = replace_metric(original, "roe", [point("roe", "0.2001")])
    engine = FactorEngine()
    a = engine.evaluate(low, ("profitability_quality",))["profitability_quality"]
    b = engine.evaluate(high, ("profitability_quality",))["profitability_quality"]
    assert Decimal(0) < b.normalized_score - a.normalized_score < Decimal("0.01")


def test_quality_inherits_degraded_input_and_conflict():
    result = FactorEngine().evaluate(context("000001"), ("cash_conversion",))["cash_conversion"]
    assert result.status is FactorStatus.DEGRADED and result.quality is Quality.DEGRADED
    assert len(result.inputs) == 3 and len(result.provenance) == 3
    ctx = context()
    ctx.prices.conflict = True
    result = FactorEngine().evaluate(ctx, ("momentum_1m",))["momentum_1m"]
    assert result.status is FactorStatus.DEGRADED and result.quality is Quality.DEGRADED


def test_as_of_hides_future_report_and_adjusted_snapshot():
    ctx = context()
    ctx.as_of = datetime(2024, 1, 1, tzinfo=timezone.utc)
    growth = FactorEngine().evaluate(ctx, ("revenue_growth_yoy",))["revenue_growth_yoy"]
    assert growth.status is FactorStatus.INSUFFICIENT_HISTORY
    price = FactorEngine().evaluate(ctx, ("momentum_1m",))["momentum_1m"]
    assert price.status is FactorStatus.NOT_AVAILABLE_AS_OF
    ctx = replace_metric(context(), "net_margin", [point("net_margin", "0.4",
                     available=datetime(2027, 1, 1, tzinfo=timezone.utc))])
    result = FactorEngine().evaluate(ctx, ("profitability_quality",))["profitability_quality"]
    assert result.status is FactorStatus.NOT_AVAILABLE_AS_OF and result.normalized_score is None


@pytest.mark.parametrize("metric,factor", [("net_income", "earnings_growth_yoy"),
                                            ("revenue", "revenue_growth_yoy")])
def test_growth_rejects_zero_negative_near_zero_and_period_mismatch(metric, factor):
    ctx = context()
    for base in ["0", "-1", "0.0000001"]:
        points = [point(metric, base, date(2024, 12, 31)), point(metric, "10")]
        result = FactorEngine().evaluate(replace_metric(ctx, metric, points), (factor,))[factor]
        assert result.status is FactorStatus.INVALID_INPUT and result.normalized_score is None
    points = [point(metric, 5, date(2024, 9, 30)), point(metric, 10)]
    result = FactorEngine().evaluate(replace_metric(ctx, metric, points), (factor,))[factor]
    assert result.status is FactorStatus.INSUFFICIENT_HISTORY


def test_cash_conversion_zero_denominator_and_nonpositive_pe():
    ctx = replace_metric(context(), "net_income", [point("net_income", 0)])
    result = FactorEngine().evaluate(ctx, ("cash_conversion",))["cash_conversion"]
    assert result.status is FactorStatus.INVALID_INPUT
    ctx = replace_metric(context(), "pe", [point("pe", -3, date(2026, 9, 25), period="daily")])
    result = FactorEngine().evaluate(ctx, ("valuation_level",))["valuation_level"]
    assert result.status is FactorStatus.INVALID_INPUT and result.normalized_score is None


def test_valuation_percentile_history_negative_pe_and_extreme_values():
    ctx = context()
    start = date(2025, 8, 1)
    days = [start + timedelta(days=i) for i in range(420) if (start + timedelta(days=i)).weekday() < 5]
    points = [point("pe", 10 + index / 100, day,
                    available=datetime.combine(day + timedelta(days=1), datetime.min.time(), timezone.utc),
                    period="daily") for index, day in enumerate(days)]
    ctx = replace_metric(ctx, "pe", points)
    result = FactorEngine().evaluate(ctx, ("valuation_percentile",))["valuation_percentile"]
    assert result.status is FactorStatus.AVAILABLE and result.raw_value == 1
    assert result.normalized_score == -1
    ctx = replace_metric(ctx, "pe", points[:251] + [point("pe", -1, days[251], period="daily")])
    result = FactorEngine().evaluate(ctx, ("valuation_percentile",))["valuation_percentile"]
    assert result.status is FactorStatus.INVALID_INPUT
    with pytest.raises(ValidationError):
        point("pe", float("nan"))


def test_price_factors_require_adjustment_and_handle_ex_date_continuity():
    ctx = context()
    raw = ctx.model_copy(deep=True)
    raw.prices.bars = tuple(bar.model_copy(update={"adjustment": Adjustment.UNADJUSTED})
                            for bar in raw.prices.bars)
    result = FactorEngine().evaluate(raw, ("momentum_1m",))["momentum_1m"]
    assert result.status is FactorStatus.INVALID_INPUT
    # A dividend creates a 10% raw gap; backward-adjusted closes remove it.
    ctx.prices.bars = tuple(bar.model_copy(update={"close": Decimal(100)}) for bar in ctx.prices.bars[:-1]) + (
        ctx.prices.bars[-1].model_copy(update={"close": Decimal(100)}),)
    result = FactorEngine().evaluate(ctx, ("momentum_1m",))["momentum_1m"]
    assert result.status is FactorStatus.AVAILABLE and result.raw_value == 0


def test_price_long_windows_drawdown_and_volatility_formulas():
    ctx = context()
    bars = []
    start = date(2025, 8, 1)
    days = [start + timedelta(days=i) for i in range(420) if (start + timedelta(days=i)).weekday() < 5]
    for index, day in enumerate(days):
        close = Decimal("100") + Decimal(index) / 10
        if index == len(days) - 1:
            close *= Decimal("0.8")
        bars.append(ctx.prices.bars[0].model_copy(update={"trading_date": day,
                                                   "close": close, "open": close,
                                                   "high": close, "low": close}))
    ctx.prices.bars = tuple(bars)
    ctx.prices.provenance = ctx.prices.provenance.model_copy(update={
        "observed_date": days[-1], "available_at": datetime(2026, 9, 26, tzinfo=timezone.utc)})
    out = FactorEngine().evaluate(ctx, ("momentum_3m", "momentum_12m", "drawdown_6m", "volatility_3m"))
    assert all(result.status is FactorStatus.AVAILABLE for result in out.values())
    assert Decimal("-0.25") < out["drawdown_6m"].raw_value < Decimal("-0.15")
    assert out["volatility_3m"].raw_value > 0


def test_raw_metric_series_rejects_duplicate_reporting_dates():
    with pytest.raises(ValidationError, match="duplicate raw metric date"):
        RawMetricSeries(metric_id="revenue", points=(point("revenue", 100), point("revenue", 110)))


def test_proxy_result_requires_explicit_limitations():
    fields = dict(factor_id="example_proxy", version="v1", factor_type=FactorType.PROXY,
                  raw_value=Decimal("0.2"), normalized_score=Decimal("0.2"),
                  status=FactorStatus.AVAILABLE, coverage=Decimal(1), as_of=context().as_of,
                  window="latest")
    with pytest.raises(ValidationError, match="proxy factor must declare limitations"):
        FactorResult(**fields)
    assert FactorResult(**fields, limitations=("does not measure actual expectations",)).limitations


def test_three_year_cagr_is_decimal_and_requires_four_consecutive_years():
    ctx = context()
    values = (100, 110, 121, 133.1)
    points = [point("revenue", value, date(year, 12, 31))
              for year, value in zip(range(2022, 2026), values)]
    result = FactorEngine().evaluate(replace_metric(ctx, "revenue", points),
                                     ("revenue_cagr_3y",))["revenue_cagr_3y"]
    assert result.status is FactorStatus.AVAILABLE
    assert abs(result.raw_value - Decimal("0.1")) < Decimal("0.000000001")
    assert abs(result.normalized_score - Decimal("0.5")) < Decimal("0.000000001")
    missing_year = replace_metric(ctx, "revenue", points[:2] + points[3:])
    result = FactorEngine().evaluate(missing_year, ("revenue_cagr_3y",))["revenue_cagr_3y"]
    assert result.status is FactorStatus.INSUFFICIENT_HISTORY and result.normalized_score is None


def test_price_factors_reject_mixed_adjustment_and_duplicate_dates():
    ctx = context()
    mixed = ctx.model_copy(deep=True)
    mixed.prices.bars = (mixed.prices.bars[0].model_copy(update={"adjustment": Adjustment.FORWARD}),
                         *mixed.prices.bars[1:])
    result = FactorEngine().evaluate(mixed, ("momentum_1m",))["momentum_1m"]
    assert result.status is FactorStatus.INVALID_INPUT
    duplicate = ctx.model_copy(deep=True)
    duplicate.prices.bars = (duplicate.prices.bars[0], duplicate.prices.bars[0],
                             *duplicate.prices.bars[1:])
    result = FactorEngine().evaluate(duplicate, ("momentum_1m",))["momentum_1m"]
    assert result.status is FactorStatus.INVALID_INPUT


def test_volatility_reports_insufficient_history_for_long_trading_gap():
    ctx = context()
    template = ctx.prices.bars[0]
    days = [date(2026, 4, 1) + timedelta(days=i) for i in range(100)
            if (date(2026, 4, 1) + timedelta(days=i)).weekday() < 5]
    days = days[:32] + [day + timedelta(days=28) for day in days[32:64]]
    ctx.prices.bars = tuple(template.model_copy(update={"trading_date": day}) for day in days)
    result = FactorEngine().evaluate(ctx, ("volatility_3m",))["volatility_3m"]
    assert result.status is FactorStatus.INSUFFICIENT_HISTORY
    assert "gap" in result.reason


def test_loader_derives_raw_metrics_from_normalized_statements_with_provenance():
    from src.data.domain import (DataEnvelope, FinancialField, FinancialStatement,
                                 ObservedValue, StatementType, ValuationSnapshot)
    from src.factors.loader import RawMetricLoader

    ins = context().prices.bars[0].instrument
    retrieved = datetime(2026, 9, 26, tzinfo=timezone.utc)
    def statement(kind, year, fields):
        return FinancialStatement(instrument=ins, statement_type=kind,
            period_end=date(year, 12, 31), period="annual",
            available_at=datetime(year + 1, 3, 31, tzinfo=timezone.utc),
            fields=tuple(FinancialField(name=k, value=Decimal(str(v)), unit=Unit.CNY)
                         for k, v in fields.items()))
    sets = {
        Capability.INCOME_STATEMENT: [statement(StatementType.INCOME, 2024,
            {"revenue": 100, "net_income": 20, "operating_income": 30, "cost_of_revenue": 50}),
            statement(StatementType.INCOME, 2025,
            {"revenue": 120, "net_income": 30, "operating_income": 40, "cost_of_revenue": 60})],
        Capability.BALANCE_SHEET: [statement(StatementType.BALANCE_SHEET, 2024,
            {"shareholders_equity": 100}),
            statement(StatementType.BALANCE_SHEET, 2025,
            {"shareholders_equity": 120, "short_term_debt": 20,
             "current_assets": 200, "current_liabilities": 100, "cash_and_equivalents": 50})],
        Capability.CASH_FLOW_STATEMENT: [statement(StatementType.CASH_FLOW, 2025,
            {"operating_cash_flow": 36, "capital_expenditure": 6})],
    }
    class FakeService:
        requests = []
        def get_financial_statements(self, req):
            self.requests.append(req)
            data = sets[req.capability]
            return DataEnvelope(status=DataStatus.PRESENT, provider="sina",
                observation=ObservedValue(value=data, provider="sina",
                    observed_date=data[-1].period_end, available_at=data[-1].available_at,
                    retrieved_at=retrieved, unit=Unit.CNY, quality=Quality.VALIDATED))
        def fetch(self, req):
            self.requests.append(req)
            return DataEnvelope(status=DataStatus.NOT_AVAILABLE_FOR_DATE, provider="fixture")
    service = FakeService()
    as_of = datetime(2026, 9, 27, tzinfo=timezone.utc)
    loaded = RawMetricLoader(service).load(ins, as_of)
    assert all(item.as_of == as_of and not item.compatibility_mode for item in service.requests)
    assert Capability.NEWS not in {item.capability for item in service.requests}
    assert Capability.DIVIDEND not in {item.capability for item in service.requests}
    assert loaded.series("net_margin")[-1].value == Decimal("0.25")
    assert loaded.series("free_cash_flow")[-1].value == Decimal("30")
    assert loaded.series("debt_to_equity")[-1].value == Decimal(20) / 120
    assert loaded.series("roe")[-1].value == Decimal(30) / 110
    fcf = loaded.series("free_cash_flow")[-1]
    assert len(fcf.source_inputs) == 1 and fcf.source_inputs[0].provider == "sina"
    results = FactorEngine().evaluate(loaded, ("cash_conversion", "momentum_1m"))
    assert results["cash_conversion"].status is FactorStatus.AVAILABLE
    assert len(results["cash_conversion"].provenance) == 4
    assert results["momentum_1m"].status is FactorStatus.NOT_AVAILABLE_AS_OF
