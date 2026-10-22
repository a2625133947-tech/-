"""Borderless Rich output for the legacy backtest row contract."""

from __future__ import annotations

import re

from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text


ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _plain(value: object) -> str:
    return ANSI.sub("", str(value))


def render_backtest(rows: list, console: Console | None = None) -> None:
    console = console or Console()
    summaries = [row for row in rows if len(row) > 1 and "PORTFOLIO SUMMARY" in _plain(row[1])]
    ticker_rows = [row for row in rows if row not in summaries]
    if summaries:
        last = max(summaries, key=lambda row: row[0])
        console.print(Text("回测组合摘要", style="bold cyan"))
        fields = [
            ("现金", 8), ("持仓市值", 7), ("组合总值", 9), ("收益率", 10),
            ("夏普比率", 11), ("Sortino 比率", 12), ("最大回撤", 13), ("基准收益率", 14),
        ]
        for label, index in fields:
            if len(last) > index and last[index]:
                console.print(f"{label}：{_plain(last[index])}")
        console.print()
    table = Table(box=None, show_edge=False, expand=False)
    for header in ("日期", "股票", "动作", "数量", "价格", "多头股数", "空头股数", "持仓市值"):
        table.add_column(header, overflow="fold")
    for row in ticker_rows:
        table.add_row(*(_plain(value) for value in row[:8]))
    if ticker_rows:
        console.print(table)
