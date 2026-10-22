from types import SimpleNamespace

from src.cli.metadata import stock_names
from src.data.capabilities import Capability
from src.data.compat import request
from src.data.domain import DataStatus
from src.data.pipeline import DataService


def test_metadata_present_missing_and_failure(monkeypatch):
    import baostock as bs

    monkeypatch.setattr(bs, "login", lambda: SimpleNamespace(error_code="0"))
    monkeypatch.setattr(bs, "logout", lambda: None)
    monkeypatch.setattr(bs, "query_stock_basic", lambda **_: SimpleNamespace(
        error_code="0", fields=["code_name"], next=lambda: True,
        get_row_data=lambda: ["贵州茅台"]))
    assert stock_names(["600519"]) == {"600519": "贵州茅台"}

    monkeypatch.setattr(bs, "query_stock_basic", lambda **_: SimpleNamespace(
        error_code="0", next=lambda: False))
    missing = DataService().get_company_profile(request(Capability.INSTRUMENT_METADATA, "600519", "2026-09-27"))
    assert missing.status is DataStatus.MISSING

    monkeypatch.setattr(bs, "login", lambda: SimpleNamespace(error_code="1"))
    failed = DataService().get_company_profile(request(Capability.INSTRUMENT_METADATA, "600519", "2026-09-27"))
    assert failed.status is DataStatus.PROVIDER_FAILURE
    assert stock_names(["600519"]) == {}
