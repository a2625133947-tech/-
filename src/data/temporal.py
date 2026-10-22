"""Temporal capability policies and point-in-time constraints.

Defines point-in-time (PIT) classifications, reconstructibility, and archive
dependencies for all data capabilities based on free A-share provider semantics.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Mapping

from pydantic import BaseModel, ConfigDict

from src.data.capabilities import Capability
from src.data.domain import DataStatus
from src.factors.contracts import FactorContext, PriceInput, RawMetricPoint, RawMetricSeries


class TemporalClassification(StrEnum):
    """How historical observations can be obtained or reconstructed."""

    HISTORICALLY_RECONSTRUCTIBLE = "historically_reconstructible"
    """Source payload contains authentic available_at (e.g. statement announcement dates)
    allowing safe reconstruction of historical as_of states without look-ahead bias."""

    ARCHIVED_ONLY = "archived_only"
    """Historical replay requires an archived snapshot captured on or before as_of.
    Cannot be retrospectively reconstructed from today's live free endpoints."""

    CURRENT_ONLY = "current_only"
    """Represents only current snapshot state at capture time (e.g. current CSRC industry).
    Cannot be backfilled to arbitrary past historical dates."""

    UNAVAILABLE = "unavailable"
    """No verified provider implementation currently exists."""


class PitSafetyLevel(StrEnum):
    """Point-in-time safety classification for retrospective backtesting and shadow replay."""

    PIT_SAFE = "pit_safe"
    """Fully safe for retrospective evaluation at historical as_of."""

    PIT_PARTIAL = "pit_partial"
    """Conditionally safe: safe when replaying a prospective archived snapshot,
    but not reconstructible from live endpoints for retrospective evaluation."""

    CURRENT_ONLY = "current_only"
    """Unsafe for historical retrospective evaluation; must never backfill past dates."""


class CapabilityTemporalPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    capability: Capability
    classification: TemporalClassification
    pit_safety: PitSafetyLevel
    has_archived_revisions: bool
    retrospective_eligible: bool
    prospective_eligible: bool
    note: str


_POLICIES: dict[Capability, CapabilityTemporalPolicy] = {
    # -------------------------------------------------------------
    # Historically Reconstructible Financial Statements & Line Items
    # -------------------------------------------------------------
    Capability.INCOME_STATEMENT: CapabilityTemporalPolicy(
        capability=Capability.INCOME_STATEMENT,
        classification=TemporalClassification.HISTORICALLY_RECONSTRUCTIBLE,
        pit_safety=PitSafetyLevel.PIT_SAFE,
        has_archived_revisions=True,
        retrospective_eligible=True,
        prospective_eligible=True,
        note="AKShare/Sina statements include authentic announcement dates as available_at.",
    ),
    Capability.BALANCE_SHEET: CapabilityTemporalPolicy(
        capability=Capability.BALANCE_SHEET,
        classification=TemporalClassification.HISTORICALLY_RECONSTRUCTIBLE,
        pit_safety=PitSafetyLevel.PIT_SAFE,
        has_archived_revisions=True,
        retrospective_eligible=True,
        prospective_eligible=True,
        note="AKShare/Sina balance sheets include authentic announcement dates as available_at.",
    ),
    Capability.CASH_FLOW_STATEMENT: CapabilityTemporalPolicy(
        capability=Capability.CASH_FLOW_STATEMENT,
        classification=TemporalClassification.HISTORICALLY_RECONSTRUCTIBLE,
        pit_safety=PitSafetyLevel.PIT_SAFE,
        has_archived_revisions=True,
        retrospective_eligible=True,
        prospective_eligible=True,
        note="AKShare/Sina cash flows include authentic announcement dates as available_at.",
    ),
    Capability.REVENUE: CapabilityTemporalPolicy(
        capability=Capability.REVENUE,
        classification=TemporalClassification.HISTORICALLY_RECONSTRUCTIBLE,
        pit_safety=PitSafetyLevel.PIT_SAFE,
        has_archived_revisions=True,
        retrospective_eligible=True,
        prospective_eligible=True,
        note="Derived from income statement with authentic announcement date.",
    ),
    Capability.NET_INCOME: CapabilityTemporalPolicy(
        capability=Capability.NET_INCOME,
        classification=TemporalClassification.HISTORICALLY_RECONSTRUCTIBLE,
        pit_safety=PitSafetyLevel.PIT_SAFE,
        has_archived_revisions=True,
        retrospective_eligible=True,
        prospective_eligible=True,
        note="Derived from income statement with authentic announcement date.",
    ),
    Capability.CAPEX: CapabilityTemporalPolicy(
        capability=Capability.CAPEX,
        classification=TemporalClassification.HISTORICALLY_RECONSTRUCTIBLE,
        pit_safety=PitSafetyLevel.PIT_SAFE,
        has_archived_revisions=True,
        retrospective_eligible=True,
        prospective_eligible=True,
        note="Derived from cash flow statement with authentic announcement date.",
    ),
    Capability.FREE_CASH_FLOW: CapabilityTemporalPolicy(
        capability=Capability.FREE_CASH_FLOW,
        classification=TemporalClassification.HISTORICALLY_RECONSTRUCTIBLE,
        pit_safety=PitSafetyLevel.PIT_SAFE,
        has_archived_revisions=True,
        retrospective_eligible=True,
        prospective_eligible=True,
        note="Derived from operating cash flow and capex with authentic announcement date.",
    ),
    Capability.ROE: CapabilityTemporalPolicy(
        capability=Capability.ROE,
        classification=TemporalClassification.HISTORICALLY_RECONSTRUCTIBLE,
        pit_safety=PitSafetyLevel.PIT_SAFE,
        has_archived_revisions=True,
        retrospective_eligible=True,
        prospective_eligible=True,
        note="Derived from annual income and balance sheets with authentic announcement dates.",
    ),
    Capability.GROSS_MARGIN: CapabilityTemporalPolicy(
        capability=Capability.GROSS_MARGIN,
        classification=TemporalClassification.HISTORICALLY_RECONSTRUCTIBLE,
        pit_safety=PitSafetyLevel.PIT_SAFE,
        has_archived_revisions=True,
        retrospective_eligible=True,
        prospective_eligible=True,
        note="Derived from income statement line items.",
    ),
    Capability.OPERATING_MARGIN: CapabilityTemporalPolicy(
        capability=Capability.OPERATING_MARGIN,
        classification=TemporalClassification.HISTORICALLY_RECONSTRUCTIBLE,
        pit_safety=PitSafetyLevel.PIT_SAFE,
        has_archived_revisions=True,
        retrospective_eligible=True,
        prospective_eligible=True,
        note="Derived from income statement line items.",
    ),
    Capability.NET_MARGIN: CapabilityTemporalPolicy(
        capability=Capability.NET_MARGIN,
        classification=TemporalClassification.HISTORICALLY_RECONSTRUCTIBLE,
        pit_safety=PitSafetyLevel.PIT_SAFE,
        has_archived_revisions=True,
        retrospective_eligible=True,
        prospective_eligible=True,
        note="Derived from income statement line items.",
    ),
    # -------------------------------------------------------------
    # Daily Unadjusted Trading Prices & Volume
    # -------------------------------------------------------------
    Capability.PRICE_DAILY: CapabilityTemporalPolicy(
        capability=Capability.PRICE_DAILY,
        classification=TemporalClassification.HISTORICALLY_RECONSTRUCTIBLE,
        pit_safety=PitSafetyLevel.PIT_SAFE,
        has_archived_revisions=False,
        retrospective_eligible=True,
        prospective_eligible=True,
        note="Unadjusted daily OHLC bars are published on market close; not rewritten by corporate actions.",
    ),
    Capability.VOLUME: CapabilityTemporalPolicy(
        capability=Capability.VOLUME,
        classification=TemporalClassification.HISTORICALLY_RECONSTRUCTIBLE,
        pit_safety=PitSafetyLevel.PIT_SAFE,
        has_archived_revisions=False,
        retrospective_eligible=True,
        prospective_eligible=True,
        note="Unadjusted daily trading volume.",
    ),
    # -------------------------------------------------------------
    # Archived-Only Capabilities (Require Prior Snapshots for PIT replay)
    # -------------------------------------------------------------
    Capability.PRICE_ADJUSTED: CapabilityTemporalPolicy(
        capability=Capability.PRICE_ADJUSTED,
        classification=TemporalClassification.ARCHIVED_ONLY,
        pit_safety=PitSafetyLevel.PIT_PARTIAL,
        has_archived_revisions=False,
        retrospective_eligible=False,
        prospective_eligible=True,
        note="BaoStock backward-adjusted prices rewrite historical bars on corporate actions; require saved snapshot.",
    ),
    Capability.VALUATION_HISTORY: CapabilityTemporalPolicy(
        capability=Capability.VALUATION_HISTORY,
        classification=TemporalClassification.ARCHIVED_ONLY,
        pit_safety=PitSafetyLevel.PIT_PARTIAL,
        has_archived_revisions=False,
        retrospective_eligible=False,
        prospective_eligible=True,
        note="BaoStock daily PE/PB/PS history has no point-in-time publication guarantee or revision archive.",
    ),
    Capability.PE: CapabilityTemporalPolicy(
        capability=Capability.PE,
        classification=TemporalClassification.ARCHIVED_ONLY,
        pit_safety=PitSafetyLevel.PIT_PARTIAL,
        has_archived_revisions=False,
        retrospective_eligible=False,
        prospective_eligible=True,
        note="Daily valuation multiple; requires local archive.",
    ),
    Capability.PB: CapabilityTemporalPolicy(
        capability=Capability.PB,
        classification=TemporalClassification.ARCHIVED_ONLY,
        pit_safety=PitSafetyLevel.PIT_PARTIAL,
        has_archived_revisions=False,
        retrospective_eligible=False,
        prospective_eligible=True,
        note="Daily valuation multiple; requires local archive.",
    ),
    Capability.PS: CapabilityTemporalPolicy(
        capability=Capability.PS,
        classification=TemporalClassification.ARCHIVED_ONLY,
        pit_safety=PitSafetyLevel.PIT_PARTIAL,
        has_archived_revisions=False,
        retrospective_eligible=False,
        prospective_eligible=True,
        note="Daily valuation multiple; requires local archive.",
    ),
    Capability.DIVIDEND: CapabilityTemporalPolicy(
        capability=Capability.DIVIDEND,
        classification=TemporalClassification.ARCHIVED_ONLY,
        pit_safety=PitSafetyLevel.PIT_PARTIAL,
        has_archived_revisions=False,
        retrospective_eligible=False,
        prospective_eligible=True,
        note="BaoStock dividend payout visible after ex-date; plan date retained but lacks revision history.",
    ),
    Capability.SHARE_CAPITAL: CapabilityTemporalPolicy(
        capability=Capability.SHARE_CAPITAL,
        classification=TemporalClassification.ARCHIVED_ONLY,
        pit_safety=PitSafetyLevel.PIT_PARTIAL,
        has_archived_revisions=False,
        retrospective_eligible=False,
        prospective_eligible=True,
        note="Effective date is known, publication timestamp is not archived by free source.",
    ),
    Capability.SHARE_CAPITAL_EVENTS: CapabilityTemporalPolicy(
        capability=Capability.SHARE_CAPITAL_EVENTS,
        classification=TemporalClassification.ARCHIVED_ONLY,
        pit_safety=PitSafetyLevel.PIT_PARTIAL,
        has_archived_revisions=False,
        retrospective_eligible=False,
        prospective_eligible=True,
        note="Event history requires prospective snapshot capture.",
    ),
    Capability.MARKET_CAP: CapabilityTemporalPolicy(
        capability=Capability.MARKET_CAP,
        classification=TemporalClassification.ARCHIVED_ONLY,
        pit_safety=PitSafetyLevel.PIT_PARTIAL,
        has_archived_revisions=False,
        retrospective_eligible=False,
        prospective_eligible=True,
        note="Depends on dated shares and price closing.",
    ),
    Capability.EV_EBITDA: CapabilityTemporalPolicy(
        capability=Capability.EV_EBITDA,
        classification=TemporalClassification.ARCHIVED_ONLY,
        pit_safety=PitSafetyLevel.PIT_PARTIAL,
        has_archived_revisions=False,
        retrospective_eligible=False,
        prospective_eligible=True,
        note="Derived composite; requires market cap and balance sheet.",
    ),
    Capability.FCF_YIELD: CapabilityTemporalPolicy(
        capability=Capability.FCF_YIELD,
        classification=TemporalClassification.ARCHIVED_ONLY,
        pit_safety=PitSafetyLevel.PIT_PARTIAL,
        has_archived_revisions=False,
        retrospective_eligible=False,
        prospective_eligible=True,
        note="Requires free cash flow and market cap.",
    ),
    Capability.NEWS: CapabilityTemporalPolicy(
        capability=Capability.NEWS,
        classification=TemporalClassification.ARCHIVED_ONLY,
        pit_safety=PitSafetyLevel.PIT_PARTIAL,
        has_archived_revisions=False,
        retrospective_eligible=False,
        prospective_eligible=True,
        note="Rolling headlines disappear from feed; historical requests require saved snapshot.",
    ),
    # -------------------------------------------------------------
    # Current-Only Capabilities (Never backfill historical as_of)
    # -------------------------------------------------------------
    Capability.INDUSTRY: CapabilityTemporalPolicy(
        capability=Capability.INDUSTRY,
        classification=TemporalClassification.CURRENT_ONLY,
        pit_safety=PitSafetyLevel.CURRENT_ONLY,
        has_archived_revisions=False,
        retrospective_eligible=False,
        prospective_eligible=True,
        note="BaoStock returns current CSRC industry classification without historical revision archive.",
    ),
    Capability.SECTOR: CapabilityTemporalPolicy(
        capability=Capability.SECTOR,
        classification=TemporalClassification.CURRENT_ONLY,
        pit_safety=PitSafetyLevel.CURRENT_ONLY,
        has_archived_revisions=False,
        retrospective_eligible=False,
        prospective_eligible=True,
        note="Current classification only.",
    ),
    Capability.INSTRUMENT_METADATA: CapabilityTemporalPolicy(
        capability=Capability.INSTRUMENT_METADATA,
        classification=TemporalClassification.CURRENT_ONLY,
        pit_safety=PitSafetyLevel.CURRENT_ONLY,
        has_archived_revisions=False,
        retrospective_eligible=False,
        prospective_eligible=True,
        note="Current stock name and basic metadata only.",
    ),
    Capability.COMPANY_PROFILE: CapabilityTemporalPolicy(
        capability=Capability.COMPANY_PROFILE,
        classification=TemporalClassification.CURRENT_ONLY,
        pit_safety=PitSafetyLevel.CURRENT_ONLY,
        has_archived_revisions=False,
        retrospective_eligible=False,
        prospective_eligible=True,
        note="Current company profile only.",
    ),
}

# Fill remaining capabilities as UNAVAILABLE
for _cap in Capability:
    if _cap not in _POLICIES:
        _POLICIES[_cap] = CapabilityTemporalPolicy(
            capability=_cap,
            classification=TemporalClassification.UNAVAILABLE,
            pit_safety=PitSafetyLevel.PIT_PARTIAL,
            has_archived_revisions=False,
            retrospective_eligible=False,
            prospective_eligible=False,
            note="No verified production implementation.",
        )


class TemporalCapabilityPolicy:
    """Query service and enforcement for temporal capability policies."""

    @staticmethod
    def get_policy(capability: Capability) -> CapabilityTemporalPolicy:
        return _POLICIES[capability]

    @staticmethod
    def all_policies() -> Mapping[Capability, CapabilityTemporalPolicy]:
        return _POLICIES

    @staticmethod
    def get_classification(capability: Capability) -> TemporalClassification:
        return _POLICIES[capability].classification

    @staticmethod
    def get_pit_safety(capability: Capability) -> PitSafetyLevel:
        return _POLICIES[capability].pit_safety

    @staticmethod
    def is_pit_safe(capability: Capability) -> bool:
        return _POLICIES[capability].pit_safety is PitSafetyLevel.PIT_SAFE

    @staticmethod
    def is_retrospective_eligible(capability: Capability) -> bool:
        return _POLICIES[capability].retrospective_eligible

    @staticmethod
    def is_archived_only(capability: Capability) -> bool:
        return _POLICIES[capability].classification is TemporalClassification.ARCHIVED_ONLY

    @staticmethod
    def is_current_only(capability: Capability) -> bool:
        return _POLICIES[capability].classification is TemporalClassification.CURRENT_ONLY


def filter_context_for_retrospective(
    context: FactorContext,
    as_of: datetime,
    *,
    allow_unadjusted_prices: bool = False,
) -> FactorContext:
    """Filter factor context for retrospective evaluation without look-ahead.

    Strict PIT enforcement:
    1. Financial metrics: retain only points where available_at <= as_of and observed_date <= as_of.date().
    2. Non-PIT-safe metrics (PE, PB, PS, etc.) are excluded or marked NOT_AVAILABLE_AS_OF.
    3. Price-derived adjusted factors: because backward-adjusted history is ARCHIVED_ONLY,
       retrospective evaluation without an archived snapshot marks price inputs as
       NOT_AVAILABLE_AS_OF, preventing look-ahead bias from future corporate actions.
    """
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    as_of = as_of.astimezone(timezone.utc)
    as_of_date = as_of.date()

    filtered_metrics: dict[str, RawMetricSeries] = {}
    for name, series in context.metrics.items():
        # Check capability policy if applicable
        # Financial metrics (revenue, net_income, roe, gross_margin, etc.) are PIT-safe
        # Valuation multiples (pe, pb, ps) from BaoStock are ARCHIVED_ONLY -> not eligible retrospectively
        if name in {"pe", "pb", "ps"}:
            filtered_metrics[name] = RawMetricSeries(
                metric_id=name,
                points=(),
                source_status=DataStatus.NOT_AVAILABLE_FOR_DATE,
            )
            continue

        visible_points = tuple(
            point for point in series.points
            if point.provenance.visible_as_of(as_of) and point.observed_date <= as_of_date
        )
        if visible_points:
            filtered_metrics[name] = RawMetricSeries(
                metric_id=name,
                points=visible_points,
                source_status=DataStatus.PRESENT,
            )
        else:
            status = (
                DataStatus.NOT_PUBLISHED
                if series.source_status is DataStatus.PRESENT
                else series.source_status
            )
            filtered_metrics[name] = RawMetricSeries(
                metric_id=name,
                points=(),
                source_status=status,
            )

    # Price handling:
    # Unless explicit unadjusted prices are allowed, adjusted price history is ARCHIVED_ONLY
    # and cannot be safely backfilled retrospectively.
    if allow_unadjusted_prices:
        bars = tuple(bar for bar in context.prices.bars if bar.trading_date <= as_of_date)
        prices = context.prices.model_copy(update={"bars": bars})
    else:
        prices = PriceInput(
            bars=(),
            provenance=None,
            status=DataStatus.NOT_AVAILABLE_FOR_DATE,
            conflict=False,
        )

    return FactorContext(
        ticker=context.ticker,
        as_of=as_of,
        metrics=filtered_metrics,
        prices=prices,
    )
