"""Human-readable presentation for SHADOW research mode in CLI.

Consumes StrategyEvaluationResult contracts without performing any factor or strategy computation.
"""

from __future__ import annotations

from typing import Any
from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.cli.presentation import SIGNAL_NAMES
from src.data.analysis_result import MetricItem, StockAnalysis
from src.utils.analysts import ANALYST_CONFIG

NAME_TO_KEY: dict[str, str] = {
    cfg.get("display_name", ""): key for key, cfg in ANALYST_CONFIG.items()
}


def _find_shadow_entry(agent_name: str, shadow_evaluations: dict[str, Any]) -> dict[str, Any] | None:
    """Resolve an agent name to its shadow evaluation payload."""
    key = NAME_TO_KEY.get(agent_name)
    candidates = [
        f"{key}_agent" if key else None,
        key,
        agent_name,
        f"{agent_name}_agent",
    ]
    for cand in candidates:
        if cand and cand in shadow_evaluations:
            return shadow_evaluations[cand]
    for k, v in shadow_evaluations.items():
        if key and key in k:
            return v
        if agent_name in k:
            return v
    return None


FACTOR_NAMES_CN: dict[str, str] = {
    "profitability_quality": "盈利质量",
    "cash_conversion": "现金转化",
    "balance_sheet_safety": "资产负债安全",
    "revenue_growth_yoy": "营收同比增长",
    "revenue_cagr_3y": "营收三年复合增长",
    "earnings_growth_yoy": "盈利同比增长",
    "growth_acceleration": "增长加速度",
    "margin_trend": "利润率趋势",
    "valuation_level": "估值水平",
    "valuation_percentile": "PE 估值历史分位",
    "momentum_1m": "近 1 个月动量",
    "momentum_3m": "近 3 个月动量",
    "momentum_6m": "近 6 个月动量",
    "momentum_12m": "近 12 个月动量",
    "drawdown_6m": "近 6 个月最大回撤",
    "volatility_3m": "近 3 个月波动率",
    "low_expectation_proxy": "低预期代理",
}

ROLE_NAMES_CN: dict[str, str] = {
    "core": "CORE (核心因子)",
    "supporting": "SUPPORTING (支撑因子)",
    "optional": "OPTIONAL (辅助因子)",
}

SIGNAL_BADGES: dict[str, str] = {
    "bullish": "↑ 看多 (bullish)",
    "neutral": "— 中性 (neutral)",
    "bearish": "↓ 看空 (bearish)",
}


def _get_factor_display_name(factor_id: str) -> str:
    return FACTOR_NAMES_CN.get(factor_id, factor_id)


def _fmt_val(val: Any, is_float: bool = True) -> str:
    if val is None:
        return "—"
    if is_float and isinstance(val, (int, float)):
        return f"{val:+.3f}" if isinstance(val, float) else f"{val:+d}"
    return str(val)


def _gate_checks_display(gate_id: str | None, gate_passed: bool | None, gate_inputs: dict[str, Any]) -> list[str]:
    checks = []
    if not gate_id:
        return checks

    if gate_id == "low_expectation_proxy_and_operating_improvement":
        proxy = gate_inputs.get("low_expectation_proxy")
        if proxy is not None:
            proxy_ok = float(proxy) > 0
            checks.append(f"{'✓' if proxy_ok else '✗'} 低预期代理{'成立' if proxy_ok else '未成立'} (score: {float(proxy):+.3f})")
        mean_val = gate_inputs.get("operating_improvement_mean")
        if mean_val is not None:
            mf = float(mean_val)
            if mf >= 0.15:
                checks.append(f"✓ 经营改善证据成立 (均值: {mf:+.3f} >= +0.150)")
            elif mf <= -0.20:
                checks.append(f"✗ 经营证据恶化 (均值: {mf:+.3f} <= -0.200)")
            else:
                checks.append(f"✗ 经营改善证据不足 (均值: {mf:+.3f} 未达 +0.150)")
    elif gate_id == "long_term_quality_core_evidence":
        checks.append(f"{'✓' if gate_passed else '✗'} 长期质量核心证据{'充分' if gate_passed else '缺失'}")
    elif gate_id == "growth_quality_not_deteriorating":
        mean_val = gate_inputs.get("growth_evidence_mean")
        if mean_val is not None:
            mf = float(mean_val)
            checks.append(f"{'✓' if gate_passed else '✗'} 成长动能{'未恶化' if gate_passed else '显著恶化'} (均值: {mf:+.3f})")
        else:
            checks.append(f"{'✓' if gate_passed else '✗'} 成长动能门槛检验{'通过' if gate_passed else '未通过'}")
    else:
        checks.append(f"{'✓' if gate_passed else '✗'} 门槛检验{'通过' if gate_passed else '未通过'}")

    return checks


def render_shadow_summary_table(stock: StockAnalysis, console: Console) -> None:
    """Render a concise overview table of all shadow investors when reasoning is not expanded."""
    table = Table(
        title="10 位研究投资人 Legacy vs New 快速对比",
        box=box.ROUNDED,
        header_style="bold cyan",
        title_style="bold",
        padding=(0, 1),
    )
    table.add_column("投资人", style="bold", no_wrap=True)
    table.add_column("Legacy 信号", justify="center")
    table.add_column("Legacy 置信度", justify="right")
    table.add_column("New 信号", justify="center")
    table.add_column("New 置信度", justify="right")
    table.add_column("策略评分", justify="right")
    table.add_column("证据覆盖率", justify="right")
    table.add_column("状态", justify="center")

    for agent in stock.agents:
        shadow = _find_shadow_entry(agent.name, stock.shadow_evaluations)
        if not shadow:
            continue

        legacy = shadow.get("legacy", {})
        new = shadow.get("new", {})
        new_error = shadow.get("new_error")

        leg_sig = SIGNAL_BADGES.get(legacy.get("signal", ""), legacy.get("signal", "—"))
        leg_conf = f"{legacy.get('confidence', 0.0):.1f}%" if "confidence" in legacy else "—"

        if new_error:
            table.add_row(
                agent.name,
                leg_sig,
                leg_conf,
                Text("ERROR", style="bold red"),
                "—",
                "—",
                "—",
                Text("异常", style="red"),
            )
        elif new:
            new_sig = SIGNAL_BADGES.get(new.get("signal", ""), new.get("signal", "—"))
            new_conf = f"{new.get('confidence', 0.0):.1f}%"
            score = new.get("strategy_score")
            score_str = f"{score:+.3f}" if score is not None else "—"
            cov = new.get("data_coverage", {}).get("strategy_evidence_coverage")
            cov_str = f"{cov * 100:.1f}%" if cov is not None else "—"
            changed = shadow.get("signal_changed", False)
            status_text = Text("信号差异", style="yellow") if changed else Text("一致", style="green")

            table.add_row(
                f"{agent.name} {new.get('profile_version', 'v1')}",
                leg_sig,
                leg_conf,
                new_sig,
                new_conf,
                score_str,
                cov_str,
                status_text,
            )

    console.print(table)
    console.print()


def render_investor_shadow_card(
    agent_name: str,
    shadow_data: dict[str, Any],
    console: Console,
) -> None:
    """Render structured human-readable comparison of Legacy vs New Research Model for one investor."""
    legacy = shadow_data.get("legacy", {})
    new = shadow_data.get("new", {})
    new_error = shadow_data.get("new_error")

    # 1. Legacy Section
    leg_sig = legacy.get("signal", "neutral")
    leg_conf = legacy.get("confidence", 0.0)
    leg_content: list[object] = []

    leg_header = Table.grid(padding=(0, 2))
    leg_header.add_column(style="bold", no_wrap=True)
    leg_header.add_column()
    leg_header.add_row("Signal", SIGNAL_BADGES.get(leg_sig.lower(), leg_sig))
    leg_header.add_row("Confidence", f"{leg_conf:.1f}%")
    leg_content.append(leg_header)

    leg_metrics = legacy.get("key_metrics", {})
    if leg_metrics:
        leg_content.append(Text())
        leg_content.append(Text("Legacy Key Metrics", style="bold"))
        grid = Table.grid(padding=(0, 2))
        grid.add_column(no_wrap=True)
        grid.add_column(no_wrap=True)
        for k, m in leg_metrics.items():
            lbl = m.get("label", k) if isinstance(m, dict) else k
            val = m.get("value") if isinstance(m, dict) else m
            grid.add_row(f"  {lbl}", str(val))
        leg_content.append(grid)

    if legacy.get("strengths"):
        leg_content.append(Text())
        leg_content.append(Text("Legacy Strengths", style="bold green"))
        for s in legacy["strengths"]:
            leg_content.append(Text(f"  • {s}"))

    if legacy.get("risks"):
        leg_content.append(Text())
        leg_content.append(Text("Legacy Risks", style="bold red"))
        for r in legacy["risks"]:
            leg_content.append(Text(f"  • {r}"))

    leg_panel = Panel(
        Group(*leg_content),
        title=f"{agent_name} · Legacy",
        title_align="left",
        box=box.ROUNDED,
        padding=(0, 1),
    )
    console.print(leg_panel)

    # 2. New Research Model Section
    if new_error:
        err_panel = Panel(
            Text(f"New Research Model 计算发生异常：{new_error}", style="red"),
            title=f"{agent_name} · New Research Model",
            title_align="left",
            box=box.ROUNDED,
            padding=(0, 1),
        )
        console.print(err_panel)
        console.print()
        return

    new_sig = new.get("signal", "neutral")
    new_conf = new.get("confidence", 0.0)
    score = new.get("strategy_score")
    score_str = f"{score:+.3f}" if score is not None else "—"
    version = new.get("profile_version", "v1")

    new_content: list[object] = []

    # Strategy headline
    new_header = Table.grid(padding=(0, 2))
    new_header.add_column(style="bold", no_wrap=True)
    new_header.add_column()
    new_header.add_row("Signal", SIGNAL_BADGES.get(new_sig.lower(), new_sig))
    new_header.add_row("Confidence", f"{new_conf:.1f}%")
    new_header.add_row("Strategy Score", score_str)
    new_content.append(new_header)

    # Coverage & Quality
    cov = new.get("data_coverage", {})
    new_content.append(Text())
    new_content.append(Text("Coverage & Data Quality", style="bold"))
    cov_grid = Table.grid(padding=(0, 2))
    cov_grid.add_column(no_wrap=True, style="dim")
    cov_grid.add_column(no_wrap=True)
    if "implemented_factor_coverage" in cov:
        cov_grid.add_row("  Implemented Factor Coverage", f"{cov['implemented_factor_coverage'] * 100:.1f}%")
    if "strategy_evidence_coverage" in cov:
        cov_grid.add_row("  Strategy Evidence Coverage", f"{cov['strategy_evidence_coverage'] * 100:.1f}%")
    if "core_coverage" in cov:
        cov_grid.add_row("  CORE Coverage", f"{cov['core_coverage'] * 100:.1f}%")
    if "supporting_coverage" in cov:
        cov_grid.add_row("  Supporting Coverage", f"{cov['supporting_coverage'] * 100:.1f}%")
    cov_grid.add_row("  Data Quality", "HEALTHY")
    new_content.append(cov_grid)

    # 3. Factor Contributions (Grouped by CORE, SUPPORTING, OPTIONAL)
    contributions = new.get("factor_contributions", [])
    if contributions:
        new_content.append(Text())
        new_content.append(Text("Factor Contributions", style="bold cyan"))

        for role_key, role_label in ROLE_NAMES_CN.items():
            role_factors = [fc for fc in contributions if fc.get("role") == role_key]
            if not role_factors:
                continue

            f_table = Table(
                title=f"  {role_label}",
                box=box.SIMPLE,
                header_style="bold",
                padding=(0, 1),
                show_header=True,
            )
            f_table.add_column("因子名称 (Display Name)", style="bold", no_wrap=True)
            f_table.add_column("Score", justify="right")
            f_table.add_column("Weight", justify="right")
            f_table.add_column("Contribution", justify="right")
            f_table.add_column("Status", justify="center")
            f_table.add_column("Raw Value", justify="right")

            for fc in role_factors:
                fid = fc.get("factor_id", "")
                fname = _get_factor_display_name(fid)
                fscore = fc.get("score")
                fscore_str = f"{float(fscore):+.3f}" if fscore is not None else "—"
                fweight = f"{float(fc.get('weight', 0)):.2f}"
                fcontrib = fc.get("weighted_contribution")
                fcontrib_str = f"{float(fcontrib):+.3f}" if fcontrib is not None else "—"
                fstatus = fc.get("status", "AVAILABLE")
                fraw = fc.get("raw_value")
                fraw_str = f"{float(fraw):.3f}" if fraw is not None else "—"

                f_table.add_row(fname, fscore_str, fweight, fcontrib_str, fstatus, fraw_str)

            new_content.append(f_table)

    # 4. Signal Explanation
    exp = new.get("signal_explanation")
    if exp:
        new_content.append(Text())
        new_content.append(Text("判断逻辑 (Signal Explanation)", style="bold yellow"))
        exp_grid = Table.grid(padding=(0, 2))
        exp_grid.add_column(no_wrap=True, style="bold")
        exp_grid.add_column()

        b_th = exp.get("bullish_threshold")
        s_th = exp.get("bearish_threshold")
        th_str = f"Bullish >= {float(b_th):+.3f}, Bearish <= {float(s_th):+.3f}" if b_th is not None else "—"
        exp_grid.add_row("  Signal Threshold", th_str)
        exp_grid.add_row("  Policy Style", exp.get("policy_style", "—"))

        gate_id = exp.get("gate_id")
        gate_passed = exp.get("gate_passed")
        gate_status = "✓ 通过" if gate_passed else "✗ 未通过" if gate_passed is False else "—"
        exp_grid.add_row("  Profile Gate", f"{gate_id or '无'} [{gate_status}]")

        checks = _gate_checks_display(gate_id, gate_passed, exp.get("gate_inputs", {}))
        for check in checks:
            exp_grid.add_row("    Gate Check", check)

        exp_grid.add_row("  Reason Code", exp.get("reason_code", "—"))
        if new.get("signal_reason"):
            exp_grid.add_row("  Signal Reason", new["signal_reason"])

        new_content.append(exp_grid)

    # 5. Confidence Breakdown
    conf_comp = new.get("confidence_components")
    if conf_comp:
        new_content.append(Text())
        new_content.append(Text("置信度拆解 (Confidence Breakdown)", style="bold magenta"))
        c_grid = Table.grid(padding=(0, 2))
        c_grid.add_column(no_wrap=True, style="dim")
        c_grid.add_column(no_wrap=True)

        if "coverage_score" in conf_comp:
            c_grid.add_row("  Evidence Coverage Score", f"{conf_comp['coverage_score'] * 100:.1f}%")
        if "evidence_quality" in conf_comp:
            c_grid.add_row("  Evidence Quality", f"{conf_comp['evidence_quality'] * 100:.1f}%")
        if "strategy_evidence_cap" in conf_comp and conf_comp["strategy_evidence_cap"] is not None:
            c_grid.add_row("  Strategy Evidence Cap", f"{conf_comp['strategy_evidence_cap']:.1f}%")
        if "proxy_cap" in conf_comp and conf_comp["proxy_cap"] is not None:
            c_grid.add_row("  Proxy Cap", f"{conf_comp['proxy_cap']:.1f}%")
        if conf_comp.get("active_cap_name"):
            c_grid.add_row("  Active Cap", f"{conf_comp['active_cap_name']} ({conf_comp.get('active_cap_value', 0):.1f}%)")
        c_grid.add_row("  Final Confidence", f"{new_conf:.1f}%")

        new_content.append(c_grid)
        new_content.append(Text("  注：置信度表示当前策略判断的数据支撑程度，不代表上涨概率或胜率。", style="dim italic"))

    # 6. Known Missing Dimensions
    missing_dims = new.get("known_missing_dimensions", [])
    if missing_dims:
        new_content.append(Text())
        new_content.append(Text("已知模型缺失维度 (非数据源故障，系公开量化模型当前无法观察维度)", style="bold yellow"))
        for dim in missing_dims:
            new_content.append(Text(f"  ⚠ {dim}", style="yellow"))

    # 7. Strengths & Risks
    if new.get("strengths"):
        new_content.append(Text())
        new_content.append(Text("New Model 优势判定", style="bold green"))
        for s in new["strengths"]:
            new_content.append(Text(f"  • {s}"))

    if new.get("risks"):
        new_content.append(Text())
        new_content.append(Text("New Model 风险判定", style="bold red"))
        for r in new["risks"]:
            new_content.append(Text(f"  • {r}"))

    # 8. Legacy vs New Summary
    new_content.append(Text())
    new_content.append(Text("Legacy → New 对照摘要", style="bold"))
    sum_grid = Table.grid(padding=(0, 2))
    sum_grid.add_column(no_wrap=True, style="bold")
    sum_grid.add_column()
    sum_grid.add_row(
        "  Signal",
        f"{SIGNAL_BADGES.get(leg_sig.lower(), leg_sig)} → {SIGNAL_BADGES.get(new_sig.lower(), new_sig)}",
    )
    sum_grid.add_row(
        "  Confidence",
        f"{leg_conf:.1f}% → {new_conf:.1f}%",
    )
    sum_grid.add_row(
        "  核心差异",
        "Legacy 基于离散财务指标硬阈值打分；New 采用连续因子引擎、多维证据覆盖率与策略门槛验证。",
    )
    sum_grid.add_row(
        "  研究声明",
        "仅供策略原型对照研究，不代表模型优劣评判。",
    )
    new_content.append(sum_grid)

    new_panel = Panel(
        Group(*new_content),
        title=f"{agent_name} {version} · New Research Model",
        title_align="left",
        box=box.ROUNDED,
        padding=(0, 1),
    )
    console.print(new_panel)
    console.print()
