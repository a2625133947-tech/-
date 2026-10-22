"""Turn workflow output into a UI-independent analysis result."""

from __future__ import annotations

import re

from src.data.analysis_result import AgentAnalysis, AnalysisResult, MetricItem, StockAnalysis
from src.utils.analysts import ANALYST_CONFIG


SECTION_NAMES = {
    "profitability_signal": "盈利能力", "growth_signal": "增长", "financial_health_signal": "财务健康",
    "price_ratios_signal": "估值", "trend_following": "趋势", "mean_reversion": "均值回归",
    "momentum": "动量", "volatility": "波动", "statistical_arbitrage": "统计套利",
}
METRIC_NAMES = {
    "adx": "ADX", "trend_strength": "趋势强度", "z_score": "Z 分数",
    "price_vs_bb": "布林带位置", "rsi_14": "RSI 14", "rsi_28": "RSI 28",
    "momentum_1m": "近 1 个月动量", "momentum_3m": "近 3 个月动量",
    "momentum_6m": "近 6 个月动量", "volume_momentum": "成交量动量",
    "historical_volatility": "历史波动率", "volatility_regime": "波动状态",
    "volatility_z_score": "波动 Z 分数", "atr_ratio": "ATR 比例",
    "hurst_exponent": "Hurst 指数", "skewness": "偏度", "kurtosis": "峰度",
    "ROE": "净资产收益率", "Net Margin": "净利率", "Op Margin": "营业利润率",
    "Revenue Growth": "营收增长率", "Earnings Growth": "利润增长率",
    "Current Ratio": "流动比率", "D/E": "债务权益比",
    "P/E": "市盈率", "P/B": "市净率", "P/S": "市销率",
    "roe": "ROE", "net_margin": "净利率", "operating_margin": "营业利润率",
    "revenue_growth": "营收增长", "earnings_growth": "盈利增长",
    "fcf_yield": "自由现金流收益率", "six_month_return": "六个月回报",
    "pe": "市盈率", "pb": "市净率", "ps": "市销率", "debt_to_equity": "资产负债率",
    "current_ratio": "流动比率",
}
PERCENT_METRICS = {
    "trend_strength", "price_vs_bb", "momentum_1m", "momentum_3m", "momentum_6m",
    "volume_momentum", "historical_volatility", "volatility_regime", "atr_ratio",
    "revenue_growth", "earnings_growth", "net_margin", "operating_margin",
    "return_on_equity", "free_cash_flow_yield", "fcf_yield", "six_month_return",
    "roe", "percent",
}
SIGNAL_NAMES = {"bullish": "看多", "bearish": "看空", "neutral": "中性"}
SOURCE_NAMES = re.compile(r"BaoStock|AKShare|Eastmoney|Sina|financialdatasets", re.IGNORECASE)


def format_metric(key: str, value: object, format_type: str | None = None) -> str:
    """Format known fractional measures as percentages without changing data."""
    if value is None:
        return "未提供"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if format_type == "percent" or key in PERCENT_METRICS:
            percentage = value * 100
            return f"{0 if abs(percentage) < 0.005 else percentage:.2f}%"
        if format_type == "ratio" or key in {"pe", "pb", "ps", "current_ratio"}:
            if key in {"Current Ratio", "D/E", "P/E", "P/B", "P/S"}:
                return f"{0 if abs(value) < 0.005 else value:.2f} 倍"
            return f"{0 if abs(value) < 0.005 else value:.2f}"
        return f"{0 if abs(value) < 0.005 else value:,.2f}"
    return str(value)


def _details(text: str) -> list[str]:
    items = []
    for part in text.split(", "):
        key, separator, value = part.partition(": ")
        if key in {"Current Ratio", "D/E", "P/E", "P/B", "P/S"} and value not in {"N/A", ""}:
            value += " 倍"
        items.append(f"{METRIC_NAMES.get(key, key)}：{value}" if separator else part)
    return items


def _user_reasoning(reasoning: str) -> str:
    if "数据获取异常：" in reasoning:
        reasoning = re.sub(r" 数据获取异常：.*?(?=；关键指标不足|$)", "；部分数据暂不可用", reasoning)
    if reasoning.lower().startswith(("error in ", "parsing error")):
        return "分析未完成，已采用保守判断。"
    return SOURCE_NAMES.sub("数据服务", reasoning)


def _agent_analysis(agent_id: str, payload: dict) -> AgentAnalysis:
    key = agent_id.removesuffix("_agent")
    name = ANALYST_CONFIG.get(key, {}).get("display_name", key.replace("_", " ").title())
    reasoning = payload.get("reasoning") or ""
    metrics: list[MetricItem] = []
    strengths: list[str] = list(payload.get("strengths") or [])
    risks: list[str] = list(payload.get("risks") or [])

    # 1. Structured key_metrics provided directly in payload
    raw_metrics = payload.get("key_metrics")
    if raw_metrics:
        if isinstance(raw_metrics, dict):
            for m_key, m_val in raw_metrics.items():
                if isinstance(m_val, dict):
                    label = m_val.get("label") or METRIC_NAMES.get(m_key, m_key)
                    val = m_val.get("value")
                    fmt = m_val.get("format")
                    formatted = m_val.get("formatted") or format_metric(fmt or m_key, val, fmt)
                    metrics.append(MetricItem(label=label, value=val, format=fmt, formatted=formatted))
                elif isinstance(m_val, MetricItem):
                    metrics.append(m_val)
                else:
                    label = METRIC_NAMES.get(m_key, m_key)
                    formatted = format_metric(m_key, m_val)
                    metrics.append(MetricItem(label=label, value=m_val, formatted=formatted))
        elif isinstance(raw_metrics, list):
            for item in raw_metrics:
                if isinstance(item, MetricItem):
                    metrics.append(item)
                elif isinstance(item, dict):
                    metrics.append(MetricItem(**item))
                elif isinstance(item, str):
                    if "：" in item:
                        lbl, _, fmtd = item.partition("：")
                    elif ": " in item:
                        lbl, _, fmtd = item.partition(": ")
                    else:
                        lbl, fmtd = item, ""
                    metrics.append(MetricItem(label=lbl, formatted=fmtd))

    has_payload_metrics = bool(raw_metrics)

    # 2. Extract metrics, strengths, risks from structured reasoning dict if key_metrics not present
    if isinstance(reasoning, dict):
        parts = []
        for section_key, section in reasoning.items():
            label = SECTION_NAMES.get(section_key, section_key.replace("_", " "))
            if not isinstance(section, dict):
                if not has_payload_metrics:
                    formatted = format_metric(section_key, section)
                    metrics.append(MetricItem(label=label, value=section, formatted=formatted))
                continue
            if section.get("signal") is not None:
                signal = str(section["signal"]).lower()
                parts.append(f"{label}{SIGNAL_NAMES.get(signal, signal)}")
                if not payload.get("strengths") and signal == "bullish" and label not in strengths:
                    strengths.append(label)
                elif not payload.get("risks") and signal == "bearish" and label not in risks:
                    risks.append(label)
            if not has_payload_metrics:
                if section.get("details"):
                    for detail_item in _details(str(section["details"])):
                        if "：" in detail_item:
                            d_lbl, _, d_fmtd = detail_item.partition("：")
                        elif ": " in detail_item:
                            d_lbl, _, d_fmtd = detail_item.partition(": ")
                        else:
                            d_lbl, d_fmtd = detail_item, ""
                        metrics.append(MetricItem(label=d_lbl, formatted=d_fmtd))
                for metric_key, value in (section.get("metrics") or {}).items():
                    m_label = METRIC_NAMES.get(metric_key, metric_key)
                    formatted = format_metric(metric_key, value)
                    metrics.append(MetricItem(label=m_label, value=value, formatted=formatted))
                for metric_key, value in section.items():
                    if metric_key not in {"signal", "confidence", "details", "metrics"} and not isinstance(value, (dict, list)):
                        m_label = f"{label} · {METRIC_NAMES.get(metric_key, metric_key)}"
                        formatted = format_metric(metric_key, value)
                        metrics.append(MetricItem(label=m_label, value=value, formatted=formatted))
        overall = SIGNAL_NAMES.get(str(payload.get("signal", "")).lower(), str(payload.get("signal", "")))
        reasoning = "分项判断：" + "；".join(parts) if parts else f"总体判断：{overall}；分项指标见上。"

    return AgentAnalysis(
        name=name, signal=str(payload.get("signal", "neutral")),
        confidence=float(payload.get("confidence") or 0), key_metrics=metrics,
        strengths=strengths, risks=risks, reasoning=_user_reasoning(str(reasoning)),
    )


def build_analysis_result(
    raw: dict, statuses: dict[str, str] | None = None,
    stock_names: dict[str, str] | None = None,
    investor_mode: str = "legacy",
    show_reasoning: bool = False,
    debug_state: bool = False,
) -> AnalysisResult:
    """Adapt the existing workflow contract; leave its decisions untouched."""
    stocks = []
    signals = raw.get("analyst_signals") or {}
    shadow_data = raw.get("investor_shadow") or {}
    for ticker, decision in (raw.get("decisions") or {}).items():
        agents = [
            _agent_analysis(agent_id, per_ticker[ticker])
            for agent_id, per_ticker in signals.items()
            if not agent_id.startswith("risk_management_agent") and ticker in per_ticker
        ]
        agents.sort(key=lambda item: next(
            (config["order"] for config in ANALYST_CONFIG.values() if config["display_name"] == item.name), 999
        ))
        ticker_shadow = {
            agent_id: per_ticker[ticker]
            for agent_id, per_ticker in shadow_data.items()
            if ticker in per_ticker
        }
        stocks.append(StockAnalysis(
            ticker=ticker, stock_name=(stock_names or {}).get(ticker),
            action=decision.get("action", "hold"),
            confidence=float(decision.get("confidence") or 0),
            quantity=int(decision.get("quantity") or 0),
            portfolio_strategy=_user_reasoning(str(decision.get("reasoning") or "")),
            agents=agents,
            shadow_evaluations=ticker_shadow,
        ))
    return AnalysisResult(
        stocks=stocks,
        progress=list((statuses or {}).items()),
        investor_mode=investor_mode,
        show_reasoning=show_reasoning,
        debug_state=debug_state,
    )
