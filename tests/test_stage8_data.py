from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.data.adapters import BaoStockProvider
from src.data.capabilities import Capability
from src.data.compat import request
from src.data.domain import Adjustment, DataEnvelope, DataStatus, NewsItem, ObservedValue, Quality, Unit
from src.data.pipeline import DataService
from src.data.snapshots import SnapshotStore


def _adjusted_rows():
    raw = ({"date": "2025-06-25", "open": "100", "high": "102", "low": "99", "close": "101", "volume": "1000"},
           {"date": "2025-06-26", "open": "97", "high": "99", "low": "96", "close": "98", "volume": "1100"})
    adjusted = ({**raw[0], "open": "98", "high": "99.96", "low": "97.02", "close": "98.98"}, raw[1])
    factors = ({"dividOperateDate": "2025-06-26", "foreAdjustFactor": "1.0", "backAdjustFactor": "1.02"},)
    return raw, adjusted, factors


def test_adjusted_price_keeps_raw_price_factor_and_cache(monkeypatch):
    calls = []
    def fake_fetch(*args):
        calls.append(args)
        return _adjusted_rows()
    monkeypatch.setattr(BaoStockProvider, "fetch_raw_adjusted", fake_fetch)
    req = request(Capability.PRICE_ADJUSTED, "600519", "2025-06-26", "2025-06-25")
    req.adjustment = Adjustment.FORWARD
    req.as_of = datetime.now(timezone.utc) + timedelta(minutes=5)
    req.compatibility_mode = False
    service = DataService()
    first = service.get_prices(req)
    second = service.get_prices(req)
    assert first.status is second.status is DataStatus.PRESENT
    assert len(calls) == 1 and calls[0][-1] == "2"
    bar = first.observation.value[0]
    assert bar.close == Decimal("98.98")
    assert bar.raw_close == Decimal("101")
    assert bar.adjustment_factor == Decimal("0.98")
    assert first.observation.value[1].source_factor_date == date(2025, 6, 26)
    assert first.observation.quality is Quality.DEGRADED
    assert first.raw_hash and len(first.raw_hash) == 64


def test_historical_adjusted_request_without_snapshot_is_explicitly_unavailable(monkeypatch):
    monkeypatch.setattr(BaoStockProvider, "fetch_raw_adjusted", lambda *_: (_ for _ in ()).throw(AssertionError("must not fetch")))
    req = request(Capability.PRICE_ADJUSTED, "600519", "2025-06-26", "2025-06-25", compatibility_mode=False)
    req.adjustment = Adjustment.BACKWARD
    assert DataService().get_prices(req).status is DataStatus.NOT_AVAILABLE_FOR_DATE


def test_dividend_final_value_is_not_visible_before_ex_date(monkeypatch):
    import baostock as bs

    fields = ["dividPlanAnnounceDate", "dividOperateDate", "dividCashPsBeforeTax", "dividStocksPs"]
    row = ["2025-04-03", "2025-06-26", "27.673", "0"]
    class Result:
        error_code = "0"
        def __init__(self): self.fields, self.done = fields, False
        def next(self):
            if self.done: return False
            self.done = True
            return True
        def get_row_data(self): return row
    monkeypatch.setattr(bs, "login", lambda: SimpleNamespace(error_code="0"))
    monkeypatch.setattr(bs, "logout", lambda: None)
    monkeypatch.setattr(bs, "query_dividend_data", lambda *_, **__: Result())
    req = request(Capability.DIVIDEND, "600519", "2025-06-26", "2025-06-20")
    assert DataService().fetch(req).status is DataStatus.EMPTY_SUCCESS
    req = request(Capability.DIVIDEND, "600519", "2025-06-27", "2025-06-20")
    result = DataService().fetch(req)
    assert result.status is DataStatus.PRESENT
    assert result.observation.value[0].cash_per_share == Decimal("27.673")
    assert result.observation.value[0].available_at.date() == date(2025, 6, 26)  # UTC conversion
    req.compatibility_mode = False
    assert DataService().fetch(req).status is DataStatus.NOT_AVAILABLE_FOR_DATE


def test_industry_current_only_and_provider_failure(monkeypatch):
    import baostock as bs
    class Result:
        error_code = "0"
        fields = ["code", "code_name", "industry", "updateDate"]
        done = False
        def next(self):
            if self.done: return False
            self.done = True
            return True
        def get_row_data(self): return ["sh.600519", "贵州茅台", "C15酒、饮料和精制茶制造业", "2026-09-21"]
    monkeypatch.setattr(bs, "login", lambda: SimpleNamespace(error_code="0"))
    monkeypatch.setattr(bs, "logout", lambda: None)
    monkeypatch.setattr(bs, "query_stock_industry", lambda **_: Result())
    req = request(Capability.INDUSTRY, "600519", "2026-09-27", compatibility_mode=False)
    req.as_of = datetime.now(timezone.utc) + timedelta(minutes=5)
    service = DataService()
    assert service.fetch(req).observation.value.industry.startswith("C15")
    assert service.fetch(req).raw_hash  # cache retains source provenance
    past = req.model_copy(update={"as_of": datetime(2026, 9, 20, tzinfo=timezone.utc),
                                  "end_date": date(2026, 9, 20)})
    assert service.fetch(past).status is DataStatus.NOT_AVAILABLE_FOR_DATE
    monkeypatch.setattr(bs, "login", lambda: SimpleNamespace(error_code="100"))
    assert DataService().fetch(req).status is DataStatus.PROVIDER_FAILURE


def test_snapshot_round_trip_and_capture_time_gate(tmp_path):
    store = SnapshotStore(tmp_path / "snapshots.sqlite3")
    req = request(Capability.NEWS, "600519", "2026-09-27")
    captured = datetime(2026, 9, 27, 10, tzinfo=timezone.utc)
    article = NewsItem(instrument=req.instrument, title="测试消息",
                       published_at=captured - timedelta(hours=2), source="example")
    envelope = DataEnvelope(status=DataStatus.PRESENT, provider="akshare_eastmoney", raw_hash="a" * 64,
        observation=ObservedValue(value=[article], provider="akshare_eastmoney",
            observed_date=date(2026, 9, 27), available_at=article.published_at,
            retrieved_at=captured, unit=Unit.NONE))
    store.save(req, envelope)
    store.save(req, envelope)
    assert store.count() == 1
    earlier = req.model_copy(update={"as_of": captured - timedelta(seconds=1)})
    later = req.model_copy(update={"as_of": captured + timedelta(seconds=1)})
    assert store.as_of(earlier) is None
    restored = store.as_of(later)
    assert restored.observation.value[0].title == "测试消息"
    assert restored.raw_hash == "a" * 64
    assert restored.observation.retrieved_at == captured
    later_article = NewsItem(instrument=req.instrument, title="下一条消息",
                            published_at=captured + timedelta(minutes=30))
    next_capture = captured + timedelta(hours=1)
    store.save(req, DataEnvelope(status=DataStatus.PRESENT, provider="akshare_eastmoney",
        raw_hash="c" * 64, observation=ObservedValue(value=[later_article],
            provider="akshare_eastmoney", observed_date=date(2026, 9, 27),
            available_at=later_article.published_at, retrieved_at=next_capture,
            unit=Unit.NONE)))
    merged = store.as_of(req.model_copy(update={"as_of": next_capture + timedelta(seconds=1)}))
    assert {item.title for item in merged.observation.value} == {"测试消息", "下一条消息"}
    assert merged.is_derived and merged.raw_hash is None


def test_data_service_reuses_historical_snapshot_without_calling_provider(tmp_path):
    from src.data.capabilities import Market
    from src.data.pipeline import CapabilityRouter
    from src.data.providers import ProviderRegistry

    captured = datetime(2026, 9, 26, 10, tzinfo=timezone.utc)
    req = request(Capability.NEWS, "600519", "2026-09-27", compatibility_mode=False)
    req.as_of = datetime(2026, 9, 27, 15, tzinfo=timezone.utc)
    article = NewsItem(instrument=req.instrument, title="当时已知",
                       published_at=captured - timedelta(hours=2))
    class Provider:
        provider_id = "fixture"
        capabilities = frozenset({Capability.NEWS})
        calls = 0
        def supports(self, _): return True
        def get_news(self, _):
            self.calls += 1
            return DataEnvelope(status=DataStatus.PRESENT, provider=self.provider_id,
                raw_hash="b" * 64, observation=ObservedValue(value=[article],
                    provider=self.provider_id, observed_date=date(2026, 9, 26),
                    available_at=article.published_at, retrieved_at=captured,
                    unit=Unit.NONE))
    provider = Provider()
    registry = ProviderRegistry()
    registry.register(provider)
    route = CapabilityRouter({(Market.CN_SH, Capability.NEWS, "daily"): ("fixture",)})
    store = SnapshotStore(tmp_path / "news.sqlite3")
    service = DataService(registry=registry, router=route, snapshot_store=store)
    assert service.fetch(req).status is DataStatus.PRESENT
    assert store.count() == 1
    historical = req.model_copy(update={"as_of": captured + timedelta(hours=1)})
    assert service.fetch(historical).observation.value[0].title == "当时已知"
    assert provider.calls == 1


def test_real_source_unit_normalization_and_conflict_marker():
    """2026-09-24 BaoStock and Sina values; EastMoney volume is in lots."""
    from src.data.pipeline import Resolver
    req = request(Capability.PRICE_DAILY, "600519", "2026-09-24")
    observed = date(2026, 9, 24)
    def candidate(provider, close, unit=Unit.CNY, day=observed):
        return DataEnvelope(status=DataStatus.PRESENT, provider=provider,
            observation=ObservedValue(value=Decimal(close), provider=provider,
                observed_date=day, available_at=datetime(2026, 9, 24, tzinfo=timezone.utc),
                retrieved_at=datetime(2026, 9, 27, tzinfo=timezone.utc),
                unit=unit, quality=Quality.VALIDATED))
    baostock = candidate("baostock", "1237.00")
    sina = candidate("sina", "1237.00")
    chosen = Resolver().choose(req, [sina, baostock], ("baostock", "sina"),
                               numeric_extract=lambda value: value)
    assert chosen.provider == "baostock" and not chosen.conflict
    divergent = candidate("sina", "1300.00")
    chosen = Resolver().choose(req, [baostock, divergent], ("baostock", "sina"),
                               numeric_extract=lambda value: value, relative_tolerance=0.01)
    assert chosen.conflict and chosen.observation.quality is Quality.DEGRADED
    # A share count must be converted from lots before numeric comparison.
    incompatible = candidate("sina", "123700", Unit.SHARES)
    chosen = Resolver().choose(req, [baostock, incompatible], ("baostock", "sina"),
                               numeric_extract=lambda value: value)
    assert not chosen.conflict


def test_snapshot_never_mixes_adjustment_or_requested_range(tmp_path):
    from src.data.domain import PriceBar
    store = SnapshotStore(tmp_path / "prices.sqlite3")
    req = request(Capability.PRICE_ADJUSTED, "600519", "2026-09-24", "2026-09-23")
    req.adjustment = Adjustment.FORWARD
    captured = datetime(2026, 9, 25, tzinfo=timezone.utc)
    bar = PriceBar(instrument=req.instrument, trading_date=date(2026, 9, 24),
                   open=100, high=102, low=99, close=101, volume=1000,
                   adjustment=Adjustment.FORWARD, raw_open=110, raw_high=112,
                   raw_low=109, raw_close=111, adjustment_factor=Decimal(101) / 111)
    store.save(req, DataEnvelope(status=DataStatus.PRESENT, provider="baostock",
        raw_hash="d" * 64, observation=ObservedValue(value=[bar], provider="baostock",
            observed_date=date(2026, 9, 24), available_at=captured,
            retrieved_at=captured, unit=Unit.CNY)))
    as_of = captured + timedelta(days=2)
    assert store.as_of(req.model_copy(update={"as_of": as_of})).observation.value[0].adjustment is Adjustment.FORWARD
    backward = req.model_copy(update={"as_of": as_of, "adjustment": Adjustment.BACKWARD})
    different_range = req.model_copy(update={"as_of": as_of, "start_date": date(2026, 9, 20)})
    assert store.as_of(backward) is None
    assert store.as_of(different_range) is None


def test_adjusted_price_handles_blank_volume_for_600438_and_688347(monkeypatch):
    from src.data.domain import PriceBar

    for ticker in ("600438", "688347"):
        raw = (
            {"date": "2026-02-24", "open": "18.0", "high": "18.5", "low": "17.9", "close": "18.16", "volume": "50000"},
            {"date": "2026-02-25", "open": "18.16", "high": "18.16", "low": "18.16", "close": "18.16", "volume": ""},
        )
        adjusted = (
            {"date": "2026-02-24", "open": "180.0", "high": "185.0", "low": "179.0", "close": "181.6", "volume": "50000"},
            {"date": "2026-02-25", "open": "181.6", "high": "181.6", "low": "181.6", "close": "181.6", "volume": ""},
        )
        factors = ({"dividOperateDate": "2026-01-01", "foreAdjustFactor": "1.0", "backAdjustFactor": "10.0"},)

        monkeypatch.setattr(BaoStockProvider, "fetch_raw_adjusted", lambda *_: (raw, adjusted, factors))
        req = request(Capability.PRICE_ADJUSTED, ticker, "2026-02-25", "2026-02-24")
        req.adjustment = Adjustment.BACKWARD
        req.as_of = datetime.now(timezone.utc) + timedelta(minutes=5)
        req.compatibility_mode = False

        envelope = DataService().get_prices(req)
        assert envelope.status is DataStatus.PRESENT
        assert envelope.observation.quality is Quality.DEGRADED
        assert "volume missing" in (envelope.reason or "")
        bars = envelope.observation.value
        assert len(bars) == 2
        # Normal bar has valid Decimal volume
        assert bars[0].volume == Decimal("50000")
        # Blank volume bar is None (never converted to 0)
        assert bars[1].volume is None
        assert bars[1].volume != Decimal("0")
        assert bars[1].close == Decimal("181.6")


def test_adjusted_price_rejects_malformed_non_empty_volume(monkeypatch):
    from src.data.errors import InvalidData

    raw = ({"date": "2026-02-25", "open": "18.16", "high": "18.16", "low": "18.16", "close": "18.16", "volume": "corrupted_text"},)
    adjusted = ({"date": "2026-02-25", "open": "181.6", "high": "181.6", "low": "181.6", "close": "181.6", "volume": "corrupted_text"},)
    factors = ()

    monkeypatch.setattr(BaoStockProvider, "fetch_raw_adjusted", lambda *_: (raw, adjusted, factors))
    req = request(Capability.PRICE_ADJUSTED, "600438", "2026-02-25", "2026-02-25")
    req.adjustment = Adjustment.BACKWARD
    req.as_of = datetime.now(timezone.utc) + timedelta(minutes=5)
    req.compatibility_mode = False

    with pytest.raises(InvalidData, match="invalid volume in raw source"):
        BaoStockProvider().get_adjusted_history(req)

    envelope = DataService().get_prices(req)
    assert envelope.status is DataStatus.INVALID_QUALITY
    assert "InvalidData: invalid volume in raw source" in (envelope.reason or "")
