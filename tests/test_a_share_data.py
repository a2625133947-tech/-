"""Source-contract and as-of tests for the A-share data adapter."""

import pandas as pd
import pytest

from src.tools import a_share
from src.tools import api


def _reports():
    dates = ["2024-12-31", "2025-03-31", "2025-12-31", "2026-03-31"]
    announced = ["2025-03-25", "2025-04-25", "2026-03-25", "2026-04-25"]
    balance = pd.DataFrame({
        "报告日": dates, "公告日期": announced,
        "资产总计": [900, 950, 1000, 1100], "负债合计": [400, 420, 450, 480],
        "归属于母公司股东权益合计": [500, 530, 550, 620],
        "流动资产合计": [300, 320, 350, 400], "流动负债合计": [150, 160, 180, 200],
        "短期借款": [50, 50, 60, 70], "货币资金": [100, 105, 110, 120],
    })
    income = pd.DataFrame({
        "报告日": dates, "公告日期": announced,
        "营业收入": [800, 200, 1000, 300], "营业成本": [500, 120, 600, 170],
        "归属于母公司所有者的净利润": [80, 20, 100, 30],
        "营业利润": [100, 25, 130, 38],
        "基本每股收益": [0.8, 0.2, 1.0, 0.3],
    })
    cash = pd.DataFrame({
        "报告日": dates, "公告日期": announced,
        "经营活动产生的现金流量净额": [100, 30, 130, 40],
        "购建固定资产、无形资产和其他长期资产所支付的现金": [40, 5, 50, 10],
    })
    return {"资产负债表": balance, "利润表": income, "现金流量表": cash}


def test_as_of_report_and_ttm_conversion(monkeypatch):
    monkeypatch.setattr(a_share, "_statements", lambda code: _reports())
    monkeypatch.setattr(a_share, "_share_history", lambda code: (
        ("2025-01-01", 100), ("2026-04-10", 120), ("2026-06-01", 130)
    ))
    monkeypatch.setattr(a_share, "_history", lambda code, start, end: ({
        "date": "2026-03-31" if end < "2026-04-25" else "2026-04-30",
        "close": "100", "peTTM": "20", "pbMRQ": "3", "psTTM": "2"
    },))

    before = api.get_financial_metrics("600519", "2026-04-01", limit=1)[0]
    assert before.report_period == "2025-12-31"
    assert before.price_to_earnings_ratio == 20

    after = api.get_financial_metrics("600519", "2026-05-01", limit=1)[0]
    assert after.report_period == "2026-03-31"
    assert after.net_margin == pytest.approx(0.1)  # 110 / 1100
    assert after.current_ratio == pytest.approx(2)
    assert after.market_cap == pytest.approx(12000)  # quote close x dated total shares
    assert api.get_market_cap("600519", "2026-04-01") == pytest.approx(10000)
    items = api.search_line_items(
        "600519", ["revenue", "net_income", "free_cash_flow", "outstanding_shares", "not_available"],
        "2026-05-01", limit=1,
    )[0]
    assert items.revenue == 1100
    assert items.net_income == 110
    assert items.free_cash_flow == 85
    assert items.outstanding_shares == pytest.approx(100)  # shares at report date
    assert items.not_available is None


def test_missing_dated_shares_does_not_fabricate_market_cap(monkeypatch):
    monkeypatch.setattr(a_share, "_statements", lambda code: _reports())
    monkeypatch.setattr(a_share, "_share_history", lambda code: ())
    monkeypatch.setattr(a_share, "_history", lambda *args: ({
        "date": "2026-04-30", "close": "100", "peTTM": "20", "psTTM": "2"
    },))
    metric = api.get_financial_metrics("600519", "2026-05-01", limit=1)[0]
    assert metric.price_to_earnings_ratio == 20
    assert metric.market_cap is None
    assert api.get_market_cap("600519", "2026-05-01") is None


def test_akshare_share_history_contract(monkeypatch):
    import akshare as ak

    requested = []

    def fake_shares(symbol):
        requested.append(symbol)
        return pd.DataFrame({
            "变更日期": ["2026-04-10", "2025-01-01", "2026-06-01"],
            "总股本": [120, 100, 130],
        })

    monkeypatch.setattr(ak, "stock_zh_a_gbjg_em", fake_shares)
    a_share._share_history.cache_clear()
    history = a_share._share_history("sh600519")
    assert requested == ["600519.SH"]
    assert a_share._shares_as_of(history, "2026-04-01") == 100
    assert a_share._shares_as_of(history, "2026-05-01") == 120
    assert a_share._shares_as_of(history, "2024-12-31") is None


def test_baostock_price_and_index_contract(monkeypatch):
    import baostock as bs

    requested = []

    class Result:
        error_code = "0"
        fields = ["date", "open", "high", "low", "close", "volume", "peTTM", "pbMRQ", "psTTM"]

        def __init__(self):
            self.remaining = 1

        def next(self):
            if self.remaining:
                self.remaining -= 1
                return True
            return False

        def get_row_data(self):
            return ["2026-04-30", "100", "104", "99", "103", "1234", "20", "3", "2"]

    monkeypatch.setattr(bs, "login", lambda: type("Login", (), {"error_code": "0"})())
    monkeypatch.setattr(bs, "logout", lambda: None)

    def query(code, fields, **kwargs):
        requested.append((code, fields, kwargs))
        result = Result()
        result.fields = fields.split(",")
        return result

    monkeypatch.setattr(bs, "query_history_k_data_plus", query)
    a_share._history.cache_clear()
    prices = api.get_prices("600519", "2026-04-01", "2026-04-30")
    assert prices[0].close == 103
    assert requested[0][0] == "sh.600519"
    assert "peTTM" in requested[0][1]
    api.get_prices("sh.000300", "2026-04-01", "2026-04-30")
    assert requested[1][0] == "sh.000300"
    assert "peTTM" not in requested[1][1]


def test_financial_reports_remain_available_when_baostock_is_down(monkeypatch):
    monkeypatch.setattr(a_share, "_statements", lambda code: _reports())

    def disconnected(*args):
        raise RuntimeError("BaoStock login failed")

    monkeypatch.setattr(a_share, "_history", disconnected)
    with pytest.warns(RuntimeWarning, match="BaoStock valuation unavailable"):
        metrics = api.get_financial_metrics("600519", "2026-05-01", limit=1)
    assert metrics[0].report_period == "2026-03-31"
    assert metrics[0].net_margin == pytest.approx(0.1)
    assert metrics[0].price_to_earnings_ratio is None
    assert metrics[0].market_cap is None


def test_unsupported_ticker_is_explicit():
    with pytest.raises(ValueError, match="Unsupported ticker"):
        api.get_prices("AAPL", "2026-01-01", "2026-02-01")
    assert api.get_insider_trades("600519", "2026-05-01") == []


def test_a_share_investors_metrics_and_strengths_risks_deterministic():
    from src.agents.a_share_investors import PROFILES, _build_key_metrics, _build_strengths_and_risks

    raw = {
        "roe": 0.332451,
        "net_margin": 0.478595,
        "revenue_growth": -0.046006,
        "earnings_growth": -0.094529,
        "fcf_yield": 0.075487,
        "debt_to_equity": 0.000276,
        "pe": 20.03677,
        "pb": 7.550987,
        "six_month_return": -0.128873,
    }
    scores = {
        "profitability": 1.0,
        "revenue_growth": 0.0,
        "earnings_growth": -1.0,
        "cash_flow": 1.0,
        "balance_sheet": 1.0,
        "valuation": -0.5,
        "momentum": -1.0,
    }

    # Liu Yanchun test
    lyc_profile = PROFILES["liu_yanchun"]
    lyc_metrics = _build_key_metrics(lyc_profile, raw)
    lyc_strengths, lyc_risks = _build_strengths_and_risks(lyc_profile, scores)

    # 6 metrics for Liu Yanchun
    assert list(lyc_metrics.keys()) == ["roe", "net_margin", "fcf_yield", "revenue_growth", "earnings_growth", "six_month_return"]
    assert lyc_metrics["roe"]["value"] == 0.332451
    assert lyc_metrics["roe"]["format"] == "percent"
    assert lyc_metrics["net_margin"]["value"] == 0.478595

    # Strengths and risks
    assert lyc_strengths == ["盈利质量较强", "自由现金流表现良好", "资产负债表稳健"]
    assert lyc_risks == ["盈利增长承压", "当前估值吸引力有限", "近期价格动量偏弱"]

    # Fu Pengbo test (includes valuation: pe, pb)
    fpb_profile = PROFILES["fu_pengbo"]
    fpb_metrics = _build_key_metrics(fpb_profile, raw)
    assert "pe" in fpb_metrics
    assert "pb" in fpb_metrics
