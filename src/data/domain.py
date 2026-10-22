"""Small normalized data contracts, separate from legacy production models."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.data.capabilities import Market

T = TypeVar("T")


class Unit(StrEnum):
    CNY = "CNY"
    USD = "USD"
    SHARES = "shares"
    COUNT = "count"
    FRACTION = "fraction"
    MULTIPLE = "multiple"
    NONE = "none"


class Quality(StrEnum):
    UNVERIFIED = "unverified"
    VALIDATED = "validated"
    DEGRADED = "degraded"


class DataStatus(StrEnum):
    PRESENT = "present"
    EMPTY_SUCCESS = "empty_success"
    MISSING = "missing"
    PROVIDER_FAILURE = "provider_failure"
    UNSUPPORTED = "unsupported"
    NOT_PUBLISHED = "not_published"
    INVALID_QUALITY = "invalid_quality"
    NOT_AVAILABLE_FOR_DATE = "not_available_for_date"


class Adjustment(StrEnum):
    UNADJUSTED = "unadjusted"
    FORWARD = "forward"
    BACKWARD = "backward"


def percent_to_fraction(value: Decimal | str | int | float) -> Decimal:
    """Normalize a provider's 33.25 percent to the internal 0.3325 fraction."""
    result = Decimal(str(value)) / Decimal("100")
    if not result.is_finite():
        raise ValueError("percentage must be finite")
    return result


class Instrument(BaseModel):
    ticker: str = Field(min_length=1)
    market: Market
    currency: Unit
    name: str | None = None


class PriceBar(BaseModel):
    instrument: Instrument
    trading_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None = Field(default=None, ge=0)
    adjustment: Adjustment = Adjustment.UNADJUSTED
    raw_open: Decimal | None = None
    raw_high: Decimal | None = None
    raw_low: Decimal | None = None
    raw_close: Decimal | None = None
    adjustment_factor: Decimal | None = None
    source_factor: Decimal | None = None
    source_factor_date: date | None = None

    @model_validator(mode="after")
    def valid_ohlc(self) -> PriceBar:
        prices = (self.open, self.high, self.low, self.close)
        if not all(value.is_finite() and value > 0 for value in prices):
            raise ValueError("prices must be positive and finite")
        if self.high < max(self.open, self.close, self.low) or self.low > min(self.open, self.close, self.high):
            raise ValueError("inconsistent OHLC values")
        return self


class DividendEvent(BaseModel):
    instrument: Instrument
    announced_date: date
    ex_date: date
    cash_per_share: Decimal = Field(ge=0)
    stock_per_share: Decimal = Field(ge=0)
    provider: str
    available_at: datetime
    retrieved_at: datetime
    quality: Quality = Quality.UNVERIFIED


class StatementType(StrEnum):
    INCOME = "income"
    BALANCE_SHEET = "balance_sheet"
    CASH_FLOW = "cash_flow"


class FinancialField(BaseModel):
    name: str = Field(min_length=1)
    value: Decimal | None
    unit: Unit


class FinancialStatement(BaseModel):
    instrument: Instrument
    statement_type: StatementType
    period_end: date
    period: str = Field(min_length=1)  # e.g. annual, quarter, ttm
    fields: tuple[FinancialField, ...]
    available_at: datetime
    revision: str | None = None

    @field_validator("available_at")
    @classmethod
    def aware_publication(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("financial publication time must include timezone")
        return value


class ValuationSnapshot(BaseModel):
    instrument: Instrument
    observed_date: date
    pe: Decimal | None = None
    pb: Decimal | None = None
    ps: Decimal | None = None
    market_cap: Decimal | None = None
    close: Decimal | None = None
    provider: str
    available_at: datetime
    retrieved_at: datetime
    quality: Quality = Quality.UNVERIFIED
    revision: str | None = None
    market_cap_inputs: tuple[Provenance, ...] = ()


class ShareCapitalEvent(BaseModel):
    instrument: Instrument
    effective_date: date
    total_shares: Decimal = Field(gt=0)
    provider: str
    available_at: datetime
    retrieved_at: datetime
    quality: Quality = Quality.UNVERIFIED


class CompanyProfile(BaseModel):
    instrument: Instrument
    name: str
    industry: str | None = None
    sector: str | None = None
    website: str | None = None


class NewsItem(BaseModel):
    instrument: Instrument
    title: str = Field(min_length=1)
    published_at: datetime
    url: str | None = None
    source: str | None = None


class Provenance(BaseModel):
    """Source and publication metadata shared by observed values."""

    provider: str = Field(min_length=1)
    period: str | None = None
    observed_date: date | None = None
    available_at: datetime
    retrieved_at: datetime
    unit: Unit
    quality: Quality = Quality.UNVERIFIED
    revision: str | None = None

    @field_validator("available_at", "retrieved_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must include a timezone")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def valid_provenance(self) -> Provenance:
        if self.period is None and self.observed_date is None:
            raise ValueError("period or observed_date is required")
        if self.retrieved_at < self.available_at:
            raise ValueError("retrieved_at cannot predate available_at")
        return self

    def visible_as_of(self, as_of: datetime) -> bool:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must include a timezone")
        return self.available_at <= as_of.astimezone(timezone.utc)


class ObservedValue(Provenance, Generic[T]):
    """A real value; absent or failed data belongs in DataEnvelope.status."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    value: T

    @model_validator(mode="after")
    def valid_value(self) -> ObservedValue[T]:
        if self.value is None:
            raise ValueError("use DataStatus.MISSING rather than a null observed value")
        if isinstance(self.value, Decimal) and not self.value.is_finite():
            raise ValueError("numeric value must be finite")
        return self


class DataEnvelope(BaseModel, Generic[T]):
    """An observation or an explicit absence/failure state."""

    status: DataStatus
    observation: ObservedValue[T] | None = None
    provider: str = Field(min_length=1)
    reason: str | None = None
    is_fallback: bool = False
    is_derived: bool = False
    raw_hash: str | None = None
    conflict: bool = False

    @model_validator(mode="after")
    def consistent_status(self) -> DataEnvelope[T]:
        if self.status is DataStatus.PRESENT:
            if self.observation is None or self.observation.provider != self.provider:
                raise ValueError("present data requires an observation from the same provider")
        elif self.observation is not None:
            raise ValueError("non-present status cannot contain an observation")
        return self

    def as_of(self, at: datetime) -> DataEnvelope[T]:
        """Never expose an observation before its publication time."""
        if self.status is DataStatus.PRESENT and not self.observation.visible_as_of(at):
            return DataEnvelope[T](status=DataStatus.NOT_PUBLISHED, provider=self.provider,
                                   reason="observation was not available as of the requested time")
        return self
