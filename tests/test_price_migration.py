import json
from pathlib import Path

from src.data.capabilities import Capability
from src.data.domain import Adjustment, DataStatus
from src.data.pipeline import get_data_service
from src.tools import a_share, api
from src.data.compat import request

BASELINE = json.loads((Path(__file__).resolve().parents[1] / "docs/baselines/stage1_600519_before.json").read_text())


def test_600519_prices_match_every_saved_row(monkeypatch):
    expected = BASELINE["prices"]["data"]
    rows = tuple({"date": item["time"], **{key: str(item[key]) for key in
                 ("open", "high", "low", "close", "volume")}} for item in expected)
    monkeypatch.setattr(a_share, "_history", lambda *_args: rows)
    get_data_service().cache.clear()
    actual = [item.model_dump() for item in api.get_prices("600519", "2026-03-25", "2026-09-25")]
    assert len(actual) == 127
    assert actual == expected
    envelope = get_data_service().get_prices(request(Capability.PRICE_DAILY, "600519",
                                                     "2026-09-25", "2026-03-25"))
    assert envelope.status is DataStatus.PRESENT
    assert all(item.adjustment is Adjustment.UNADJUSTED for item in envelope.observation.value)
    assert envelope.provider == "baostock"
