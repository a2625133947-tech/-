"""Versioned, continuous factors over visible raw metrics and adjusted prices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from math import sqrt
from statistics import stdev
from typing import Callable

from src.data.capabilities import Capability
from src.data.domain import Adjustment, DataStatus, Provenance, Quality, Unit
from src.factors.contracts import (
    FactorCategory, FactorContext, FactorResult, FactorStatus, FactorType,
    RawMetricPoint, aggregate_quality, clamp_score,
)

D = Decimal


class FactorInputError(Exception):
    def __init__(self, status: FactorStatus, reason: str):
        super().__init__(reason)
        self.status = status


def _latest(context: FactorContext, metric: str) -> RawMetricPoint:
    return context.series(metric)[-1]


def _at(context: FactorContext, metric: str, day: date) -> RawMetricPoint | None:
    return next((point for point in reversed(context.series(metric)) if point.observed_date == day), None)


def _annual(context: FactorContext, metric: str, count: int) -> tuple[RawMetricPoint, ...]:
    points = tuple(point for point in context.series(metric) if point.period == "annual")
    if len(points) < count:
        raise FactorInputError(FactorStatus.INSUFFICIENT_HISTORY, "insufficient annual history")
    selected = points[-count:]
    if any(right.observed_date.year - left.observed_date.year != 1 or
           (right.observed_date.month, right.observed_date.day) != (left.observed_date.month, left.observed_date.day)
           for left, right in zip(selected, selected[1:])):
        raise FactorInputError(FactorStatus.INSUFFICIENT_HISTORY, "non-consecutive comparable annual periods")
    return selected


def _positive_growth(previous: Decimal, current: Decimal) -> Decimal:
    if previous <= D("0.000001"):
        raise ValueError("growth base is nonpositive or too close to zero")
    return current / previous - 1


def profitability(context):
    base = _latest(context, "net_margin")
    inputs = [base]
    for name in ("roe", "operating_margin"):
        item = _at(context, name, base.observed_date)
        if item and item.period == base.period:
            inputs.append(item)
    values = {item.metric_id: item.value for item in inputs}
    raw = sum(values.values()) / len(values)
    components = [clamp_score(values["net_margin"] / D("0.25") - 1)]
    if "roe" in values:
        components.append(clamp_score(values["roe"] / D("0.15") - 1))
    if "operating_margin" in values:
        components.append(clamp_score(values["operating_margin"] / D("0.25") - 1))
    return raw, sum(components) / len(components), tuple(inputs)


def cash_conversion(context):
    net = _latest(context, "net_income")
    ocf = _at(context, "operating_cash_flow", net.observed_date)
    if ocf is None or ocf.period != net.period:
        raise FactorInputError(FactorStatus.UNAVAILABLE, "cash flow and earnings periods do not align")
    if net.value <= 0:
        raise ValueError("net income must be positive for cash conversion")
    inputs = [ocf, net]
    ratio = ocf.value / net.value
    scores = [clamp_score(ratio - 1)]
    fcf = _at(context, "free_cash_flow", net.observed_date)
    if fcf and fcf.period == net.period:
        inputs.append(fcf)
        scores.append(clamp_score(fcf.value / net.value - D("0.75")))
    return ratio, sum(scores) / len(scores), tuple(inputs)


def balance_safety(context):
    debt = _latest(context, "debt_to_equity")
    if debt.value < 0:
        raise ValueError("negative debt/equity is not a safety score")
    inputs = [debt]
    scores = [clamp_score(1 - 2 * debt.value)]
    for name, center, scale in (("current_ratio", D("1.5"), D("1.5")),
                                ("cash_ratio", D("0.5"), D("0.5"))):
        point = _at(context, name, debt.observed_date)
        if point:
            inputs.append(point)
            scores.append(clamp_score((point.value - center) / scale))
    return debt.value, sum(scores) / len(scores), tuple(inputs)


def growth(metric: str, count: int):
    def calculate(context):
        points = _annual(context, metric, count)
        if count == 4:
            if points[0].value <= D("0.000001") or points[-1].value < 0:
                raise ValueError("CAGR requires a positive base and nonnegative current value")
            raw = (points[-1].value / points[0].value) ** (D(1) / D(3)) - 1
        else:
            raw = _positive_growth(points[-2].value, points[-1].value)
        return raw, clamp_score(raw / D("0.2")), points
    return calculate


def growth_acceleration(context):
    points = _annual(context, "revenue", 3)
    previous = _positive_growth(points[0].value, points[1].value)
    current = _positive_growth(points[1].value, points[2].value)
    raw = current - previous
    return raw, clamp_score(raw / D("0.1")), points


def margin_trend(context):
    points = _annual(context, "net_margin", 3)
    raw = (points[-1].value - points[0].value) / 2  # fraction points per year
    return raw, clamp_score(raw / D("0.05")), points


def valuation_level(context):
    pe = _latest(context, "pe")
    if pe.value <= 0:
        raise ValueError("nonpositive PE cannot mean cheap")
    points = [pe]
    scores = [clamp_score((D("25") - pe.value) / D("15"))]
    for name, center, scale in (("pb", D("4"), D("3")), ("ps", D("7"), D("5"))):
        item = _at(context, name, pe.observed_date)
        if item and item.value > 0:
            points.append(item)
            scores.append(clamp_score((center - item.value) / scale))
    return pe.value, sum(scores) / len(scores), tuple(points)


def valuation_percentile(context):
    series = context.series("pe")
    if not series or series[-1].value <= 0:
        raise ValueError("latest PE must be positive")
    points = tuple(item for item in series if item.value > 0)
    if len(points) < 252 or (points[-1].observed_date - points[0].observed_date).days < 365:
        raise FactorInputError(FactorStatus.INSUFFICIENT_HISTORY,
                               "need 252 positive trading observations spanning at least 365 days")
    current = points[-1].value
    rank = D(sum(item.value <= current for item in points[:-1])) / D(len(points) - 1)
    return rank, 1 - 2 * rank, points


def _price_points(context: FactorContext, count: int, min_days: int):
    data = context.prices
    if data.status is not DataStatus.PRESENT or data.provenance is None:
        if data.status in (DataStatus.NOT_AVAILABLE_FOR_DATE, DataStatus.NOT_PUBLISHED):
            raise FactorInputError(FactorStatus.NOT_AVAILABLE_AS_OF,
                                   "price history not available as_of requested time")
        raise FactorInputError(FactorStatus.UNAVAILABLE, "adjusted prices unavailable")
    if not data.provenance.visible_as_of(context.as_of):
        raise FactorInputError(FactorStatus.NOT_AVAILABLE_AS_OF, "price snapshot captured after as_of")
    bars = tuple(bar for bar in data.bars if bar.trading_date <= context.as_of.date())
    dates = [bar.trading_date for bar in bars]
    if dates != sorted(set(dates)):
        raise ValueError("adjusted price dates must be strictly increasing")
    modes = {bar.adjustment for bar in bars}
    if Adjustment.UNADJUSTED in modes or len(modes) != 1:
        raise ValueError("price factor requires one consistent adjusted OHLC mode")
    if len(bars) < count or (bars[-1].trading_date - bars[-count].trading_date).days < min_days:
        raise FactorInputError(FactorStatus.INSUFFICIENT_HISTORY, "insufficient adjusted price history")
    selected = bars[-count:]
    points = tuple(RawMetricPoint(metric_id="adjusted_close", value=bar.close,
                   observed_date=bar.trading_date, period="daily",
                   provenance=data.provenance.model_copy(update={"observed_date": bar.trading_date}))
                   for bar in selected)
    return points


def momentum(count: int, min_days: int, scale: str):
    def calculate(context):
        points = _price_points(context, count, min_days)
        raw = points[-1].value / points[0].value - 1
        return raw, clamp_score(raw / D(scale)), points
    return calculate


def drawdown(context):
    points = _price_points(context, 126, 175)
    raw = points[-1].value / max(point.value for point in points) - 1
    return raw, clamp_score(1 + raw / D("0.125")), points


def volatility(context):
    points = _price_points(context, 64, 84)
    if any((right.observed_date - left.observed_date).days > 14 for left, right in zip(points, points[1:])):
        raise FactorInputError(FactorStatus.INSUFFICIENT_HISTORY,
                               "price gap exceeds 14 calendar days")
    returns = [float(right.value / left.value - 1) for left, right in zip(points, points[1:])]
    raw = D(str(stdev(returns) * sqrt(252)))
    return raw, clamp_score((D("0.4") - raw) / D("0.3")), points


@dataclass(frozen=True)
class BaseFactor:
    factor_id: str
    display_name: str
    category: FactorCategory
    required_capabilities: frozenset[Capability]
    optional_capabilities: frozenset[Capability]
    required_metrics: tuple[str, ...]
    optional_metrics: tuple[str, ...]
    required_history: int
    time_horizon: str
    raw_unit: Unit
    formula: Callable
    version: str = "v1"
    factor_type: FactorType = FactorType.DIRECT
    dependencies: tuple[str, ...] = ()

    def evaluate(self, context: FactorContext) -> FactorResult:
        """Public evaluation entry point; calculation stays deterministic."""
        return self.calculate(context)

    def calculate(self, context: FactorContext) -> FactorResult:
        names = self.required_metrics + self.optional_metrics
        present = sum(bool(context.series(name)) for name in names)
        coverage = (D(present) / D(len(names)) if names else
                    min(D(1), D(len(context.prices.bars)) / D(self.required_history)))
        if self.required_history > 1 and self.required_metrics:
            def count(name):
                points = context.series(name)
                if self.category is FactorCategory.GROWTH or self.factor_id == "margin_trend":
                    return sum(point.period == "annual" for point in points)
                if self.factor_id == "valuation_percentile":
                    return sum(point.value > 0 for point in points)
                return len(points)
            coverage *= min(D(1), min(D(count(name)) / D(self.required_history)
                                      for name in self.required_metrics))
        base = dict(factor_id=self.factor_id, version=self.version, factor_type=self.factor_type,
                    as_of=context.as_of, window=self.time_horizon, coverage=coverage,
                    raw_unit=self.raw_unit)
        for name in self.required_metrics:
            series = context.metrics.get(name)
            visible = context.series(name)
            if not visible:
                status = (FactorStatus.NOT_AVAILABLE_AS_OF if series and
                          (series.source_status in (DataStatus.NOT_AVAILABLE_FOR_DATE, DataStatus.NOT_PUBLISHED)
                           or series.points) else FactorStatus.UNAVAILABLE)
                return FactorResult(**base, status=status, reason=f"required metric {name} unavailable")
            if len(visible) < self.required_history and self.required_history > 1:
                return FactorResult(**base, status=FactorStatus.INSUFFICIENT_HISTORY,
                                    reason=f"{name}: need {self.required_history} observations")
        try:
            raw, score, inputs = self.formula(context)
        except FactorInputError as exc:
            return FactorResult(**base, status=exc.status, reason=str(exc))
        except (ValueError, ZeroDivisionError, OverflowError) as exc:
            return FactorResult(**base, status=FactorStatus.INVALID_INPUT, reason=str(exc))
        if not raw.is_finite() or not score.is_finite():
            return FactorResult(**base, status=FactorStatus.INVALID_INPUT, reason="nonfinite calculation")
        if names:
            coverage = D(len({item.metric_id for item in inputs} & set(names))) / D(len(names))
        quality = aggregate_quality(inputs, conflict=context.prices.conflict if self.category is FactorCategory.PRICE_BEHAVIOR else False)
        status = (FactorStatus.DEGRADED if quality is Quality.DEGRADED else
                  FactorStatus.PARTIAL if coverage < 1 else FactorStatus.AVAILABLE)
        consumed = {item.metric_id for item in inputs}
        limitations = tuple(f"optional input {name} unavailable for the selected period"
                            for name in self.optional_metrics if name not in consumed)
        if self.category is FactorCategory.PRICE_BEHAVIOR:
            coverage = D("1")
            status = FactorStatus.DEGRADED if quality is Quality.DEGRADED else FactorStatus.AVAILABLE
            limitations = ()
        return FactorResult(**{**base, "coverage": coverage}, status=status, raw_value=raw,
                            normalized_score=clamp_score(score), quality=quality, inputs=inputs,
                            provenance=tuple(source for item in inputs
                                             for source in (item.provenance, *item.source_inputs)),
                            limitations=limitations)


def builtins() -> tuple[BaseFactor, ...]:
    income = frozenset({Capability.INCOME_STATEMENT})
    cash = frozenset({Capability.CASH_FLOW_STATEMENT})
    balance = frozenset({Capability.BALANCE_SHEET})
    valuation = frozenset({Capability.VALUATION_HISTORY})
    adjusted = frozenset({Capability.PRICE_ADJUSTED})
    def f(id, name, cat, required_caps, optional_caps, required, optional, history, horizon, unit, formula):
        return BaseFactor(id, name, cat, required_caps, optional_caps, required, optional,
                          history, horizon, unit, formula)
    factors = [
        f("profitability_quality", "Profitability Quality", FactorCategory.QUALITY, income, balance,
          ("net_margin",), ("roe", "operating_margin"), 1, "latest comparable period", Unit.FRACTION, profitability),
        f("cash_conversion", "Cash Conversion", FactorCategory.CASH_FLOW, income | cash, frozenset(),
          ("net_income", "operating_cash_flow"), ("free_cash_flow",), 1, "latest comparable period", Unit.MULTIPLE, cash_conversion),
        f("balance_sheet_safety", "Balance Sheet Safety", FactorCategory.QUALITY, balance, frozenset(),
          ("debt_to_equity",), ("current_ratio", "cash_ratio"), 1, "latest balance sheet", Unit.MULTIPLE, balance_safety),
        f("revenue_growth_yoy", "Revenue Growth YoY", FactorCategory.GROWTH, income, frozenset(),
          ("revenue",), (), 2, "2 annual periods", Unit.FRACTION, growth("revenue", 2)),
        f("revenue_cagr_3y", "Revenue CAGR 3Y", FactorCategory.GROWTH, income, frozenset(),
          ("revenue",), (), 4, "4 annual periods", Unit.FRACTION, growth("revenue", 4)),
        f("earnings_growth_yoy", "Earnings Growth YoY", FactorCategory.GROWTH, income, frozenset(),
          ("net_income",), (), 2, "2 annual periods", Unit.FRACTION, growth("net_income", 2)),
        f("growth_acceleration", "Growth Acceleration", FactorCategory.GROWTH, income, frozenset(),
          ("revenue",), (), 3, "3 annual periods", Unit.FRACTION, growth_acceleration),
        f("margin_trend", "Margin Trend", FactorCategory.QUALITY, income, frozenset(),
          ("net_margin",), (), 3, "3 annual periods", Unit.FRACTION, margin_trend),
        f("valuation_level", "Valuation Level", FactorCategory.VALUATION, valuation, frozenset(),
          ("pe",), ("pb", "ps"), 1, "latest trading day", Unit.MULTIPLE, valuation_level),
        f("valuation_percentile", "PE Valuation Percentile", FactorCategory.VALUATION, valuation, frozenset(),
          ("pe",), (), 252, "252 positive days / 365 calendar days", Unit.FRACTION, valuation_percentile),
    ]
    for horizon, count, days, scale in (("1m", 21, 28, "0.1"), ("3m", 63, 84, "0.2"),
                                        ("6m", 126, 175, "0.3"), ("12m", 252, 350, "0.5")):
        factors.append(f(f"momentum_{horizon}", f"Momentum {horizon.upper()}",
                         FactorCategory.PRICE_BEHAVIOR, adjusted, frozenset(), (), (), count,
                         horizon, Unit.FRACTION, momentum(count, days, scale)))
    factors += [
        f("drawdown_6m", "Drawdown 6M", FactorCategory.PRICE_BEHAVIOR, adjusted, frozenset(),
          (), (), 126, "6m", Unit.FRACTION, drawdown),
        f("volatility_3m", "Volatility 3M", FactorCategory.PRICE_BEHAVIOR, adjusted, frozenset(),
          (), (), 64, "3m annualized / sqrt(252)", Unit.FRACTION, volatility),
    ]
    return tuple(factors)
