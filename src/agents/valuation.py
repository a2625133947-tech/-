from __future__ import annotations

"""Valuation Agent

Implements four complementary valuation methodologies and aggregates them with
configurable weights. 
"""

import json
import statistics
from langchain_core.messages import HumanMessage
from src.graph.state import AgentState, show_agent_reasoning
from src.utils.progress import progress
from src.tools.api import (
    get_financial_metrics,
    search_line_items,
    get_financial_report_references,
    get_latest_financial_report_reference,
)

def valuation_analyst_agent(state: AgentState, agent_id: str = "valuation_analyst_agent"):
    """Run valuation across tickers and write signals back to `state`."""

    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]

    valuation_analysis: dict[str, dict] = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching financial data")

        # --- Historical financial metrics ---
        financial_metrics = get_financial_metrics(
            ticker=ticker,
            end_date=end_date,
            period="ttm",
            limit=8,

        )
        if not financial_metrics:
            progress.update_status(agent_id, ticker, "Failed: No financial metrics found")
            valuation_analysis[ticker] = {
                "signal": "insufficient_evidence",
                "confidence": 0.0,
                "summary": f"标的 {ticker} 缺失历史财务数据，当前数据不足以支持可靠 DCF 与估值模型测算。",
                "narrative": {"conclusion": "数据不足：无可用财务比率与报表历史。"},
                "key_findings": ["缺少现金流与报表数据，无法构建估值模型"],
                "evidence": [],
                "bull_case": [],
                "bear_case": [],
                "risks": ["无法评估当前价格相较内在价值的安全边际"],
                "data_quality": {"status": "insufficient", "source": "BaoStock / AKShare", "limitations": ["财务指标缺失"]},
                "key_metrics": {},
                "strengths": [],
                "reasoning": "缺失历史财务数据，当前数据不足以支持可靠估值测算。",
                "_raw_reasoning": {}
            }
            continue
        most_recent_metrics = financial_metrics[0]
        market_cap = most_recent_metrics.market_cap
        if market_cap is None or market_cap <= 0:
            progress.update_status(agent_id, ticker, "Skipped: Dated market cap unavailable")
            valuation_analysis[ticker] = {
                "signal": "insufficient_evidence",
                "confidence": 0.0,
                "summary": f"标的 {ticker} 缺失对应日期的总市值数据，无法评估估值折溢价空间。",
                "narrative": {"conclusion": "数据不足：总市值不可用。"},
                "key_findings": ["缺少总市值数据"],
                "evidence": [],
                "bull_case": [],
                "bear_case": [],
                "risks": ["无市值基准，无法计算价格偏离度"],
                "data_quality": {"status": "insufficient", "source": "AKShare", "limitations": ["总市值未获取到"]},
                "key_metrics": {},
                "strengths": [],
                "reasoning": "缺失对应日期的总市值数据，无法评估估值折溢价空间。",
                "_raw_reasoning": {}
            }
            continue

        # --- Enhanced line‑items ---
        progress.update_status(agent_id, ticker, "Gathering comprehensive line items")
        line_items = search_line_items(
            ticker=ticker,
            line_items=[
                "free_cash_flow",
                "net_income",
                "depreciation_and_amortization",
                "capital_expenditure",
                "working_capital",
                "total_debt",
                "cash_and_equivalents", 
                "interest_expense",
                "revenue",
                "operating_income",
                "ebit",
                "ebitda"
            ],
            end_date=end_date,
            period="ttm",
            limit=8,

        )
        if len(line_items) < 2:
            progress.update_status(agent_id, ticker, "Failed: Insufficient financial line items")
            valuation_analysis[ticker] = {
                "signal": "insufficient_evidence",
                "confidence": 0.0,
                "summary": f"标的 {ticker} 财务三大表明细行项目不足两期，当前数据不足以支持可靠 DCF 与估值模型测算。",
                "narrative": {"conclusion": "数据不足：自由现金流或资产负债表期数过少。"},
                "key_findings": ["缺少连续财务报表明细项"],
                "evidence": [],
                "bull_case": [],
                "bear_case": [],
                "risks": ["无法构建跨期折现模型"],
                "data_quality": {"status": "insufficient", "source": "AKShare (Sina)", "limitations": ["报表期数不足2期"]},
                "key_metrics": {},
                "strengths": [],
                "reasoning": "财务三大表明细行项目不足两期，当前数据不足以支持可靠 DCF 与估值模型测算。",
                "_raw_reasoning": {}
            }
            continue
        li_curr, li_prev = line_items[0], line_items[1]

        # ------------------------------------------------------------------
        # Valuation models
        # ------------------------------------------------------------------
        # Handle potential None values for working capital
        if li_curr.working_capital is not None and li_prev.working_capital is not None:
            wc_change = li_curr.working_capital - li_prev.working_capital
        else:
            wc_change = 0  # Default to 0 if working capital data is unavailable

        # Owner Earnings
        owner_val = calculate_owner_earnings_value(
            net_income=li_curr.net_income,
            depreciation=li_curr.depreciation_and_amortization,
            capex=li_curr.capital_expenditure,
            working_capital_change=wc_change,
            growth_rate=most_recent_metrics.earnings_growth or 0.05,
        )

        # Enhanced Discounted Cash Flow with WACC and scenarios
        progress.update_status(agent_id, ticker, "Calculating WACC and enhanced DCF")
        
        # Calculate WACC
        wacc = calculate_wacc(
            market_cap=market_cap,
            total_debt=getattr(li_curr, 'total_debt', None),
            cash=getattr(li_curr, 'cash_and_equivalents', None),
            interest_coverage=most_recent_metrics.interest_coverage,
            debt_to_equity=most_recent_metrics.debt_to_equity,
        )
        
        # Prepare FCF history for enhanced DCF
        fcf_history = []
        for li in line_items:
            if hasattr(li, 'free_cash_flow') and li.free_cash_flow is not None:
                fcf_history.append(li.free_cash_flow)
        
        # Enhanced DCF with scenarios
        dcf_results = calculate_dcf_scenarios(
            fcf_history=fcf_history,
            growth_metrics={
                'revenue_growth': most_recent_metrics.revenue_growth,
                'fcf_growth': most_recent_metrics.free_cash_flow_growth,
                'earnings_growth': most_recent_metrics.earnings_growth
            },
            wacc=wacc,
            market_cap=market_cap,
            revenue_growth=most_recent_metrics.revenue_growth
        )
        
        dcf_val = dcf_results['expected_value']

        # Implied Equity Value
        ev_ebitda_val = calculate_ev_ebitda_value(financial_metrics)

        # Residual Income Model
        rim_val = calculate_residual_income_value(
            market_cap=market_cap,
            net_income=li_curr.net_income,
            price_to_book_ratio=most_recent_metrics.price_to_book_ratio,
            book_value_growth=most_recent_metrics.book_value_growth or 0.03,
        )

        # ------------------------------------------------------------------
        # Aggregate & signal
        # ------------------------------------------------------------------
        method_values = {
            "dcf": {"value": dcf_val, "weight": 0.35},
            "owner_earnings": {"value": owner_val, "weight": 0.35},
            "ev_ebitda": {"value": ev_ebitda_val, "weight": 0.20},
            "residual_income": {"value": rim_val, "weight": 0.10},
        }

        total_weight = sum(v["weight"] for v in method_values.values() if v["value"] > 0)
        if total_weight == 0:
            progress.update_status(agent_id, ticker, "Failed: All valuation methods zero")
            continue

        for v in method_values.values():
            v["gap"] = (v["value"] - market_cap) / market_cap if v["value"] > 0 else None

        weighted_gap = sum(
            v["weight"] * v["gap"] for v in method_values.values() if v["gap"] is not None
        ) / total_weight

        signal = "bullish" if weighted_gap > 0.15 else "bearish" if weighted_gap < -0.15 else "neutral"
        confidence = round(min(abs(weighted_gap) / 0.30 * 100, 100))

        # Enhanced reasoning with DCF scenario details
        reasoning = {}
        for m, vals in method_values.items():
            if vals["value"] > 0:
                base_details = (
                    f"Value: ¥{vals['value']:,.2f}, Market Cap: ¥{market_cap:,.2f}, "
                    f"Gap: {vals['gap']:.1%}, Weight: {vals['weight']*100:.0f}%"
                )
                
                # Add enhanced DCF details
                if m == "dcf" and 'dcf_results' in locals():
                    enhanced_details = (
                        f"{base_details}\n"
                        f"  WACC: {wacc:.1%}, Bear: ¥{dcf_results['downside']:,.2f}, "
                        f"Bull: ¥{dcf_results['upside']:,.2f}, Range: ¥{dcf_results['range']:,.2f}"
                    )
                else:
                    enhanced_details = base_details
                
                reasoning[f"{m}_analysis"] = {
                    "signal": (
                        "bullish" if vals["gap"] and vals["gap"] > 0.15 else
                        "bearish" if vals["gap"] and vals["gap"] < -0.15 else "neutral"
                    ),
                    "details": enhanced_details,
                }
        
        # Add overall DCF scenario summary if available
        if 'dcf_results' in locals():
            reasoning["dcf_scenario_analysis"] = {
                "bear_case": f"${dcf_results['downside']:,.2f}",
                "base_case": f"${dcf_results['scenarios']['base']:,.2f}",  
                "bull_case": f"${dcf_results['upside']:,.2f}",
                "wacc_used": f"{wacc:.1%}",
                "fcf_periods_analyzed": len(fcf_history)
            }

        key_metrics = {}
        if "dcf" in method_values and method_values["dcf"]["value"] > 0 and method_values["dcf"]["gap"] is not None:
            key_metrics["dcf_gap"] = {"label": "DCF 估值空间", "value": method_values["dcf"]["gap"], "format": "percent"}
        if "owner_earnings" in method_values and method_values["owner_earnings"]["value"] > 0 and method_values["owner_earnings"]["gap"] is not None:
            key_metrics["owner_earnings_gap"] = {"label": "所有者收益估值空间", "value": method_values["owner_earnings"]["gap"], "format": "percent"}
        if weighted_gap is not None:
            key_metrics["weighted_gap"] = {"label": "加权估值空间", "value": weighted_gap, "format": "percent"}

        strengths = []
        risks = []
        for m, vals in method_values.items():
            gap = vals.get("gap")
            name = "DCF 估值" if m == "dcf" else "所有者收益估值" if m == "owner_earnings" else m
            if gap and gap > 0.15:
                strengths.append(f"{name}具备安全边际")
            elif gap and gap < -0.15:
                risks.append(f"{name}显示当前市值溢价偏高")

        # Synthesize Human-readable Valuation narrative with safe formatting
        dcf_val = method_values.get("dcf", {}).get("value") or 0.0
        dcf_gap = method_values.get("dcf", {}).get("gap")
        dcf_gap_str = f"{dcf_gap:+.1%}" if dcf_gap is not None else "不适用"

        ri_val = method_values.get("residual_income", {}).get("value") or 0.0
        ri_gap = method_values.get("residual_income", {}).get("gap")
        ri_gap_str = f"{ri_gap:+.1%}" if ri_gap is not None else "不适用"

        wacc_pct = f"{wacc:.1%}" if "wacc" in locals() and wacc is not None else "10.0%"
        mcap_val = market_cap or 0.0
        w_gap_val = weighted_gap if weighted_gap is not None else 0.0
        w_gap_str = f"{weighted_gap:+.1%}" if weighted_gap is not None else "数据不充分"

        verdict_cn = "估值显著偏高（缺乏安全边际）" if signal == "bearish" else "估值具备安全边际（折价低估）" if signal == "bullish" else "估值处于合理中枢区间"

        val_summary = (
            f"估值分析综合研判：当前公司总市值为 ¥{mcap_val:,.2f}。基于过去 {len(fcf_history) if 'fcf_history' in locals() else 8} 期自由现金流序列，"
            f"在设定折现率 WACC 为 {wacc_pct} 的多情景 DCF 估值模型下，测算基准内在价值为 ¥{dcf_val:,.2f}，较当前市值存在 {dcf_gap_str} 的折溢价空间；"
            f"剩余收益模型测算内在价值为 ¥{ri_val:,.2f}（折溢价 {ri_gap_str}）。"
            f"多模型加权估值空间为 {w_gap_str}。结论给出【{verdict_cn}】，当前交易价格未提供充足安全边际，面临消化溢价的下行调整压力。"
        )

        val_narrative = {
            "dcf_model": f"增强型现金流折现 (DCF)：采用 WACC {wacc_pct}，测得内在价值公允底盘为 ¥{dcf_val:,.2f}，相对当前市值溢价折让幅度为 {dcf_gap_str}。",
            "residual_income": f"剩余收益模型 (Edwards-Bell-Ohlson)：考虑股东权益与超额收益折现，测算内在价值为 ¥{ri_val:,.2f}，相对偏离度为 {ri_gap_str}。",
            "margin_of_safety": f"安全边际与估值空间：加权综合估值偏离度为 {w_gap_str}，安全边际{'处于坚实防御区间' if w_gap_val > 0.15 else '明显不足，市值存在高估溢价' if w_gap_val < -0.15 else '处于相对合理公允带'}。",
            "conclusion": val_summary
        }

        key_findings = [
            f"当前市场总市值约为 ¥{mcap_val:,.2f}",
            f"DCF模型（WACC {wacc_pct}）测算内在价值为 ¥{dcf_val:,.2f}，估值差距为 {dcf_gap_str}",
            f"剩余收益模型测算内在价值为 ¥{ri_val:,.2f}，估值差距为 {ri_gap_str}",
            f"各估值模型综合加权估值空间为 {w_gap_str}，安全边际{'相对欠缺' if w_gap_val < 0 else '良好'}"
        ]

        # Retrieve official disclosure report reference from CNINFO via AKShare
        latest_report_ref = get_latest_financial_report_reference(ticker, end_date)
        all_report_refs = get_financial_report_references(ticker, end_date, limit=4)
        
        # Register into global source registry in state
        source_registry = data.setdefault("source_registry", {})
        if latest_report_ref:
            source_registry[latest_report_ref.source_id] = latest_report_ref.model_dump()
        for ref in all_report_refs:
            source_registry[ref.source_id] = ref.model_dump()

        ref_dict = latest_report_ref.model_dump() if latest_report_ref else None

        evidence = [
            {"metric": "当前市场总市值", "value": f"¥{mcap_val:,.2f}", "interpretation": "二级市场当前计价基准", "source": "BaoStock + AKShare", "report_ref": ref_dict},
            {"metric": "DCF 基准内在价值", "value": f"¥{dcf_val:,.2f}", "interpretation": f"估值偏离度 {dcf_gap_str}", "source": "DCF 现金流折现模型", "report_ref": ref_dict},
            {"metric": "剩余收益内在价值", "value": f"¥{ri_val:,.2f}", "interpretation": f"估值偏离度 {ri_gap_str}", "source": "剩余收益模型", "report_ref": ref_dict},
            {"metric": "加权平均资本成本 (WACC)", "value": wacc_pct, "interpretation": "资本折现率基准", "source": "资本结构参数计算"},
            {"metric": "加权综合估值偏离度", "value": w_gap_str, "interpretation": verdict_cn, "source": "多模型加权矩阵"}
        ]

        bull_case = [
            f"若未来自由现金流增速超预期提升20%以上，DCF估值中枢有望大幅抬升",
            "强大的商业护城河可赋予一定程度的品牌无形资产溢价"
        ]

        bear_case = [
            f"DCF 测算公允价值较现价折让较深（{dcf_gap_str}），表明当前股价隐含了较高的未来现金流预期",
            f"剩余收益模型亦显示当前价格较合理权益中枢偏离 {ri_gap_str}"
        ]

        data_quality = {
            "status": "complete",
            "source": "BaoStock + AKShare (Sina财经)",
            "official_filing": latest_report_ref.title if latest_report_ref else "官方定期报告",
            "periods_analyzed": len(fcf_history) if "fcf_history" in locals() else 8,
            "limitations": ["贴现率 WACC 及永续增长率假设对宏观利率较为敏感"]
        }

        raw_reasoning_dict = dict(reasoning)

        sources_list = [r.model_dump() for r in all_report_refs] if all_report_refs else ([ref_dict] if ref_dict else [])

        valuation_analysis[ticker] = {
            "signal": signal,
            "confidence": confidence,
            "summary": val_summary,
            "narrative": val_narrative,
            "key_findings": key_findings,
            "evidence": evidence,
            "bull_case": bull_case,
            "bear_case": bear_case,
            "risks": risks or ["当前价格高出DCF公允中枢的估值均值回归风险"],
            "data_quality": data_quality,
            "key_metrics": key_metrics,
            "strengths": strengths or ["估值模型历史数据完整"],
            "reasoning": val_summary,
            "_raw_reasoning": raw_reasoning_dict,
            "sources": sources_list,
            "latest_report": ref_dict,
        }
        progress.update_status(agent_id, ticker, "Done", analysis=json.dumps(reasoning, indent=4))

    # ---- Emit message (for LLM tool chain) ----
    msg = HumanMessage(content=json.dumps(valuation_analysis), name=agent_id)
    if state["metadata"].get("show_reasoning"):
        show_agent_reasoning(valuation_analysis, "Valuation Analysis Agent")

    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"][agent_id] = valuation_analysis

    progress.update_status(agent_id, None, "Done")
    
    return {"messages": [msg], "data": data}

#############################
# Helper Valuation Functions
#############################

def calculate_owner_earnings_value(
    net_income: float | None,
    depreciation: float | None,
    capex: float | None,
    working_capital_change: float | None,
    growth_rate: float = 0.05,
    required_return: float = 0.15,
    margin_of_safety: float = 0.25,
    num_years: int = 5,
) -> float:
    """Buffett owner‑earnings valuation with margin‑of‑safety."""
    if not all(isinstance(x, (int, float)) for x in [net_income, depreciation, capex, working_capital_change]):
        return 0

    owner_earnings = net_income + depreciation - capex - working_capital_change
    if owner_earnings <= 0:
        return 0

    pv = 0.0
    for yr in range(1, num_years + 1):
        future = owner_earnings * (1 + growth_rate) ** yr
        pv += future / (1 + required_return) ** yr

    terminal_growth = min(growth_rate, 0.03)
    term_val = (owner_earnings * (1 + growth_rate) ** num_years * (1 + terminal_growth)) / (
        required_return - terminal_growth
    )
    pv_term = term_val / (1 + required_return) ** num_years

    intrinsic = pv + pv_term
    return intrinsic * (1 - margin_of_safety)


def calculate_intrinsic_value(
    free_cash_flow: float | None,
    growth_rate: float = 0.05,
    discount_rate: float = 0.10,
    terminal_growth_rate: float = 0.02,
    num_years: int = 5,
) -> float:
    """Classic DCF on FCF with constant growth and terminal value."""
    if free_cash_flow is None or free_cash_flow <= 0:
        return 0

    pv = 0.0
    for yr in range(1, num_years + 1):
        fcft = free_cash_flow * (1 + growth_rate) ** yr
        pv += fcft / (1 + discount_rate) ** yr

    term_val = (
        free_cash_flow * (1 + growth_rate) ** num_years * (1 + terminal_growth_rate)
    ) / (discount_rate - terminal_growth_rate)
    pv_term = term_val / (1 + discount_rate) ** num_years

    return pv + pv_term


def calculate_ev_ebitda_value(financial_metrics: list):
    """Implied equity value via median EV/EBITDA multiple."""
    if not financial_metrics:
        return 0
    m0 = financial_metrics[0]
    if not (m0.enterprise_value and m0.enterprise_value_to_ebitda_ratio):
        return 0
    if m0.enterprise_value_to_ebitda_ratio == 0:
        return 0

    ebitda_now = m0.enterprise_value / m0.enterprise_value_to_ebitda_ratio
    med_mult = statistics.median([
        m.enterprise_value_to_ebitda_ratio for m in financial_metrics if m.enterprise_value_to_ebitda_ratio
    ])
    ev_implied = med_mult * ebitda_now
    net_debt = (m0.enterprise_value or 0) - (m0.market_cap or 0)
    return max(ev_implied - net_debt, 0)


def calculate_residual_income_value(
    market_cap: float | None,
    net_income: float | None,
    price_to_book_ratio: float | None,
    book_value_growth: float = 0.03,
    cost_of_equity: float = 0.10,
    terminal_growth_rate: float = 0.03,
    num_years: int = 5,
):
    """Residual Income Model (Edwards‑Bell‑Ohlson)."""
    if not (market_cap and net_income and price_to_book_ratio and price_to_book_ratio > 0):
        return 0

    book_val = market_cap / price_to_book_ratio
    ri0 = net_income - cost_of_equity * book_val
    if ri0 <= 0:
        return 0

    pv_ri = 0.0
    for yr in range(1, num_years + 1):
        ri_t = ri0 * (1 + book_value_growth) ** yr
        pv_ri += ri_t / (1 + cost_of_equity) ** yr

    term_ri = ri0 * (1 + book_value_growth) ** (num_years + 1) / (
        cost_of_equity - terminal_growth_rate
    )
    pv_term = term_ri / (1 + cost_of_equity) ** num_years

    intrinsic = book_val + pv_ri + pv_term
    return intrinsic * 0.8  # 20% margin of safety


####################################
# Enhanced DCF Helper Functions
####################################

def calculate_wacc(
    market_cap: float,
    total_debt: float | None,
    cash: float | None,
    interest_coverage: float | None,
    debt_to_equity: float | None,
    beta_proxy: float = 1.0,
    risk_free_rate: float = 0.045,
    market_risk_premium: float = 0.06
) -> float:
    """Calculate WACC using available financial data."""
    
    # Cost of Equity (CAPM)
    cost_of_equity = risk_free_rate + beta_proxy * market_risk_premium
    
    # Cost of Debt - estimate from interest coverage
    if interest_coverage and interest_coverage > 0:
        # Higher coverage = lower cost of debt
        cost_of_debt = max(risk_free_rate + 0.01, risk_free_rate + (10 / interest_coverage))
    else:
        cost_of_debt = risk_free_rate + 0.05  # Default spread
    
    # Weights
    net_debt = max((total_debt or 0) - (cash or 0), 0)
    total_value = market_cap + net_debt
    
    if total_value > 0:
        weight_equity = market_cap / total_value
        weight_debt = net_debt / total_value
        
        # Tax shield (assume 25% corporate tax rate)
        wacc = (weight_equity * cost_of_equity) + (weight_debt * cost_of_debt * 0.75)
    else:
        wacc = cost_of_equity
    
    return min(max(wacc, 0.06), 0.20)  # Floor 6%, cap 20%


def calculate_fcf_volatility(fcf_history: list[float]) -> float:
    """Calculate FCF volatility as coefficient of variation."""
    if len(fcf_history) < 3:
        return 0.5  # Default moderate volatility
    
    # Filter out zeros and negatives for volatility calc
    positive_fcf = [fcf for fcf in fcf_history if fcf > 0]
    if len(positive_fcf) < 2:
        return 0.8  # High volatility if mostly negative FCF
    
    try:
        mean_fcf = statistics.mean(positive_fcf)
        std_fcf = statistics.stdev(positive_fcf)
        return min(std_fcf / mean_fcf, 1.0) if mean_fcf > 0 else 0.8
    except:
        return 0.5


def calculate_enhanced_dcf_value(
    fcf_history: list[float],
    growth_metrics: dict,
    wacc: float,
    market_cap: float,
    revenue_growth: float | None = None
) -> float:
    """Enhanced DCF with multi-stage growth."""
    
    if not fcf_history or fcf_history[0] <= 0:
        return 0
    
    # Analyze FCF trend and quality
    fcf_current = fcf_history[0]
    fcf_avg_3yr = sum(fcf_history[:3]) / min(3, len(fcf_history))
    fcf_volatility = calculate_fcf_volatility(fcf_history)
    
    # Stage 1: High Growth (Years 1-3)
    # Use revenue growth but cap based on business maturity
    high_growth = min(revenue_growth or 0.05, 0.25) if revenue_growth else 0.05
    if market_cap > 50_000_000_000:  # Large cap
        high_growth = min(high_growth, 0.10)
    
    # Stage 2: Transition (Years 4-7)
    transition_growth = (high_growth + 0.03) / 2
    
    # Stage 3: Terminal (steady state)
    terminal_growth = min(0.03, high_growth * 0.6)
    
    # Project FCF with stages
    pv = 0
    base_fcf = max(fcf_current, fcf_avg_3yr * 0.85)  # Conservative base
    
    # High growth stage
    for year in range(1, 4):
        fcf_projected = base_fcf * (1 + high_growth) ** year
        pv += fcf_projected / (1 + wacc) ** year
    
    # Transition stage
    for year in range(4, 8):
        transition_rate = transition_growth * (8 - year) / 4  # Declining
        fcf_projected = base_fcf * (1 + high_growth) ** 3 * (1 + transition_rate) ** (year - 3)
        pv += fcf_projected / (1 + wacc) ** year
    
    # Terminal value
    final_fcf = base_fcf * (1 + high_growth) ** 3 * (1 + transition_growth) ** 4
    if wacc <= terminal_growth:
        terminal_growth = wacc * 0.8  # Adjust if invalid
    terminal_value = (final_fcf * (1 + terminal_growth)) / (wacc - terminal_growth)
    pv_terminal = terminal_value / (1 + wacc) ** 7
    
    # Quality adjustment based on FCF volatility
    quality_factor = max(0.7, 1 - (fcf_volatility * 0.5))
    
    return (pv + pv_terminal) * quality_factor


def calculate_dcf_scenarios(
    fcf_history: list[float],
    growth_metrics: dict,
    wacc: float,
    market_cap: float,
    revenue_growth: float | None = None
) -> dict:
    """Calculate DCF under multiple scenarios."""
    
    scenarios = {
        'bear': {'growth_adj': 0.5, 'wacc_adj': 1.2, 'terminal_adj': 0.8},
        'base': {'growth_adj': 1.0, 'wacc_adj': 1.0, 'terminal_adj': 1.0},
        'bull': {'growth_adj': 1.5, 'wacc_adj': 0.9, 'terminal_adj': 1.2}
    }
    
    results = {}
    base_revenue_growth = revenue_growth or 0.05
    
    for scenario, adjustments in scenarios.items():
        adjusted_revenue_growth = base_revenue_growth * adjustments['growth_adj']
        adjusted_wacc = wacc * adjustments['wacc_adj']
        
        results[scenario] = calculate_enhanced_dcf_value(
            fcf_history=fcf_history,
            growth_metrics=growth_metrics,
            wacc=adjusted_wacc,
            market_cap=market_cap,
            revenue_growth=adjusted_revenue_growth
        )
    
    # Probability-weighted average
    expected_value = (
        results['bear'] * 0.2 + 
        results['base'] * 0.6 + 
        results['bull'] * 0.2
    )
    
    return {
        'scenarios': results,
        'expected_value': expected_value,
        'range': results['bull'] - results['bear'],
        'upside': results['bull'],
        'downside': results['bear']
    }
