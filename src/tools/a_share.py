"""BaoStock quotes and AKShare/Sina statements for Shanghai/Shenzhen stocks."""

from datetime import date, timedelta
from threading import RLock
import logging
import math
import re
import warnings
from zoneinfo import ZoneInfo

import pandas as pd

from src.data.models import CompanyNews, FinancialMetrics, LineItem, Price, FinancialReportReference, ReportType
from src.data.ttl import ttl_lru_cache
from src.data.baostock_transport import install_guard

install_guard()


_baostock_lock = RLock()  # BaoStock has a process-wide login connection.
_logger = logging.getLogger(__name__)
_stock_fields = "date,open,high,low,close,volume,peTTM,pbMRQ,psTTM"
_index_fields = "date,open,high,low,close,volume"


def normalize_ticker(ticker: str) -> tuple[str, str, bool]:
    """Return (BaoStock code, Sina code, index flag); reject unsupported markets."""
    value = ticker.strip().lower()
    if value in {"sh.000300", "sh000300"}:
        return "sh.000300", "", True
    match = re.fullmatch(r"(?:(sh|sz)\.?)?(\d{6})", value)
    if not match:
        raise ValueError(f"Unsupported ticker {ticker!r}; use a Shanghai/Shenzhen six-digit A-share code")
    digits = match.group(2)
    market = "sh" if digits.startswith("6") else "sz" if digits.startswith(("0", "3")) else None
    if market is None or (match.group(1) and match.group(1) != market):
        raise ValueError(f"Unsupported A-share ticker {ticker!r}")
    return f"{market}.{digits}", f"{market}{digits}", False


def _number(value):
    try:
        result = float(str(value).replace(",", ""))
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _ratio(numerator, denominator):
    return numerator / denominator if numerator is not None and denominator not in (None, 0) else None


@ttl_lru_cache(maxsize=256, ttl_seconds=6 * 60 * 60)
def _history(code: str, start_date: str, end_date: str) -> tuple[dict, ...]:
    from src.data.adapters import BaoStockProvider
    return BaoStockProvider.fetch_raw_history(code, start_date, end_date)


def get_prices(ticker: str, start_date: str, end_date: str) -> list[Price]:
    code, _, _ = normalize_ticker(ticker)
    prices = []
    for row in _history(code, start_date, end_date):
        values = [_number(row.get(field)) for field in ("open", "close", "high", "low", "volume")]
        if any(value is None for value in values):
            continue
        prices.append(Price(open=values[0], close=values[1], high=values[2],
                            low=values[3], volume=int(values[4]), time=row["date"]))
    return prices


@ttl_lru_cache(maxsize=64, ttl_seconds=24 * 60 * 60)
def _statements(sina_code: str) -> dict[str, pd.DataFrame]:
    from src.data.adapters import AKShareSinaProvider
    return AKShareSinaProvider.fetch_raw_statements(sina_code)


@ttl_lru_cache(maxsize=64, ttl_seconds=24 * 60 * 60)
def _share_history(sina_code: str) -> tuple[tuple[str, float], ...]:
    """AKShare/Eastmoney dated total shares, in individual shares."""
    from src.data.adapters import AKShareEastMoneyProvider
    return AKShareEastMoneyProvider.fetch_raw_share_history(sina_code)


def _available_share_history(ticker: str) -> tuple[tuple[str, float], ...]:
    _, sina_code, index = normalize_ticker(ticker)
    if index:
        return ()
    try:
        from datetime import datetime
        from src.data.capabilities import Capability
        from src.data.compat import request, value_or_raise
        from src.data.pipeline import DataService

        today = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
        events = value_or_raise(
            DataService().get_share_capital(request(Capability.SHARE_CAPITAL, ticker, today)),
            empty=[],
        )
        return tuple((event.effective_date.isoformat(), float(event.total_shares))
                     for event in events)
    except Exception as exc:
        _logger.warning("Dated total shares unavailable for %s (%s)", ticker, type(exc).__name__)
        _logger.debug("Dated share history exception for %s", ticker, exc_info=True)
        return ()


def _shares_as_of(history: tuple[tuple[str, float], ...], as_of_date: str | None) -> float | None:
    if not as_of_date:
        return None
    for changed, shares in reversed(history):
        if changed <= as_of_date:
            return shares
    return None


def _as_date(value):
    if value is None or pd.isna(value):
        return None
    parsed = pd.to_datetime(str(value), errors="coerce")
    return parsed.date().isoformat() if not pd.isna(parsed) else None


def _visible(frame: pd.DataFrame, end_date: str) -> dict[str, pd.Series]:
    """Select only reports whose actual announcement date is no later than end_date."""
    found = {}
    for _, row in frame.iterrows():
        report_date = _as_date(row.get("报告日"))
        announced = _as_date(row.get("公告日期"))
        if report_date and announced and report_date <= end_date and announced <= end_date:
            previous = found.get(report_date)
            if previous is None or announced > _as_date(previous.get("公告日期")):
                found[report_date] = row
    return found


_aliases = {
    "revenue": ("利润表", ("营业收入", "营业总收入")),
    "cost_of_revenue": ("利润表", ("营业成本",)),
    "net_income": ("利润表", ("归属于母公司所有者的净利润", "归属于母公司股东的净利润", "归母净利润")),
    "operating_income": ("利润表", ("营业利润",)),
    "interest_expense": ("利润表", ("利息费用",)),
    "earnings_per_share": ("利润表", ("基本每股收益", "基本每股收益(元/股)")),
    "operating_cash_flow": ("现金流量表", ("经营活动产生的现金流量净额", "经营活动产生的现金流量净额(元)")),
    "capital_expenditure": ("现金流量表", ("购建固定资产、无形资产和其他长期资产所支付的现金", "购建固定资产、无形资产和其他长期资产支付的现金")),
    "depreciation_and_amortization": ("现金流量表", ("固定资产折旧、油气资产折耗、生产性生物资产折旧", "固定资产折旧",)),
    "dividends_and_other_cash_distributions": ("现金流量表", ("分配股利、利润或偿付利息所支付的现金", "分配股利、利润或偿付利息支付的现金")),
    "total_assets": ("资产负债表", ("资产总计",)),
    "total_liabilities": ("资产负债表", ("负债合计",)),
    "shareholders_equity": ("资产负债表", ("归属于母公司股东权益合计", "归属于母公司所有者权益合计", "所有者权益合计")),
    "current_assets": ("资产负债表", ("流动资产合计",)),
    "current_liabilities": ("资产负债表", ("流动负债合计",)),
    "cash_and_equivalents": ("资产负债表", ("货币资金",)),
    "inventory": ("资产负债表", ("存货",)),
    "receivables": ("资产负债表", ("应收账款",)),
    "intangible_assets": ("资产负债表", ("无形资产",)),
    "goodwill": ("资产负债表", ("商誉",)),
    "short_term_debt": ("资产负债表", ("短期借款",)),
    "current_portion_long_term_debt": ("资产负债表", ("一年内到期的非流动负债",)),
    "long_term_debt": ("资产负债表", ("长期借款",)),
    "bonds_payable": ("资产负债表", ("应付债券",)),
}
_flow_fields = {name for name, (statement, _) in _aliases.items() if statement != "资产负债表"}


def _field(reports, report_date: str, name: str):
    statement, aliases = _aliases[name]
    row = reports[statement].get(report_date)
    if row is None:
        return None
    for alias in aliases:
        if alias in row.index:
            value = _number(row.get(alias))
            if value is not None:
                return value
    return None


def _value(reports, report_date: str, name: str, ttm: bool):
    current = _field(reports, report_date, name)
    if current is None or not ttm or name not in _flow_fields or report_date.endswith("12-31"):
        return current
    year = int(report_date[:4]) - 1
    annual = _field(reports, f"{year}-12-31", name)
    prior = _field(reports, f"{year}{report_date[4:]}", name)
    return current + annual - prior if annual is not None and prior is not None else None


def _reports(ticker: str, end_date: str):
    _, sina_code, index = normalize_ticker(ticker)
    if index:
        raise ValueError("The CSI 300 index has prices but no company statements")
    from src.data.capabilities import Capability
    from src.data.compat import request, value_or_raise
    from src.data.pipeline import DataService

    service = DataService()
    reports = {}
    for capability, name in (
        (Capability.BALANCE_SHEET, "资产负债表"),
        (Capability.INCOME_STATEMENT, "利润表"),
        (Capability.CASH_FLOW_STATEMENT, "现金流量表"),
    ):
        normalized = value_or_raise(
            service.get_financial_statements(request(capability, ticker, end_date)),
            empty=[],
        )
        rows = {}
        for statement in normalized:
            report_date = statement.period_end.isoformat()
            row = {"报告日": report_date,
                   "公告日期": statement.available_at.astimezone(
                       ZoneInfo("Asia/Shanghai")).date().isoformat()}
            for field in statement.fields:
                row[_aliases[field.name][1][0]] = float(field.value) if field.value is not None else None
            rows[report_date] = pd.Series(row)
        reports[name] = rows
    return reports


def _periods(reports, period: str, limit: int):
    if period not in ("ttm", "annual"):
        raise ValueError(f"Unsupported financial period: {period}")
    dates = set.intersection(*(set(items) for items in reports.values()))
    if period == "annual":
        dates = {item for item in dates if item.endswith("12-31")}
    return sorted(dates, reverse=True)[:limit]


def _line_values(reports, report_date: str, ttm: bool, shares: float | None = None) -> dict:
    values = {name: _value(reports, report_date, name, ttm) for name in _aliases}
    parts = [values[name] for name in ("short_term_debt", "current_portion_long_term_debt", "long_term_debt", "bonds_payable")]
    values["total_debt"] = sum(part or 0 for part in parts) if any(part is not None for part in parts) else None
    assets, liabilities = values["current_assets"], values["current_liabilities"]
    values["working_capital"] = assets - liabilities if assets is not None and liabilities is not None else None
    ocf, capex = values["operating_cash_flow"], values["capital_expenditure"]
    values["free_cash_flow"] = ocf - abs(capex) if ocf is not None and capex is not None else None
    revenue, cost = values["revenue"], values["cost_of_revenue"]
    values["gross_profit"] = revenue - cost if revenue is not None and cost is not None else None
    operating, depreciation = values["operating_income"], values["depreciation_and_amortization"]
    values["ebit"] = operating
    values["ebitda"] = operating + depreciation if operating is not None and depreciation is not None else None
    equity = values["shareholders_equity"]
    values["outstanding_shares"] = shares
    values["book_value_per_share"] = _ratio(equity, values["outstanding_shares"])
    values["free_cash_flow_per_share"] = _ratio(values["free_cash_flow"], values["outstanding_shares"])
    values["goodwill_and_intangible_assets"] = (
        values["goodwill"] + values["intangible_assets"]
        if values["goodwill"] is not None and values["intangible_assets"] is not None else None
    )
    return values


def _latest_quote(ticker: str, end_date: str) -> dict:
    from src.data.capabilities import Capability
    from src.data.compat import request, value_or_raise
    from src.data.pipeline import DataService

    start = date.fromisoformat(end_date) - timedelta(days=45)
    service = DataService()
    valuations = value_or_raise(
        service.get_valuation_history(request(Capability.VALUATION_HISTORY, ticker, end_date,
                                             start.isoformat())),
        empty=[],
    )
    if not valuations:
        return {}
    latest = max(valuations, key=lambda item: item.observed_date)
    return {"date": latest.observed_date.isoformat(),
            "close": str(latest.close) if latest.close is not None else "",
            "peTTM": str(latest.pe) if latest.pe is not None else "",
            "pbMRQ": str(latest.pb) if latest.pb is not None else "",
            "psTTM": str(latest.ps) if latest.ps is not None else ""}


def _growth(reports, report_date: str, name: str, ttm: bool):
    current = _value(reports, report_date, name, ttm)
    prior = _value(reports, f"{int(report_date[:4]) - 1}{report_date[4:]}", name, ttm)
    return _ratio(current - prior, abs(prior)) if current is not None and prior is not None else None


def _market_cap(quote: dict, shares: float | None) -> float | None:
    close = _number(quote.get("close"))
    return close * shares if close is not None and close > 0 and shares is not None and shares > 0 else None


def get_financial_metrics(ticker: str, end_date: str, period: str = "ttm", limit: int = 10) -> list[FinancialMetrics]:
    reports = _reports(ticker, end_date)
    dates = _periods(reports, period, limit)
    try:
        quote = _latest_quote(ticker, end_date) if dates else {}
    except (OSError, RuntimeError, TimeoutError) as exc:
        _logger.debug("BaoStock valuation exception for %s", ticker, exc_info=True)
        warnings.warn(f"BaoStock valuation unavailable for {ticker}: {exc}", RuntimeWarning, stacklevel=2)
        quote = {}
    share_history = _available_share_history(ticker) if dates else ()
    output = []
    for index, report_date in enumerate(dates):
        values = _line_values(reports, report_date, period == "ttm", _shares_as_of(share_history, report_date))
        previous_equity = _field(reports, f"{int(report_date[:4]) - 1}{report_date[4:]}", "shareholders_equity")
        equity = values["shareholders_equity"]
        average_equity = (equity + previous_equity) / 2 if equity is not None and previous_equity is not None else None
        data = {field: None for field in FinancialMetrics.model_fields}
        data.update(ticker=ticker, report_period=report_date, period=period, currency="CNY",
                    gross_margin=_ratio(values["gross_profit"], values["revenue"]),
                    operating_margin=_ratio(values["operating_income"], values["revenue"]),
                    net_margin=_ratio(values["net_income"], values["revenue"]),
                    return_on_equity=_ratio(values["net_income"], average_equity),
                    return_on_assets=_ratio(values["net_income"], values["total_assets"]),
                    current_ratio=_ratio(values["current_assets"], values["current_liabilities"]),
                    quick_ratio=_ratio(
                        values["current_assets"] - values["inventory"], values["current_liabilities"]
                    ) if values["current_assets"] is not None and values["inventory"] is not None else None,
                    cash_ratio=_ratio(values["cash_and_equivalents"], values["current_liabilities"]),
                    operating_cash_flow_ratio=_ratio(values["operating_cash_flow"], values["current_liabilities"]),
                    debt_to_equity=_ratio(values["total_debt"], equity),
                    debt_to_assets=_ratio(values["total_debt"], values["total_assets"]),
                    interest_coverage=_ratio(values["operating_income"], values["interest_expense"]),
                    revenue_growth=_growth(reports, report_date, "revenue", period == "ttm"),
                    earnings_growth=_growth(reports, report_date, "net_income", period == "ttm"),
                    earnings_per_share_growth=_growth(reports, report_date, "earnings_per_share", period == "ttm"),
                    book_value_growth=_growth(reports, report_date, "shareholders_equity", False),
                    earnings_per_share=values["earnings_per_share"],
                    book_value_per_share=values["book_value_per_share"],
                    free_cash_flow_per_share=values["free_cash_flow_per_share"])
        if index == 0:
            data.update(price_to_earnings_ratio=_number(quote.get("peTTM")),
                        price_to_book_ratio=_number(quote.get("pbMRQ")),
                        price_to_sales_ratio=_number(quote.get("psTTM")),
                        market_cap=_market_cap(quote, _shares_as_of(share_history, quote.get("date"))))
            if data["market_cap"] is not None and values["total_debt"] is not None and values["cash_and_equivalents"] is not None:
                data["enterprise_value"] = data["market_cap"] + values["total_debt"] - values["cash_and_equivalents"]
            data["enterprise_value_to_ebitda_ratio"] = _ratio(data["enterprise_value"], values["ebitda"])
            data["enterprise_value_to_revenue_ratio"] = _ratio(data["enterprise_value"], values["revenue"])
            data["free_cash_flow_yield"] = _ratio(values["free_cash_flow"], data["market_cap"])
            data["peg_ratio"] = _ratio(data["price_to_earnings_ratio"], data["earnings_growth"] * 100) if data["earnings_growth"] and data["earnings_growth"] > 0 else None
        output.append(FinancialMetrics(**data))
    return output


def search_line_items(ticker: str, line_items: list[str], end_date: str, period: str = "ttm", limit: int = 10) -> list[LineItem]:
    reports = _reports(ticker, end_date)
    dates = _periods(reports, period, limit)
    share_history = _available_share_history(ticker) if dates else ()
    output = []
    for report_date in dates:
        values = _line_values(reports, report_date, period == "ttm", _shares_as_of(share_history, report_date))
        selected = {field: values.get(field) for field in line_items}
        output.append(LineItem(ticker=ticker, report_period=report_date, period=period, currency="CNY", **selected))
    return output


def get_market_cap(ticker: str, end_date: str) -> float | None:
    quote = _latest_quote(ticker, end_date)
    return _market_cap(quote, _shares_as_of(_available_share_history(ticker), quote.get("date")))


def get_company_news(ticker: str, end_date: str, start_date: str | None = None, limit: int = 1000) -> list[CompanyNews]:
    """Legacy direct caller uses the same typed news service as src.tools.api."""
    from src.tools.api import get_company_news as service_news
    return service_news(ticker, end_date, start_date, limit)


@ttl_lru_cache(maxsize=128, ttl_seconds=24 * 60 * 60)
def get_financial_report_references(
    ticker: str,
    end_date: str | None = None,
    start_date: str | None = None,
    limit: int = 10,
) -> tuple[FinancialReportReference, ...]:
    """Retrieve official periodic disclosure filings from CNINFO (巨潮资讯) via AKShare."""
    import akshare as ak
    import re
    from datetime import datetime

    # Extract 6-digit A-share code
    digits_match = re.search(r"\d{6}", str(ticker))
    if not digits_match:
        return ()
    code = digits_match.group(0)

    # Format dates to YYYYMMDD
    now_year = datetime.now().year
    s_date = start_date.replace("-", "") if start_date else f"{now_year - 3}0101"
    e_date = end_date.replace("-", "") if end_date else f"{now_year + 1}1231"

    categories = ["年报", "半年报", "一季报", "三季报"]
    collected: list[FinancialReportReference] = []
    seen_ids = set()

    for cat in categories:
        try:
            df = ak.stock_zh_a_disclosure_report_cninfo(
                symbol=code,
                market="沪深京",
                category=cat,
                start_date=s_date,
                end_date=e_date,
            )
            if df is None or df.empty:
                continue

            for _, row in df.iterrows():
                title = str(row.get("公告标题") or "").strip()
                pub_date = str(row.get("公告时间") or "")[:10]
                url = str(row.get("公告链接") or "").strip()
                company_name = str(row.get("简称") or "").strip()

                if not title or not url or not url.startswith(("http://", "https://")):
                    continue
                if "cninfo.com.cn" not in url:
                    continue

                # Parse announcementId from URL query parameters
                announcement_id = None
                org_id = None
                m_ann = re.search(r"announcementId=([0-9a-zA-Z]+)", url)
                if m_ann:
                    announcement_id = m_ann.group(1)
                m_org = re.search(r"orgId=([0-9a-zA-Z]+)", url)
                if m_org:
                    org_id = m_org.group(1)

                if announcement_id and announcement_id in seen_ids:
                    continue
                if announcement_id:
                    seen_ids.add(announcement_id)

                # Filter out summary abstracts to prioritize full text filings
                if "摘要" in title:
                    continue

                # Determine report type in strict priority order
                if "半年度报告" in title or "半年报" in title:
                    r_type = ReportType.SEMI_ANNUAL_REPORT.value
                elif "第一季度报告" in title or "一季报" in title:
                    r_type = ReportType.Q1_REPORT.value
                elif "第三季度报告" in title or "三季报" in title:
                    r_type = ReportType.Q3_REPORT.value
                elif "年度报告" in title or "年报" in title:
                    r_type = ReportType.ANNUAL_REPORT.value
                else:
                    r_type = ReportType.OTHER_REPORT.value

                # Construct reliable static PDF URL if announcementId and pub_date are available
                pdf_url = None
                if announcement_id and pub_date and re.match(r"^\d{4}-\d{2}-\d{2}$", pub_date):
                    pdf_url = f"http://static.cninfo.com.cn/finalpage/{pub_date}/{announcement_id}.PDF"

                source_id = f"CNINFO_{code}_{pub_date}_{announcement_id or len(collected)}"

                ref = FinancialReportReference(
                    source_id=source_id,
                    title=title,
                    report_type=r_type,
                    publish_date=pub_date,
                    ticker=code,
                    company_name=company_name or code,
                    source="CNINFO",
                    source_name="巨潮资讯",
                    source_url=url,
                    pdf_url=pdf_url,
                    announcement_id=announcement_id,
                    org_id=org_id,
                )
                collected.append(ref)
        except Exception as exc:
            _logger.warning("CNINFO report disclosure failed for %s %s: %s", code, cat, exc)

    # Sort descending by publish_date
    collected.sort(key=lambda x: x.publish_date, reverse=True)
    return tuple(collected[:limit])
