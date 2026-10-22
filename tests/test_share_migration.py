from datetime import datetime, timezone

from src.data.capabilities import Capability
from src.data.compat import request
from src.data.domain import DataStatus, Quality
from src.data.pipeline import DataService
from src.tools import a_share


def test_share_history_compatibility_and_strict_as_of(monkeypatch):
    monkeypatch.setattr(a_share, "_share_history", lambda _: (
        ("2025-01-01", 100.0), ("2026-04-10", 120.0)))
    assert a_share._available_share_history("600519") == (
        ("2025-01-01", 100.0), ("2026-04-10", 120.0))
    strict = DataService().get_share_capital(
        request(Capability.SHARE_CAPITAL, "600519", "2026-05-01", compatibility_mode=False))
    assert strict.status is DataStatus.NOT_PUBLISHED
    legacy = DataService().get_share_capital(
        request(Capability.SHARE_CAPITAL, "600519", "2026-05-01"))
    assert legacy.status is DataStatus.PRESENT
    assert legacy.observation.quality is Quality.DEGRADED
    assert [event.total_shares for event in legacy.observation.value] == [100, 120]


def test_share_provider_failure_is_typed(monkeypatch):
    monkeypatch.setattr(a_share, "_share_history", lambda _: (_ for _ in ()).throw(RuntimeError("down")))
    result = DataService().get_share_capital(request(Capability.SHARE_CAPITAL, "600519", "2026-05-01"))
    assert result.status is DataStatus.PROVIDER_FAILURE
