"""Names and metadata for data abilities; no production routing occurs here."""

from enum import StrEnum


class Capability(StrEnum):
    INSTRUMENT_METADATA = "instrument_metadata"
    PRICE_DAILY = "price_daily"
    PRICE_INTRADAY = "price_intraday"
    PRICE_ADJUSTED = "price_adjusted"
    VOLUME = "volume"
    MARKET_CAP = "market_cap"
    INCOME_STATEMENT = "income_statement"
    BALANCE_SHEET = "balance_sheet"
    CASH_FLOW_STATEMENT = "cash_flow_statement"
    ROE = "roe"
    ROIC = "roic"
    GROSS_MARGIN = "gross_margin"
    OPERATING_MARGIN = "operating_margin"
    NET_MARGIN = "net_margin"
    REVENUE = "revenue"
    NET_INCOME = "net_income"
    FREE_CASH_FLOW = "free_cash_flow"
    CAPEX = "capex"
    PE = "pe"
    PB = "pb"
    PS = "ps"
    EV_EBITDA = "ev_ebitda"
    FCF_YIELD = "fcf_yield"
    DIVIDEND = "dividend"
    SHARE_CAPITAL = "share_capital"
    SHARE_CAPITAL_EVENTS = "share_capital_events"
    CORPORATE_ACTIONS = "corporate_actions"
    INDUSTRY = "industry"
    SECTOR = "sector"
    COMPANY_PROFILE = "company_profile"
    VALUATION_HISTORY = "valuation_history"
    NEWS = "news"
    ANNOUNCEMENTS = "announcements"
    ANALYST_ESTIMATES = "analyst_estimates"
    EARNINGS_REVISIONS = "earnings_revisions"
    CONSENSUS_FORECAST = "consensus_forecast"
    MANAGEMENT = "management"
    OWNERSHIP = "ownership"
    MAJOR_SHAREHOLDERS = "major_shareholders"
    MANAGEMENT_HOLDINGS = "management_holdings"
    SHAREHOLDER_CHANGES = "shareholder_changes"
    LOCKUP_RELEASE = "lockup_release"
    PLEDGE = "pledge"


class Availability(StrEnum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class AccessTier(StrEnum):
    FREE = "free"
    REGISTERED_FREE = "registered_free"
    PAID = "paid"
    UNKNOWN = "unknown"


class Market(StrEnum):
    CN_SH = "cn_sh"
    CN_SZ = "cn_sz"
    US = "us"
    OTHER = "other"
