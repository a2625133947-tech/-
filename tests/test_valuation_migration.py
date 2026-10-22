from decimal import Decimal

from src.data.capabilities import Capability
from src.data.compat import request
from src.data.domain import DataStatus, Quality
from src.data.pipeline import DataService
from src.tools import a_share


def test_valuation_series_and_market_cap_inputs(monkeypatch):
    monkeypatch.setattr(a_share, "_history", lambda *_: (
        {"date": "2026-04-29", "open": "98", "high": "101", "low": "97",
         "close": "100", "volume": "1000", "peTTM": "-2", "pbMRQ": "", "psTTM": "3"},
        {"date": "2026-04-30", "open": "100", "high": "104", "low": "99",
         "close": "103", "volume": "1200", "peTTM": "20", "pbMRQ": "3", "psTTM": "2"},
    ))
    monkeypatch.setattr(a_share, "_share_history", lambda _: (("2026-04-10", 120),))
    result = DataService().get_valuation_history(
        request(Capability.VALUATION_HISTORY, "600519", "2026-05-01", "2026-04-01"))
    assert result.status is DataStatus.PRESENT
    earlier, latest = result.observation.value
    assert earlier.pe == Decimal("-2")  # Recorded value, never labelled cheap by the data layer.
    assert earlier.pb is None
    assert latest.pe == Decimal("20")
    assert latest.market_cap == Decimal("12360")
    assert [(x.provider, x.observed_date.isoformat()) for x in latest.market_cap_inputs] == [
        ("baostock", "2026-04-30"), ("akshare_eastmoney", "2026-04-10")]
    assert latest.quality is Quality.DEGRADED
    assert a_share._latest_quote("600519", "2026-05-01")["peTTM"] == "20.0"
