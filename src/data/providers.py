"""Provider metadata and registry skeleton; not wired into production calls."""

from __future__ import annotations

from datetime import date, datetime
from typing import Protocol, runtime_checkable
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator, model_validator

from src.data.capabilities import AccessTier, Capability, Market
from src.data.domain import Adjustment, DataEnvelope, FinancialStatement, Instrument, PriceBar, ValuationSnapshot

class DataRequest(BaseModel):
    capability: Capability
    instrument: Instrument
    as_of: datetime
    start_date: date | None = None
    end_date: date | None = None
    frequency: str = "daily"
    adjustment: Adjustment = Adjustment.UNADJUSTED
    financial_period: str | None = None
    compatibility_mode: bool = False

    @field_validator("as_of")
    @classmethod
    def aware_as_of(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("as_of must include a timezone")
        return value

    @model_validator(mode="after")
    def valid_dates(self) -> DataRequest:
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date cannot follow end_date")
        if self.end_date and self.end_date > self.as_of.astimezone(ZoneInfo("Asia/Shanghai")).date():
            raise ValueError("end_date cannot be after as_of")
        return self


@runtime_checkable
class DataProvider(Protocol):
    @property
    def provider_id(self) -> str: ...

    @property
    def capabilities(self) -> frozenset[Capability]: ...

    def supports(self, request: DataRequest) -> bool: ...


class PriceHistoryProvider(DataProvider, Protocol):
    def get_price_history(self, request: DataRequest) -> DataEnvelope[list[PriceBar]]: ...


class FinancialStatementProvider(DataProvider, Protocol):
    def get_financial_statements(self, request: DataRequest) -> DataEnvelope[list[FinancialStatement]]: ...


class ValuationHistoryProvider(DataProvider, Protocol):
    def get_valuation_history(self, request: DataRequest) -> DataEnvelope[list[ValuationSnapshot]]: ...


class ProviderDescriptor(BaseModel):
    """Capability claims for current sources, not an active adapter."""

    provider_id: str = Field(min_length=1)
    capabilities: frozenset[Capability]
    markets: frozenset[Market]
    access_tier: AccessTier

    def supports(self, request: DataRequest) -> bool:
        return request.capability in self.capabilities and request.instrument.market in self.markets


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, DataProvider] = {}

    def register(self, provider: DataProvider) -> None:
        if not isinstance(provider, DataProvider):
            raise TypeError("provider must implement DataProvider")
        if not provider.provider_id or provider.provider_id in self._providers:
            raise ValueError("provider_id must be nonempty and unique")
        self._providers[provider.provider_id] = provider

    def get(self, provider_id: str) -> DataProvider:
        return self._providers[provider_id]

    def supporting(self, request: DataRequest) -> tuple[DataProvider, ...]:
        return tuple(p for p in self._providers.values() if p.supports(request))

    def all(self) -> tuple[DataProvider, ...]:
        return tuple(self._providers.values())


def current_provider_registry() -> ProviderRegistry:
    """Register existing sources without executing requests."""
    from src.data.adapters import BaoStockProvider, AKShareSinaProvider, AKShareEastMoneyProvider

    registry = ProviderRegistry()
    registry.register(BaoStockProvider())
    registry.register(AKShareSinaProvider())
    registry.register(AKShareEastMoneyProvider())
    return registry
