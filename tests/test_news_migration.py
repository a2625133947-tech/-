import pandas as pd

from src.data.capabilities import Capability
from src.data.compat import request
from src.data.domain import DataStatus
from src.data.pipeline import DataService, get_data_service
from src.tools import api


def test_news_empty_failure_and_historical_limit(monkeypatch):
    import akshare as ak

    monkeypatch.setattr(ak, "stock_news_em", lambda **_: pd.DataFrame())
    empty = DataService().get_news(request(Capability.NEWS, "600519", "2026-09-25"))
    assert empty.status is DataStatus.EMPTY_SUCCESS

    monkeypatch.setattr(ak, "stock_news_em", lambda **_: (_ for _ in ()).throw(RuntimeError("down")))
    failed = DataService().get_news(request(Capability.NEWS, "600519", "2026-09-25"))
    assert failed.status is DataStatus.PROVIDER_FAILURE
    assert api.get_company_news("600519", "2026-09-25") == []  # legacy list contract

    strict = api.get_company_news_result("600519", "2020-01-01")
    assert strict.status is DataStatus.NOT_AVAILABLE_FOR_DATE


def test_news_legacy_shape_and_date_filter(monkeypatch):
    import akshare as ak

    monkeypatch.setattr(ak, "stock_news_em", lambda **_: pd.DataFrame({
        "发布时间": ["2026-09-25 11:30:00", "2026-09-26 09:00:00"],
        "新闻标题": ["A", "B"], "文章来源": ["东方财富", "东方财富"],
        "新闻链接": ["https://example.com/a", "https://example.com/b"],
    }))
    get_data_service().cache.clear()
    rows = api.get_company_news("600519", "2026-09-25")
    assert [item.title for item in rows] == ["A"]
    assert rows[0].date == "2026-09-25"
