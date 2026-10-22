from datetime import datetime, timezone

import pandas as pd

from src.data.capabilities import Capability
from src.data.compat import request
from src.data.domain import DataStatus, Unit
from src.data.pipeline import DataService
from src.tools import a_share, api


def _frame():
    return pd.DataFrame({
        "报告日": ["2025-12-31", "2026-03-31"],
        "公告日期": ["2026-03-25", "2026-04-25"],
        "营业收入": [1000, 300],
        "归属于母公司所有者的净利润": [100, 30],
    })


def test_financial_as_of_and_missing_field(monkeypatch):
    monkeypatch.setattr(a_share, "_statements", lambda _: {"利润表": _frame()})
    service = DataService()
    before = service.get_financial_statements(
        request(Capability.INCOME_STATEMENT, "600519", "2026-04-01"))
    assert before.status is DataStatus.PRESENT
    assert [s.period_end.isoformat() for s in before.observation.value] == ["2025-12-31"]
    assert before.observation.value[0].available_at.date().isoformat() == "2026-03-24"  # UTC conversion
    fields = {field.name: field for field in before.observation.value[0].fields}
    assert fields["revenue"].value == 1000
    assert fields["revenue"].unit is Unit.CNY
    assert fields["cost_of_revenue"].value is None
    after = service.get_financial_statements(
        request(Capability.INCOME_STATEMENT, "600519", "2026-05-01"))
    assert [s.period_end.isoformat() for s in after.observation.value][-1] == "2026-03-31"
    too_early = service.get_financial_statements(
        request(Capability.INCOME_STATEMENT, "600519", "2026-01-01"))
    assert too_early.status is DataStatus.NOT_PUBLISHED


def test_financial_provider_failure_is_not_missing(monkeypatch):
    monkeypatch.setattr(a_share, "_statements", lambda _: (_ for _ in ()).throw(RuntimeError("down")))
    result = DataService().get_financial_statements(
        request(Capability.INCOME_STATEMENT, "600519", "2026-05-01"))
    assert result.status is DataStatus.PROVIDER_FAILURE
