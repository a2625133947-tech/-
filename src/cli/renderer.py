"""Rich presentation for the interactive command line."""

from __future__ import annotations

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.cli.presentation import SIGNAL_NAMES
from src.cli.shadow_renderer import (
    _find_shadow_entry,
    render_investor_shadow_card,
    render_shadow_summary_table,
)
from src.data.analysis_result import AgentAnalysis, AnalysisResult, MetricItem


def _field(label: str, value: str) -> Text:
    line = Text()
    line.append(f"{label}  ", style="bold")
    line.append(value)
    return line


def _agent_card(agent: AgentAnalysis) -> Panel:
    summary_header = Table.grid(padding=(0, 2))
    summary_header.add_column(style="bold", no_wrap=True)
    summary_header.add_column()
    summary_header.add_row("Signal", SIGNAL_NAMES.get(agent.signal.lower(), agent.signal))
    summary_header.add_row("Confidence", f"{agent.confidence:.1f}%")

    content: list[object] = [summary_header]

    if agent.key_metrics:
        content.append(Text())
        content.append(Text("关键指标", style="bold"))
        grid = Table.grid(padding=(0, 2))
        grid.add_column(no_wrap=True)
        grid.add_column(no_wrap=True)
        for item in agent.key_metrics:
            if isinstance(item, MetricItem):
                label = item.label
                val_str = item.formatted
            else:
                s = str(item)
                if "：" in s:
                    label, _, val_str = s.partition("：")
                elif ": " in s:
                    label, _, val_str = s.partition(": ")
                else:
                    label, val_str = s, ""
            if val_str:
                grid.add_row(f"  {label}", val_str)
            else:
                grid.add_row(f"  {label}")
        content.append(grid)

    if agent.strengths:
        content.append(Text())
        content.append(Text("优势", style="bold"))
        for s in agent.strengths:
            content.append(Text(f"  • {s}"))

    if agent.risks:
        content.append(Text())
        content.append(Text("风险", style="bold"))
        for r in agent.risks:
            content.append(Text(f"  • {r}"))

    if agent.reasoning:
        content.append(Text())
        content.append(Text("综合分析", style="bold"))
        content.append(Text(f"  {agent.reasoning}"))

    return Panel(Group(*content), title=agent.name, title_align="left", box=box.ROUNDED, padding=(0, 1))


def render_analysis(result: AnalysisResult, console: Console | None = None) -> None:
    """Render one or more stocks without changing the workflow's result."""
    console = console or Console()
    console.print(Text("AI Hedge Fund", style="bold cyan"))

    mode = (getattr(result, "investor_mode", None) or "legacy").lower()
    if mode == "shadow":
        console.print(Text("Research Mode · SHADOW", style="bold yellow"))
        console.print(Text("Production Decision Uses LEGACY", style="yellow"))
    elif mode == "new":
        console.print(Text("Pilot Mode · NEW", style="bold magenta"))
    else:
        console.print(Text("Production Mode · LEGACY", style="dim"))
    console.print()

    if not result.stocks:
        console.print("未生成投资决策。", style="yellow")
        return

    for stock in result.stocks:
        if mode == "shadow":
            console.print(Text("=" * 40, style="dim"))
            console.print(Text(f"{stock.ticker} · {stock.stock_name or 'A股'}", style="bold cyan"))
            console.print(Text("Research Mode · SHADOW", style="yellow"))
            console.print(Text("=" * 40, style="dim"))
            console.print()

            console.print(Text("生产交易决策", style="bold"))
            console.print(Text("LEGACY", style="dim"))
            summary = Table.grid(padding=(0, 2))
            summary.add_column(style="bold", no_wrap=True)
            summary.add_column()
            summary.add_row("Action", stock.action.upper())
            summary.add_row("Confidence", f"{stock.confidence:.1f}%")
            summary.add_row("Quantity", str(stock.quantity))
            console.print(summary)
            console.print()

            if result.progress:
                console.print(Text("分析进度", style="bold"))
                for name, status in result.progress:
                    done = status.lower() == "done"
                    symbol = "✓" if done else "!"
                    line = Text(f"{symbol} {name}", style="green" if done else "yellow")
                    if not done:
                        line.append(f"：{status}")
                    console.print(line)
                console.print()

            if result.show_reasoning and stock.shadow_evaluations:
                console.print(Text("Shadow 投资人研究模型拆解", style="bold cyan"))
                console.print(Text("-" * 40, style="dim"))
                console.print()
                for agent in stock.agents:
                    shadow_entry = _find_shadow_entry(agent.name, stock.shadow_evaluations)
                    if shadow_entry:
                        render_investor_shadow_card(agent.name, shadow_entry, console)
                    else:
                        console.print(_agent_card(agent))
            else:
                if stock.shadow_evaluations:
                    render_shadow_summary_table(stock, console)
                    console.print(Text("💡 提示：使用 --show-reasoning 参数可查看各投资人 New Research Model 因子拆解、门槛逻辑与置信度构成。", style="dim italic"))
                    console.print(Text("💡 提示：使用 --debug-state 参数可导出完整图状态及原始 JSON 数据。\n", style="dim italic"))

                console.print(Text("Agent 分析", style="bold"))
                for agent in stock.agents:
                    console.print(_agent_card(agent))

            console.print(Text("Portfolio Strategy", style="bold"))
            console.print(Text(stock.portfolio_strategy or "未提供"))
            console.print()
        else:
            # Legacy / standard mode
            console.print(_field("股票代码 / 股票名称", f"{stock.ticker} / {stock.stock_name or '未提供'}"))
            console.print()
            console.print(Text("分析进度", style="bold"))
            for name, status in result.progress:
                done = status.lower() == "done"
                symbol = "✓" if done else "!"
                line = Text(f"{symbol} {name}", style="green" if done else "yellow")
                if not done:
                    line.append(f"：{status}")
                console.print(line)
            console.print()
            console.print(Text("最终投资结论", style="bold"))
            summary = Table.grid(padding=(0, 2))
            summary.add_column(style="bold", no_wrap=True)
            summary.add_column()
            summary.add_row("Action", stock.action.upper())
            summary.add_row("Confidence", f"{stock.confidence:.1f}%")
            summary.add_row("Quantity", str(stock.quantity))
            console.print(summary)
            console.print()
            console.print(Text("Agent 分析", style="bold"))
            for agent in stock.agents:
                console.print(_agent_card(agent))
            console.print(Text("Portfolio Strategy", style="bold"))
            console.print(Text(stock.portfolio_strategy or "未提供"))
            console.print()
