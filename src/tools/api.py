"""Market data adapter for Shanghai and Shenzhen A shares.

Prices and valuation multiples come from BaoStock. Financial statements come
from AKShare's Sina endpoint.
"""

import pandas as pd

from src.data.models import CompanyNews, FinancialMetrics, InsiderTrade, LineItem, Price, FinancialReportReference
from src.tools import a_share
from src.data.capabilities import Capability
from src.data.compat import request, value_or_raise
from src.data.pipeline import get_data_service


def get_prices(ticker: str, start_date: str, end_date: str, api_key: str = None) -> list[Price]:
    """Return unadjusted daily bars from BaoStock (legacy api_key is ignored)."""
    envelope = get_data_service().get_prices(request(Capability.PRICE_DAILY, ticker, end_date, start_date))
    bars = value_or_raise(envelope, empty=[])
    return [Price(open=float(bar.open), close=float(bar.close), high=float(bar.high),
                  low=float(bar.low), volume=int(bar.volume) if bar.volume is not None else 0, time=bar.trading_date.isoformat())
            for bar in bars]


def get_financial_metrics(
    ticker: str, end_date: str, period: str = "ttm", limit: int = 10, api_key: str = None
) -> list[FinancialMetrics]:
    return a_share.get_financial_metrics(ticker, end_date, period, limit)


def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[LineItem]:
    return a_share.search_line_items(ticker, line_items, end_date, period, limit)


def get_market_cap(ticker: str, end_date: str, api_key: str = None) -> float | None:
    return a_share.get_market_cap(ticker, end_date)


def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[CompanyNews]:
    import logging
    from src.data.domain import DataStatus

    result = get_data_service().get_news(request(Capability.NEWS, ticker, end_date, start_date))
    if result.status is DataStatus.PRESENT:
        return [CompanyNews(ticker=ticker, title=item.title, author="",
                            source=item.source or "", date=item.published_at.date().isoformat(),
                            url=item.url or "")
                for item in result.observation.value[:limit]]
    if result.status is not DataStatus.EMPTY_SUCCESS:
        logging.getLogger(__name__).debug("News unavailable for %s: %s %s",
                                          ticker, result.status, result.reason)
    # The legacy list-returning facade preserves optional-news behavior.
    return []


def get_company_news_result(ticker: str, end_date: str, start_date: str | None = None):
    """Typed news result for callers that need to distinguish empty and failure."""
    return get_data_service().get_news(request(Capability.NEWS, ticker, end_date, start_date,
                                               compatibility_mode=False))


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[InsiderTrade]:
    """No comparable historical insider transaction feed in the selected APIs."""
    a_share.normalize_ticker(ticker)
    return []


def prices_to_df(prices: list[Price]) -> pd.DataFrame:
    df = pd.DataFrame([p.model_dump() for p in prices], columns=["open", "close", "high", "low", "volume", "time"])
    df["Date"] = pd.to_datetime(df["time"])
    df.set_index("Date", inplace=True)
    for column in ("open", "close", "high", "low", "volume"):
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df.sort_index()


def get_price_data(ticker: str, start_date: str, end_date: str, api_key: str = None) -> pd.DataFrame:
    return prices_to_df(get_prices(ticker, start_date, end_date))


def get_financial_report_references(
    ticker: str, end_date: str | None = None, start_date: str | None = None, limit: int = 10
) -> list[FinancialReportReference]:
    """Retrieve official periodic disclosure filings from CNINFO (巨潮资讯)."""
    return list(a_share.get_financial_report_references(ticker, end_date, start_date, limit))


def get_latest_financial_report_reference(ticker: str, end_date: str | None = None) -> FinancialReportReference | None:
    """Retrieve the most recent periodic disclosure filing from CNINFO."""
    refs = a_share.get_financial_report_references(ticker, end_date, limit=1)
    return refs[0] if refs else None
