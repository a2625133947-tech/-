from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.data.capabilities import AccessTier, Availability, Capability, Market
from src.data.domain import (
    DataEnvelope, DataStatus, Instrument, ObservedValue, PriceBar, Provenance, Quality, Unit,
    percent_to_fraction,
)
from src.data.inventory import current_a_share_inventory
from src.data.providers import DataProvider, DataRequest, ProviderDescriptor, ProviderRegistry, current_provider_registry


UTC = timezone.utc
STOCK = Instrument(ticker="600519", market=Market.CN_SH, currency=Unit.CNY)


def request(capability=Capability.PRICE_DAILY, market=Market.CN_SH):
    instrument = STOCK.model_copy(update={"market": market})
    return DataRequest(capability=capability, instrument=instrument,
                       as_of=datetime(2026, 9, 25, tzinfo=UTC))


def observation():
    return ObservedValue[Decimal](
        value=Decimal("0.332451"), provider="akshare_sina", period="2026-06-30",
        available_at=datetime(2026, 8, 1, tzinfo=UTC),
        retrieved_at=datetime(2026, 9, 25, tzinfo=UTC),
        unit=Unit.FRACTION, quality=Quality.VALIDATED, revision="1",
    )


def test_inventory_separates_availability_and_access_tier():
    rows = {entry.capability: entry for entry in current_a_share_inventory()}
    assert set(rows) == set(Capability)
    assert rows[Capability.PRICE_DAILY].availability is Availability.AVAILABLE
    assert rows[Capability.PRICE_DAILY].access_tier is AccessTier.FREE
    assert rows[Capability.ROIC].availability is Availability.UNAVAILABLE
    assert rows[Capability.ROIC].access_tier is AccessTier.UNKNOWN
    assert rows[Capability.MARKET_CAP].availability is Availability.PARTIAL


def test_provider_support_is_capability_and_market_specific():
    registry = current_provider_registry()
    assert isinstance(registry.get("baostock"), DataProvider)
    assert [p.provider_id for p in registry.supporting(request())] == ["baostock"]
    assert [p.provider_id for p in registry.supporting(request(Capability.INCOME_STATEMENT))] == ["akshare_sina"]
    assert registry.supporting(request(Capability.PRICE_INTRADAY)) == ()
    assert registry.supporting(request(market=Market.US)) == ()


def test_registry_rejects_duplicate_and_invalid_provider():
    registry = ProviderRegistry()
    provider = ProviderDescriptor(provider_id="sample", capabilities=frozenset({Capability.NEWS}),
                                  markets=frozenset({Market.CN_SH}), access_tier=AccessTier.FREE)
    registry.register(provider)
    assert registry.get("sample") is provider
    with pytest.raises(ValueError, match="unique"):
        registry.register(provider)
    with pytest.raises(TypeError):
        registry.register(object())


def test_observed_value_keeps_provenance_and_publication_time():
    value = observation()
    assert isinstance(value, Provenance)
    assert value.value == Decimal("0.332451")
    assert value.provider == "akshare_sina"
    assert value.period == "2026-06-30"
    assert value.unit is Unit.FRACTION
    assert value.quality is Quality.VALIDATED
    assert value.revision == "1"
    assert value.visible_as_of(datetime(2026, 8, 1, tzinfo=UTC))
    assert not value.visible_as_of(datetime(2026, 7, 31, tzinfo=UTC))


def test_as_of_hides_future_observation():
    envelope = DataEnvelope[Decimal](status=DataStatus.PRESENT, observation=observation(),
                                     provider="akshare_sina")
    hidden = envelope.as_of(datetime(2026, 7, 31, tzinfo=UTC))
    assert hidden.status is DataStatus.NOT_PUBLISHED
    assert hidden.observation is None
    assert envelope.as_of(datetime(2026, 8, 1, tzinfo=UTC)).observation == observation()
    with pytest.raises(ValueError, match="timezone"):
        envelope.as_of(datetime(2026, 8, 1))


def test_absence_failure_unsupported_and_invalid_quality_are_distinct():
    statuses = (DataStatus.MISSING, DataStatus.PROVIDER_FAILURE,
                DataStatus.UNSUPPORTED, DataStatus.NOT_PUBLISHED,
                DataStatus.INVALID_QUALITY)
    assert len(set(statuses)) == 5
    for status in statuses:
        envelope = DataEnvelope[Decimal](status=status, provider="baostock", reason="test")
        assert envelope.observation is None
        assert envelope.status is status
    with pytest.raises(ValidationError):
        DataEnvelope[Decimal](status=DataStatus.PRESENT, provider="baostock")
    with pytest.raises(ValidationError):
        DataEnvelope[Decimal](status=DataStatus.MISSING, provider="akshare_sina",
                              observation=observation())


def test_time_and_unit_contracts():
    assert percent_to_fraction("33.2451") == Decimal("0.332451")
    assert percent_to_fraction("-4.6006") == Decimal("-0.046006")
    with pytest.raises(ValidationError, match="timezone"):
        ObservedValue[Decimal](value=Decimal("1"), provider="p", observed_date=date(2026, 8, 1),
                               available_at=datetime(2026, 8, 1),
                               retrieved_at=datetime(2026, 8, 2, tzinfo=UTC), unit=Unit.CNY)
    with pytest.raises(ValidationError):
        ObservedValue[Decimal](value=Decimal("NaN"), provider="p", observed_date=date(2026, 8, 1),
                               available_at=datetime(2026, 8, 1, tzinfo=UTC),
                               retrieved_at=datetime(2026, 8, 2, tzinfo=UTC), unit=Unit.CNY)


def test_price_bar_basic_validation():
    kwargs = dict(instrument=STOCK, trading_date=date(2026, 9, 25),
                  open="100", high="103", low="99", close="102", volume="1000")
    assert PriceBar(**kwargs).volume == Decimal("1000")
    with pytest.raises(ValidationError, match="inconsistent"):
        PriceBar(**{**kwargs, "high": "101"})
