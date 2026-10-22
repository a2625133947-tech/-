"""Optional stock labels for presentation; never used by analysis."""

from __future__ import annotations

from datetime import datetime
import logging
from zoneinfo import ZoneInfo

from src.data.capabilities import Capability
from src.data.compat import request
from src.data.domain import DataStatus
from src.data.pipeline import DataService

logger = logging.getLogger(__name__)


def stock_names(tickers: list[str]) -> dict[str, str]:
    """Resolve labels through DataService; failures remain optional to the CLI."""
    service = DataService()
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    names = {}
    for ticker in tickers:
        try:
            result = service.get_company_profile(request(Capability.INSTRUMENT_METADATA, ticker, today))
        except ValueError:
            logger.debug("Invalid ticker for optional label: %s", ticker, exc_info=True)
            continue
        if result.status is DataStatus.PRESENT:
            names[ticker] = result.observation.value.name
        elif result.status is DataStatus.PROVIDER_FAILURE:
            logger.debug("Optional stock-name provider failed for %s: %s", ticker, result.reason)
        else:
            logger.debug("Optional stock-name unavailable for %s: %s", ticker, result.status)
    return names
