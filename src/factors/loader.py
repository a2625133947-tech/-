"""Build objective raw metric series from DataService normalized observations."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from src.data.capabilities import Capability
from src.data.domain import Adjustment, DataStatus, Instrument, Provenance, Quality, StatementType, Unit
from src.data.pipeline import DataService
from src.data.providers import DataRequest
from src.factors.contracts import FactorContext, PriceInput, RawMetricPoint, RawMetricSeries


_FINANCIAL_FIELDS = {
    Capability.INCOME_STATEMENT: ("revenue", "cost_of_revenue", "net_income", "operating_income"),
    Capability.BALANCE_SHEET: ("shareholders_equity", "short_term_debt", "current_portion_long_term_debt",
                               "long_term_debt", "bonds_payable", "current_assets", "current_liabilities",
                               "cash_and_equivalents"),
    Capability.CASH_FLOW_STATEMENT: ("operating_cash_flow", "capital_expenditure"),
}


class RawMetricLoader:
    def __init__(self, service: DataService):
        self.service = service

    def load(self, instrument: Instrument, as_of: datetime,
             *, financial_start: date | None = None,
             market_start: date | None = None) -> FactorContext:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        end = as_of.astimezone(ZoneInfo("Asia/Shanghai")).date()
        financial_start = financial_start or date(max(1990, end.year - 6), 1, 1)
        market_start = market_start or end - timedelta(days=430)
        points: dict[str, list[RawMetricPoint]] = defaultdict(list)
        statuses: dict[str, DataStatus] = {}

        def request(capability, start, adjustment=Adjustment.UNADJUSTED):
            return DataRequest(capability=capability, instrument=instrument,
                               as_of=as_of, start_date=start, end_date=end,
                               adjustment=adjustment, compatibility_mode=False)

        for capability, expected in _FINANCIAL_FIELDS.items():
            result = self.service.get_financial_statements(request(capability, financial_start))
            for field in expected:
                statuses[field] = result.status
            if result.status is not DataStatus.PRESENT:
                continue
            source = result.observation
            for statement in source.value:
                for field in statement.fields:
                    if field.value is None:
                        continue
                    provenance = Provenance(provider=result.provider, period=statement.period,
                        observed_date=statement.period_end, available_at=statement.available_at,
                        retrieved_at=source.retrieved_at, unit=field.unit,
                        quality=Quality.DEGRADED if result.conflict else source.quality,
                        revision=statement.revision)
                    points[field.name].append(RawMetricPoint(metric_id=field.name, value=field.value,
                        observed_date=statement.period_end, period=statement.period, provenance=provenance))

        by_date = {metric: {point.observed_date: point for point in series}
                   for metric, series in points.items()}
        def derive(name, day, value, *sources, period=None):
            if value is None or not value.is_finite():
                return
            first = sources[0]
            provenance = first.provenance.model_copy(update={"unit":
                Unit.FRACTION if name in {"net_margin", "operating_margin", "gross_margin", "roe"}
                else Unit.MULTIPLE if name in {"debt_to_equity", "current_ratio", "cash_ratio"}
                else Unit.CNY,
                "available_at": max(source.provenance.available_at for source in sources),
                "retrieved_at": max(source.provenance.retrieved_at for source in sources),
                "quality": min((source.provenance.quality for source in sources),
                               key={Quality.DEGRADED: 0, Quality.UNVERIFIED: 1, Quality.VALIDATED: 2}.__getitem__)})
            points[name].append(RawMetricPoint(metric_id=name, value=value, observed_date=day,
                period=period or first.period, provenance=provenance,
                source_inputs=tuple(source.provenance for source in sources[1:])))

        for day, revenue in by_date.get("revenue", {}).items():
            for target, numerator in (("net_margin", "net_income"),
                                      ("operating_margin", "operating_income")):
                item = by_date.get(numerator, {}).get(day)
                if item and revenue.value > 0:
                    derive(target, day, item.value / revenue.value, item, revenue)
            cost = by_date.get("cost_of_revenue", {}).get(day)
            if cost and revenue.value > 0:
                derive("gross_margin", day, (revenue.value - cost.value) / revenue.value, revenue, cost)

        for day, cash in by_date.get("operating_cash_flow", {}).items():
            capex = by_date.get("capital_expenditure", {}).get(day)
            if capex:
                derive("free_cash_flow", day, cash.value - abs(capex.value), cash, capex)

        for day, equity in by_date.get("shareholders_equity", {}).items():
            debt_parts = [by_date.get(name, {}).get(day) for name in
                          ("short_term_debt", "current_portion_long_term_debt", "long_term_debt", "bonds_payable")]
            debt_parts = [part for part in debt_parts if part is not None]
            if debt_parts and equity.value > 0:
                derive("debt_to_equity", day, sum((part.value for part in debt_parts), Decimal(0)) / equity.value,
                       equity, *debt_parts)
            income = by_date.get("net_income", {}).get(day)
            prior = by_date.get("shareholders_equity", {}).get(date(day.year - 1, day.month, day.day))
            if income and prior and income.period == "annual" and equity.value + prior.value > 0:
                derive("roe", day, income.value / ((equity.value + prior.value) / 2),
                       income, equity, prior, period="annual")
            current_assets = by_date.get("current_assets", {}).get(day)
            current_liabilities = by_date.get("current_liabilities", {}).get(day)
            cash = by_date.get("cash_and_equivalents", {}).get(day)
            if current_liabilities and current_liabilities.value > 0:
                if current_assets:
                    derive("current_ratio", day, current_assets.value / current_liabilities.value,
                           current_assets, current_liabilities)
                if cash:
                    derive("cash_ratio", day, cash.value / current_liabilities.value,
                           cash, current_liabilities)

        valuation = self.service.fetch(request(Capability.VALUATION_HISTORY, market_start))
        for name in ("pe", "pb", "ps"):
            statuses[name] = valuation.status
        if valuation.status is DataStatus.PRESENT:
            for item in valuation.observation.value:
                for name in ("pe", "pb", "ps"):
                    value = getattr(item, name)
                    if value is not None and value.is_finite():
                        provenance = Provenance(provider=item.provider, observed_date=item.observed_date,
                            period="daily", available_at=item.available_at, retrieved_at=item.retrieved_at,
                            unit=Unit.MULTIPLE, quality=Quality.DEGRADED if valuation.conflict else item.quality,
                            revision=item.revision)
                        points[name].append(RawMetricPoint(metric_id=name, value=value,
                            observed_date=item.observed_date, period="daily", provenance=provenance))

        adjusted = self.service.fetch(request(Capability.PRICE_ADJUSTED, market_start, Adjustment.BACKWARD))
        price = PriceInput(status=adjusted.status, conflict=adjusted.conflict)
        if adjusted.status is DataStatus.PRESENT:
            price = PriceInput(bars=tuple(adjusted.observation.value),
                               provenance=adjusted.observation, status=adjusted.status,
                               conflict=adjusted.conflict)
        all_names = set(statuses) | set(points)
        series = {name: RawMetricSeries(metric_id=name,
                  points=tuple(sorted(points.get(name, ()), key=lambda item: item.observed_date)),
                  source_status=DataStatus.PRESENT if points.get(name) else statuses.get(name, DataStatus.MISSING))
                  for name in all_names}
        return FactorContext(ticker=instrument.ticker, as_of=as_of, metrics=series, prices=price)
