"""Legacy return shapes over the new data service."""

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from src.data.capabilities import Capability, Market
from src.data.domain import DataStatus, Instrument, Unit
from src.data.providers import DataRequest
from src.tools import a_share

SHANGHAI = ZoneInfo("Asia/Shanghai")


def request(capability: Capability, ticker: str, end_date: str,
            start_date: str | None = None, *, compatibility_mode: bool = True) -> DataRequest:
    code, _, _ = a_share.normalize_ticker(ticker)
    end = date.fromisoformat(end_date)
    return DataRequest(
        capability=capability,
        instrument=Instrument(ticker=ticker, market=Market.CN_SH if code.startswith("sh.") else Market.CN_SZ,
                              currency=Unit.CNY),
        start_date=date.fromisoformat(start_date) if start_date else None,
        end_date=end,
        as_of=datetime.combine(end, time.max, SHANGHAI).astimezone(timezone.utc),
        compatibility_mode=compatibility_mode,
    )


def value_or_raise(envelope, *, empty=None):
    if envelope.status is DataStatus.PRESENT:
        return envelope.observation.value
    if envelope.status in (DataStatus.EMPTY_SUCCESS, DataStatus.MISSING):
        return empty
    raise RuntimeError(f"Data service {envelope.status}: {envelope.reason or envelope.provider}")
