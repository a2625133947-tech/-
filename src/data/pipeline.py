"""Capability routing, validation, cache, resolver, and data service."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from enum import StrEnum
from threading import RLock
from time import monotonic
from typing import Callable
import logging
import os
from datetime import datetime, timezone

from src.data.capabilities import Capability, Market
from src.data.domain import DataEnvelope, DataStatus, FinancialStatement, PriceBar, Provenance, Quality, Unit, ValuationSnapshot
from src.data.errors import Conflict, InvalidData, ProviderFailure, RateLimited, SchemaChanged, UnsupportedCapability
from src.data.providers import DataRequest, ProviderRegistry, current_provider_registry
from src.data.availability import DataAvailabilityReport

logger = logging.getLogger(__name__)


_active_outcomes: ContextVar[dict[tuple[str, Capability], DataEnvelope] | None] = ContextVar(
    "active_data_outcomes", default=None)


@contextmanager
def capture_data_availability():
    outcomes: dict[tuple[str, Capability], DataEnvelope] = {}
    token = _active_outcomes.set(outcomes)
    try:
        yield outcomes
    finally:
        _active_outcomes.reset(token)


ROUTES: dict[tuple[Market, Capability, str], tuple[str, ...]] = {}
for _market in (Market.CN_SH, Market.CN_SZ):
    for _capability in (Capability.PRICE_DAILY, Capability.VOLUME, Capability.INSTRUMENT_METADATA,
                        Capability.VALUATION_HISTORY, Capability.PE, Capability.PB, Capability.PS,
                        Capability.PRICE_ADJUSTED, Capability.INDUSTRY, Capability.DIVIDEND):
        ROUTES[_market, _capability, "daily"] = ("baostock",)
    for _capability in (Capability.INCOME_STATEMENT, Capability.BALANCE_SHEET,
                        Capability.CASH_FLOW_STATEMENT):
        ROUTES[_market, _capability, "daily"] = ("akshare_sina",)
    for _capability in (Capability.SHARE_CAPITAL, Capability.NEWS):
        ROUTES[_market, _capability, "daily"] = ("akshare_eastmoney",)


class CapabilityRouter:
    def __init__(self, routes=None):
        self.routes = dict(routes if routes is not None else ROUTES)

    def priorities(self, request: DataRequest) -> tuple[str, ...]:
        return self.routes.get((request.instrument.market, request.capability, request.frequency), ())


TTL_SECONDS = {
    Capability.PRICE_DAILY: 6 * 60 * 60,
    Capability.PRICE_ADJUSTED: 6 * 60 * 60,
    Capability.INDUSTRY: 24 * 60 * 60,
    Capability.DIVIDEND: 24 * 60 * 60,
    Capability.INSTRUMENT_METADATA: 24 * 60 * 60,
    Capability.VALUATION_HISTORY: 6 * 60 * 60,
    Capability.INCOME_STATEMENT: 24 * 60 * 60,
    Capability.BALANCE_SHEET: 24 * 60 * 60,
    Capability.CASH_FLOW_STATEMENT: 24 * 60 * 60,
    Capability.SHARE_CAPITAL: 24 * 60 * 60,
    Capability.NEWS: 5 * 60,
}


class DataCache:
    def __init__(self, clock: Callable[[], float] = monotonic):
        self._clock = clock
        self._entries: dict[tuple, tuple[float, DataEnvelope]] = {}
        self._lock = RLock()

    @staticmethod
    def key(provider_id: str, request: DataRequest) -> tuple:
        return (provider_id, request.capability, request.instrument.ticker,
                request.instrument.market, request.start_date, request.end_date,
                request.as_of, request.frequency, request.adjustment,
                request.financial_period, request.compatibility_mode)

    def get(self, provider_id: str, request: DataRequest) -> DataEnvelope | None:
        key = self.key(provider_id, request)
        with self._lock:
            item = self._entries.get(key)
            if item is None:
                return None
            expires, envelope = item
            if expires <= self._clock():
                del self._entries[key]
                return None
            return envelope.model_copy(deep=True)

    def put(self, provider_id: str, request: DataRequest, envelope: DataEnvelope) -> None:
        if envelope.status is DataStatus.PROVIDER_FAILURE:
            ttl = 5  # short backoff, never permanent negative caching
        elif envelope.status in (DataStatus.PRESENT, DataStatus.EMPTY_SUCCESS):
            ttl = TTL_SECONDS.get(request.capability, 300)
        else:
            ttl = 30
        with self._lock:
            self._entries[self.key(provider_id, request)] = (self._clock() + ttl,
                                                               envelope.model_copy(deep=True))

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


class ValidationLayer:
    def validate(self, request: DataRequest, envelope: DataEnvelope) -> DataEnvelope:
        if envelope.status is not DataStatus.PRESENT:
            return envelope
        observation = envelope.observation
        if not observation.visible_as_of(request.as_of):
            return envelope.as_of(request.as_of)
        data = observation.value
        if request.capability in (Capability.PRICE_DAILY, Capability.VOLUME, Capability.PRICE_ADJUSTED):
            dates = [bar.trading_date for bar in data]
            if dates != sorted(set(dates)):
                raise InvalidData("price dates must be strictly increasing without duplicates")
            if any(not isinstance(bar, PriceBar) or bar.adjustment != request.adjustment for bar in data):
                raise InvalidData("price bar adjustment mismatch")
            if request.capability is Capability.PRICE_ADJUSTED and any(
                    bar.raw_close is None or bar.adjustment_factor is None for bar in data):
                raise InvalidData("adjusted bar lacks raw price or factor")
        elif request.capability in (Capability.INCOME_STATEMENT, Capability.BALANCE_SHEET,
                                     Capability.CASH_FLOW_STATEMENT):
            dates = [item.period_end for item in data]
            if dates != sorted(set(dates)):
                raise InvalidData("duplicate or unordered financial period")
            for item in data:
                if not isinstance(item, FinancialStatement) or item.available_at > request.as_of:
                    raise InvalidData("financial period or publication time invalid")
                if item.period not in {"annual", "reported_ytd", "snapshot", "quarter", "ttm"}:
                    raise InvalidData("unknown financial period")
                if any(field.value is not None and not field.value.is_finite() for field in item.fields):
                    raise InvalidData("nonfinite financial field")
        elif request.capability in (Capability.VALUATION_HISTORY, Capability.PE, Capability.PB, Capability.PS):
            dates = [item.observed_date for item in data]
            if dates != sorted(set(dates)):
                raise InvalidData("duplicate or unordered valuation date")
            for item in data:
                if not isinstance(item, ValuationSnapshot):
                    raise InvalidData("invalid valuation row")
                if item.market_cap is not None and item.market_cap <= 0:
                    raise InvalidData("market cap must be positive")
                if any(value is not None and not value.is_finite() for value in (item.pe, item.pb, item.ps)):
                    raise InvalidData("nonfinite valuation multiple")
        return envelope


class ResolverPolicy(StrEnum):
    REPORTED_OVER_DERIVED = "reported_over_derived"
    AS_OF_VALID = "as_of_valid"
    SOURCE_PRIORITY = "source_priority"
    QUALITY_PRIORITY = "quality_priority"


class Resolver:
    policies = tuple(ResolverPolicy)

    @staticmethod
    def check_numeric_conflict(candidates: list[DataEnvelope], extract: Callable,
                               relative_tolerance: float = 0.10) -> None:
        """Compare already normalized like-for-like values; no live source is duplicated yet."""
        values = [float(extract(item.observation.value)) for item in candidates
                  if item.status is DataStatus.PRESENT]
        if len(values) < 2:
            return
        scale = max(abs(value) for value in values)
        if scale and (max(values) - min(values)) / scale > relative_tolerance:
            raise Conflict("comparable providers disagree beyond the configured tolerance")

    def choose(self, request: DataRequest, candidates: list[DataEnvelope],
               priority: tuple[str, ...],
               policies: tuple[ResolverPolicy, ...] | None = None,
               numeric_extract: Callable | None = None,
               relative_tolerance: float = 0.10) -> DataEnvelope:
        valid = [candidate for candidate in candidates
                 if candidate.status is DataStatus.PRESENT
                 and candidate.observation.visible_as_of(request.as_of)]
        if not valid:
            raise InvalidData("resolver received no valid candidates")
        policies = policies or self.policies
        quality_rank = {"validated": 0, "unverified": 1, "degraded": 2}
        def rank(item):
            parts = []
            for policy in policies:
                if policy is ResolverPolicy.AS_OF_VALID:
                    continue  # invalid candidates were already removed
                if policy is ResolverPolicy.REPORTED_OVER_DERIVED:
                    parts.append(int(item.is_derived))
                elif policy is ResolverPolicy.QUALITY_PRIORITY:
                    parts.append(quality_rank[item.observation.quality.value])
                elif policy is ResolverPolicy.SOURCE_PRIORITY:
                    parts.append(priority.index(item.provider))
            return tuple(parts)
        valid.sort(key=rank)
        chosen = valid[0].model_copy(deep=True)
        chosen.is_fallback = priority.index(chosen.provider) > 0
        if numeric_extract is not None and len(valid) > 1:
            comparable = [item for item in valid if
                          item.observation.unit == chosen.observation.unit and
                          item.observation.observed_date == chosen.observation.observed_date]
            if len(comparable) > 1:
                try:
                    self.check_numeric_conflict(comparable, numeric_extract, relative_tolerance)
                except Conflict:
                    chosen.conflict = True
                    chosen.observation.quality = Quality.DEGRADED
                    chosen.reason = "comparable providers disagree beyond tolerance"
        return chosen


class DataService:
    METHODS = {
        Capability.PRICE_DAILY: "get_price_history",
        Capability.PRICE_ADJUSTED: "get_price_history",
        Capability.VOLUME: "get_price_history",
        Capability.INSTRUMENT_METADATA: "get_company_profile",
        Capability.INDUSTRY: "get_industry",
        Capability.DIVIDEND: "get_dividends",
        Capability.VALUATION_HISTORY: "get_valuation_history",
        Capability.PE: "get_valuation_history",
        Capability.PB: "get_valuation_history",
        Capability.PS: "get_valuation_history",
        Capability.INCOME_STATEMENT: "get_financial_statements",
        Capability.BALANCE_SHEET: "get_financial_statements",
        Capability.CASH_FLOW_STATEMENT: "get_financial_statements",
        Capability.SHARE_CAPITAL: "get_share_capital",
        Capability.NEWS: "get_news",
    }

    def __init__(self, registry: ProviderRegistry | None = None,
                 router: CapabilityRouter | None = None, cache: DataCache | None = None,
                 snapshot_store=None):
        self.registry = registry or current_provider_registry()
        self.router = router or CapabilityRouter()
        self.cache = cache or DataCache()
        self.validator = ValidationLayer()
        self.resolver = Resolver()
        if snapshot_store is None and os.getenv("DATA_SNAPSHOT_DB"):
            from src.data.snapshots import SnapshotStore
            snapshot_store = SnapshotStore(os.environ["DATA_SNAPSHOT_DB"])
        self.snapshot_store = snapshot_store

    def fetch(self, request: DataRequest) -> DataEnvelope:
        snapshot = None
        if (self.snapshot_store is not None and not request.compatibility_mode
                and request.as_of < datetime.now(timezone.utc)):
            snapshot = self.snapshot_store.as_of(request)
        result = snapshot if snapshot is not None else self._fetch_routed(request)
        if (snapshot is None and self.snapshot_store is not None and
                result.status is DataStatus.PRESENT and result.raw_hash):
            self.snapshot_store.save(request, result)
        if result.observation is not None:
            source = result.observation
            logger.debug("data capability=%s provider=%s available_at=%s retrieved_at=%s quality=%s fallback=%s revision=%s",
                         request.capability, result.provider, source.available_at.isoformat(),
                         source.retrieved_at.isoformat(), source.quality, result.is_fallback, source.revision)
        else:
            logger.debug("data capability=%s provider=%s status=%s",
                         request.capability, result.provider, result.status)
        outcomes = _active_outcomes.get()
        if outcomes is not None:
            outcomes[(request.instrument.ticker, request.capability)] = result.model_copy(deep=True)
        return result

    def _fetch_routed(self, request: DataRequest) -> DataEnvelope:
        priorities = self.router.priorities(request)
        if not priorities or request.capability not in self.METHODS:
            return DataEnvelope(status=DataStatus.UNSUPPORTED, provider="router")
        failures = []
        for provider_id in priorities:
            try:
                provider = self.registry.get(provider_id)
            except KeyError:
                continue
            if not provider.supports(request):
                continue
            cached = self.cache.get(provider_id, request)
            if cached is not None:
                result = cached
            else:
                try:
                    method = getattr(provider, self.METHODS[request.capability])
                    result = self.validator.validate(request, method(request))
                except UnsupportedCapability:
                    continue
                except (ProviderFailure, RateLimited, SchemaChanged, OSError, RuntimeError, TimeoutError) as exc:
                    result = DataEnvelope(status=DataStatus.PROVIDER_FAILURE, provider=provider_id,
                                          reason=type(exc).__name__)
                except (InvalidData, ValueError, TypeError) as exc:
                    result = DataEnvelope(status=DataStatus.INVALID_QUALITY, provider=provider_id,
                                          reason=f"{type(exc).__name__}: {exc}")
                self.cache.put(provider_id, request, result)
            if result.status is DataStatus.PRESENT:
                return self.resolver.choose(request, [result], priorities)
            if result.status in (DataStatus.EMPTY_SUCCESS, DataStatus.MISSING,
                                 DataStatus.NOT_PUBLISHED, DataStatus.NOT_AVAILABLE_FOR_DATE):
                return result
            failures.append(result)
        if failures:
            return failures[-1]
        return DataEnvelope(status=DataStatus.UNSUPPORTED, provider="router")

    def get_prices(self, request: DataRequest) -> DataEnvelope:
        return self.fetch(request)

    def get_financial_statements(self, request: DataRequest) -> DataEnvelope:
        return self.fetch(request)

    def get_valuation_history(self, request: DataRequest) -> DataEnvelope:
        result = self.fetch(request)
        if result.status is not DataStatus.PRESENT:
            return result
        from decimal import Decimal

        shares_request = request.model_copy(update={"capability": Capability.SHARE_CAPITAL})
        shares_result = self.get_share_capital(shares_request)
        if shares_result.status is not DataStatus.PRESENT:
            return result
        events = shares_result.observation.value
        for snapshot in result.observation.value:
            prior = [event for event in events if event.effective_date <= snapshot.observed_date
                     and event.available_at <= request.as_of]
            if snapshot.close is None or snapshot.close <= 0 or not prior:
                continue
            event = max(prior, key=lambda item: item.effective_date)
            snapshot.market_cap = snapshot.close * event.total_shares
            snapshot.quality = Quality.DEGRADED if event.quality is Quality.DEGRADED else snapshot.quality
            snapshot.market_cap_inputs = (
                Provenance(provider=snapshot.provider, observed_date=snapshot.observed_date,
                           available_at=snapshot.available_at, retrieved_at=snapshot.retrieved_at,
                           unit=Unit.CNY, quality=Quality.VALIDATED),
                Provenance(provider=event.provider, observed_date=event.effective_date,
                           available_at=event.available_at, retrieved_at=event.retrieved_at,
                           unit=Unit.SHARES, quality=event.quality),
            )
        return result

    def get_company_profile(self, request: DataRequest) -> DataEnvelope:
        return self.fetch(request)

    def get_share_capital(self, request: DataRequest) -> DataEnvelope:
        return self.fetch(request)

    def get_news(self, request: DataRequest) -> DataEnvelope:
        return self.fetch(request)

    @staticmethod
    def availability_report(outcomes: dict[tuple[str, Capability], DataEnvelope]) -> DataAvailabilityReport:
        return DataAvailabilityReport.from_outcomes(outcomes)


_service: DataService | None = None


def get_data_service() -> DataService:
    global _service
    if _service is None:
        _service = DataService()
    return _service
