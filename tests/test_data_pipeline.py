from datetime import date, datetime, timezone
from decimal import Decimal
import pytest

from src.data.availability import DataAvailabilityReport
from src.data.capabilities import Capability, Market
from src.data.compat import request
from src.data.domain import DataEnvelope, DataStatus, ObservedValue, PriceBar, Quality, Unit
from src.data.errors import Conflict, InvalidData, RateLimited, ProviderFailure, classify_provider_error
from src.data.pipeline import CapabilityRouter, DataCache, DataService, Resolver, ResolverPolicy, ValidationLayer
from src.data.providers import ProviderRegistry
from src.data.ttl import ttl_lru_cache


def _present(provider, data, quality=Quality.VALIDATED):
    return DataEnvelope(status=DataStatus.PRESENT, provider=provider,
                        observation=ObservedValue(
                            value=data, provider=provider, observed_date=date(2026, 9, 24),
                            available_at=datetime(2026, 9, 24, tzinfo=timezone.utc),
                            retrieved_at=datetime(2026, 9, 27, tzinfo=timezone.utc),
                            unit=Unit.CNY, quality=quality))


def test_router_falls_back_after_primary_failure_and_skips_unsupported():
    req = request(Capability.PRICE_DAILY, "600519", "2026-09-25", "2026-09-24")
    bar = PriceBar(instrument=req.instrument, trading_date=date(2026, 9, 24),
                   open=100, high=103, low=99, close=102, volume=1000)

    class FakeProvider:
        capabilities = frozenset({Capability.PRICE_DAILY})

        def __init__(self, provider_id, fail=False, supported=True):
            self.provider_id, self.fail, self.supported = provider_id, fail, supported
            self.calls = 0

        def supports(self, _):
            return self.supported

        def get_price_history(self, _):
            self.calls += 1
            if self.fail:
                raise ProviderFailure("down")
            return _present(self.provider_id, [bar])

    registry = ProviderRegistry()
    unsupported = FakeProvider("unsupported", supported=False)
    primary = FakeProvider("primary", fail=True)
    fallback = FakeProvider("fallback")
    for provider in (unsupported, primary, fallback):
        registry.register(provider)
    routes = {(Market.CN_SH, Capability.PRICE_DAILY, "daily"):
              ("unsupported", "primary", "fallback")}
    service = DataService(registry=registry, router=CapabilityRouter(routes), cache=DataCache())
    result = service.get_prices(req)
    assert result.provider == "fallback" and result.is_fallback
    assert unsupported.calls == 0 and primary.calls == 1 and fallback.calls == 1
    assert service.get_prices(req).provider == "fallback"
    assert primary.calls == 1 and fallback.calls == 1  # failure backoff and success cache


def test_cache_key_ttl_and_failure_backoff():
    now = [0.0]
    cache = DataCache(clock=lambda: now[0])
    req = request(Capability.NEWS, "600519", "2026-09-25")
    success = _present("p", ["headline"])
    cache.put("p", req, success)
    assert cache.get("p", req) is not None
    other_as_of = req.model_copy(update={"as_of": req.as_of.replace(year=2027)})
    assert cache.get("p", other_as_of) is None
    now[0] += 301
    assert cache.get("p", req) is None
    failure = DataEnvelope(status=DataStatus.PROVIDER_FAILURE, provider="p")
    cache.put("p", req, failure)
    now[0] += 4
    assert cache.get("p", req).status is DataStatus.PROVIDER_FAILURE
    now[0] += 2
    assert cache.get("p", req) is None


def test_legacy_raw_cache_expires_and_can_be_cleared():
    now = [0.0]
    calls = []

    @ttl_lru_cache(maxsize=2, ttl_seconds=10, clock=lambda: now[0])
    def fetch(value):
        calls.append(value)
        return value

    assert fetch(1) == fetch(1) == 1 and calls == [1]
    now[0] = 11
    assert fetch(1) == 1 and calls == [1, 1]
    fetch.cache_clear()
    assert fetch(1) == 1 and calls == [1, 1, 1]


def test_resolver_quality_and_reported_priority():
    req = request(Capability.PRICE_DAILY, "600519", "2026-09-25")
    reported = _present("reported", [1], Quality.UNVERIFIED)
    derived = _present("derived", [2], Quality.VALIDATED)
    derived.is_derived = True
    resolver = Resolver()
    assert resolver.choose(req, [derived, reported], ("derived", "reported")).provider == "reported"
    assert resolver.choose(req, [derived, reported], ("derived", "reported"),
                           (ResolverPolicy.QUALITY_PRIORITY, ResolverPolicy.SOURCE_PRIORITY)).provider == "derived"
    with pytest.raises(Conflict):
        resolver.check_numeric_conflict([_present("a", 100), _present("b", 130)], lambda value: value)


def test_rate_limit_classification_does_not_echo_upstream_secret():
    classified = classify_provider_error(RuntimeError("HTTP 429 https://example.com?api_key=secret"))
    assert isinstance(classified, RateLimited)
    assert "secret" not in str(classified)


def test_availability_uses_requested_capabilities_only():
    outcomes = {
        ("600519", Capability.PRICE_DAILY): _present("baostock", [1]),
        ("600519", Capability.SHARE_CAPITAL): _present("akshare_eastmoney", [2], Quality.DEGRADED),
        ("600519", Capability.NEWS): DataEnvelope(status=DataStatus.PROVIDER_FAILURE, provider="akshare_eastmoney"),
        ("600519", Capability.ROIC): DataEnvelope(status=DataStatus.UNSUPPORTED, provider="router"),
    }
    report = DataAvailabilityReport.from_outcomes(outcomes)
    assert report.available_capabilities == [Capability.PRICE_DAILY]
    assert report.partial_capabilities == [Capability.SHARE_CAPITAL]
    assert report.failed_capabilities == [Capability.NEWS]
    assert report.missing_capabilities == [Capability.ROIC]
    assert report.coverage == 0.375


def test_price_validator_rejects_duplicate_dates_and_bad_ohlc():
    import pytest
    from pydantic import ValidationError

    req = request(Capability.PRICE_DAILY, "600519", "2026-09-25", "2026-09-24")
    bar = PriceBar(instrument=req.instrument, trading_date=date(2026, 9, 24),
                   open=100, high=103, low=99, close=102, volume=1000)
    with pytest.raises(InvalidData, match="duplicate"):
        ValidationLayer().validate(req, _present("baostock", [bar, bar]))
    with pytest.raises(ValidationError, match="inconsistent"):
        PriceBar(instrument=req.instrument, trading_date=date(2026, 9, 24),
                 open=100, high=101, low=99, close=102, volume=1000)


def test_rate_limit_and_non_429_classification():
    # HTTP 429 status code in exception message
    err_429 = classify_provider_error(RuntimeError("HTTP 429 Too Many Requests"))
    assert isinstance(err_429, RateLimited)

    # rate limit phrase in exception message
    err_rl = classify_provider_error(RuntimeError("BaoStock API: rate limit exceeded"))
    assert isinstance(err_rl, RateLimited)

    # too many requests phrase in exception message
    err_tmr = classify_provider_error(RuntimeError("upstream rejected: too many requests"))
    assert isinstance(err_tmr, RateLimited)

    # non-429 errors: HTTP 500 internal server error
    err_500 = classify_provider_error(RuntimeError("HTTP 500 Internal Server Error"))
    assert isinstance(err_500, ProviderFailure)
    assert not isinstance(err_500, RateLimited)

    # non-429 errors: network connection failure
    err_conn = classify_provider_error(ConnectionError("connection reset by peer"))
    assert isinstance(err_conn, ProviderFailure)
    assert not isinstance(err_conn, RateLimited)

    # pre-existing ProviderFailure or RateLimited instance preserved
    existing_pf = ProviderFailure("pre-classified provider failure")
    assert classify_provider_error(existing_pf) is existing_pf
    existing_rl = RateLimited("pre-classified rate limit")
    assert classify_provider_error(existing_rl) is existing_rl


def test_data_service_rate_limit_backoff_and_retry():
    req = request(Capability.PRICE_DAILY, "600519", "2026-09-25", "2026-09-24")
    bar = PriceBar(instrument=req.instrument, trading_date=date(2026, 9, 24),
                   open=100, high=103, low=99, close=102, volume=1000)

    clock = [100.0]

    class FlakyRateLimitedProvider:
        provider_id = "flaky_provider"
        capabilities = frozenset({Capability.PRICE_DAILY})

        def __init__(self):
            self.calls = 0

        def supports(self, _):
            return True

        def get_price_history(self, _):
            self.calls += 1
            if self.calls == 1:
                # First attempt fails with rate limit
                raise RateLimited("request limited (HTTP 429)")
            return _present(self.provider_id, [bar])

    registry = ProviderRegistry()
    provider = FlakyRateLimitedProvider()
    registry.register(provider)
    routes = {(Market.CN_SH, Capability.PRICE_DAILY, "daily"): ("flaky_provider",)}
    service = DataService(
        registry=registry,
        router=CapabilityRouter(routes),
        cache=DataCache(clock=lambda: clock[0]),
    )

    # 1. First call fails with RateLimited
    first_result = service.get_prices(req)
    assert first_result.status is DataStatus.PROVIDER_FAILURE
    assert first_result.reason == "RateLimited"
    assert provider.calls == 1

    # 2. Immediate call within backoff window (5s) uses cached failure (waiting behavior)
    clock[0] += 2.0
    cached_result = service.get_prices(req)
    assert cached_result.status is DataStatus.PROVIDER_FAILURE
    assert cached_result.reason == "RateLimited"
    assert provider.calls == 1  # Did not invoke provider again

    # 3. After backoff window expires (> 5s), next call retries the provider
    clock[0] += 4.0  # Total elapsed: 6s > 5s
    retry_result = service.get_prices(req)
    assert retry_result.status is DataStatus.PRESENT
    assert retry_result.observation.value[0].close == Decimal("102")
    assert provider.calls == 2


def test_data_service_non_429_provider_failure():
    req = request(Capability.PRICE_DAILY, "600519", "2026-09-25", "2026-09-24")

    class ServerErrorProvider:
        provider_id = "server_error_provider"
        capabilities = frozenset({Capability.PRICE_DAILY})

        def supports(self, _):
            return True

        def get_price_history(self, _):
            raise ProviderFailure("Internal 500 Error")

    registry = ProviderRegistry()
    registry.register(ServerErrorProvider())
    routes = {(Market.CN_SH, Capability.PRICE_DAILY, "daily"): ("server_error_provider",)}
    service = DataService(
        registry=registry,
        router=CapabilityRouter(routes),
        cache=DataCache(),
    )

    result = service.get_prices(req)
    assert result.status is DataStatus.PROVIDER_FAILURE
    assert result.reason == "ProviderFailure"
