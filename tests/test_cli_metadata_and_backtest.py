"""Presentation lookups and backtest output do not affect trading calculations."""

from io import StringIO
from types import SimpleNamespace

from rich.cells import cell_len
from rich.console import Console

from src.cli.backtest_renderer import render_backtest
from src.cli.metadata import stock_names


def test_stock_name_lookup_is_optional(monkeypatch):
    import baostock

    monkeypatch.setattr(baostock, "login", lambda: SimpleNamespace(error_code="0"))
    monkeypatch.setattr(baostock, "logout", lambda: None)
    monkeypatch.setattr(baostock, "query_stock_basic", lambda **_kwargs: SimpleNamespace(
        error_code="0", fields=["code", "code_name"],
        next=lambda: True, get_row_data=lambda: ["sh.600519", "贵州茅台"],
    ))
    assert stock_names(["600519"]) == {"600519": "贵州茅台"}

    monkeypatch.setattr(baostock, "login", lambda: SimpleNamespace(error_code="1"))
    assert stock_names(["600519"]) == {}


def test_backtest_render_has_no_ascii_grid_at_common_widths():
    rows = [["2025-09-25", "600519", "BUY", "13", "1439.00", "13", "0", "18707.00"]]
    for width in (80, 120, 160):
        stream = StringIO()
        render_backtest(rows, Console(file=stream, width=width, force_terminal=False))
        output = stream.getvalue()
        assert "600519" in output
        assert "+---" not in output
        assert all(cell_len(line) <= width for line in output.splitlines())


def test_cli_debug_state_flag(monkeypatch):
    import sys
    from src.cli.input import parse_cli_inputs

    monkeypatch.setattr(sys, "argv", ["main.py", "--tickers", "600519", "--debug-state", "--analysts-all"])
    monkeypatch.setattr("src.cli.input.select_model", lambda _o, _m: ("gpt-4o", "OpenAI"))
    inputs = parse_cli_inputs(
        description="test",
        require_tickers=True,
        default_months_back=3,
        include_reasoning_flag=True,
    )
    assert inputs.debug_state is True
    assert inputs.tickers == ["600519"]
