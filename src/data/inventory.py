"""Read-only inventory of currently implemented A-share data abilities.

This describes the existing production path. It does not enable routing or
claim that every ticker/date has a non-missing value.
"""

from pydantic import BaseModel

from src.data.capabilities import AccessTier, Availability, Capability


class CapabilityAssessment(BaseModel):
    capability: Capability
    availability: Availability
    access_tier: AccessTier
    providers: tuple[str, ...] = ()
    note: str = ""


_AVAILABLE = {
    Capability.PRICE_DAILY: (("baostock",), "Unadjusted daily OHLC."),
    Capability.VOLUME: (("baostock",), "Daily volume."),
    Capability.INCOME_STATEMENT: (("akshare_sina",), "Sina reported statement."),
    Capability.BALANCE_SHEET: (("akshare_sina",), "Sina reported statement."),
    Capability.CASH_FLOW_STATEMENT: (("akshare_sina",), "Sina reported statement."),
}

_PARTIAL = {
    Capability.PRICE_ADJUSTED: (("baostock",), "Forward/backward history includes raw price and multiplier; vendor revisions are not point-in-time recoverable before local capture."),
    Capability.INDUSTRY: (("baostock",), "Current CSRC industry classification; historical revisions require local snapshots."),
    Capability.DIVIDEND: (("baostock",), "Final payout visible only after ex-date; plan date is retained but does not establish final-value availability. No official document ID."),
    Capability.INSTRUMENT_METADATA: (("baostock",), "Stock name only; no full company profile."),
    Capability.MARKET_CAP: (("baostock", "akshare_eastmoney"), "Needs dated shares and a valid close."),
    Capability.REVENUE: (("akshare_sina",), "Depends on reported line item and period."),
    Capability.NET_INCOME: (("akshare_sina",), "Depends on reported line item and period."),
    Capability.CAPEX: (("akshare_sina",), "Derived from a cash-flow line item."),
    Capability.FREE_CASH_FLOW: (("akshare_sina",), "Derived only when operating cash flow and capex exist."),
    Capability.ROE: (("akshare_sina",), "Derived only with current and prior equity."),
    Capability.GROSS_MARGIN: (("akshare_sina",), "Derived only with revenue and cost."),
    Capability.OPERATING_MARGIN: (("akshare_sina",), "Derived only with revenue and operating income."),
    Capability.NET_MARGIN: (("akshare_sina",), "Derived only with revenue and net income."),
    Capability.PE: (("baostock",), "Daily multiple; nonpositive values are data, not cheapness signals."),
    Capability.PB: (("baostock",), "Daily multiple; historical completeness not measured."),
    Capability.PS: (("baostock",), "Daily multiple; historical completeness not measured."),
    Capability.EV_EBITDA: (("baostock", "akshare_sina", "akshare_eastmoney"), "Derived when all inputs exist."),
    Capability.FCF_YIELD: (("baostock", "akshare_sina", "akshare_eastmoney"), "Derived when FCF and market cap exist."),
    Capability.SHARE_CAPITAL: (("akshare_eastmoney",), "Change date is known, publication date is not; strict historical availability is limited."),
    Capability.VALUATION_HISTORY: (("baostock",), "Normalized PE/PB/PS series; historical completeness not measured."),
    Capability.NEWS: (("akshare_eastmoney",), "Recent news only; strict historical requests require a saved snapshot."),
}


def current_a_share_inventory() -> tuple[CapabilityAssessment, ...]:
    """Enumerate every capability, keeping availability and access tier separate."""
    entries = []
    for capability in Capability:
        if capability in _AVAILABLE:
            providers, note = _AVAILABLE[capability]
            availability = Availability.AVAILABLE
        elif capability in _PARTIAL:
            providers, note = _PARTIAL[capability]
            availability = Availability.PARTIAL
        else:
            providers, note = (), "No verified production implementation."
            availability = Availability.UNAVAILABLE
        entries.append(CapabilityAssessment(
            capability=capability, availability=availability,
            access_tier=AccessTier.FREE if providers else AccessTier.UNKNOWN,
            providers=providers, note=note))
    return tuple(entries)
