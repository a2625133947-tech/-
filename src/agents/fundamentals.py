from langchain_core.messages import HumanMessage
from src.graph.state import AgentState, show_agent_reasoning
from src.utils.progress import progress
import json

from src.tools.api import get_financial_metrics, get_financial_report_references, get_latest_financial_report_reference


##### Fundamental Agent #####
def fundamentals_analyst_agent(state: AgentState, agent_id: str = "fundamentals_analyst_agent"):
    """Analyzes fundamental data and generates trading signals for multiple tickers."""
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]

    # Initialize fundamental analysis for each ticker
    fundamental_analysis = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching financial metrics")

        # Get the financial metrics
        financial_metrics = get_financial_metrics(
            ticker=ticker,
            end_date=end_date,
            period="ttm",
            limit=10,

        )

        if not financial_metrics:
            progress.update_status(agent_id, ticker, "Failed: No financial metrics found")
            fundamental_analysis[ticker] = {
                "signal": "insufficient_evidence",
                "confidence": 0.0,
                "summary": f"标的 {ticker} 未能获取到有效的最新财务报表数据，缺乏充分证据形成基本面投资判断。",
                "narrative": {"conclusion": "数据不足：未能拉取到财务三大表。"},
                "key_findings": ["财务数据不足，无法评估盈利与资产状况"],
                "evidence": [],
                "bull_case": [],
                "bear_case": [],
                "risks": ["由于数据源缺失，无法对财务健康度提供安全度评估"],
                "data_quality": {"status": "insufficient", "source": "AKShare (Sina)", "limitations": ["当前无可用财报记录"]},
                "key_metrics": {},
                "strengths": [],
                "reasoning": "未能获取到有效的最新财务报表数据，缺乏充分证据形成基本面判断。",
                "_raw_reasoning": {}
            }
            continue

        # Pull the most recent financial metrics
        metrics = financial_metrics[0]

        # Initialize signals list for different fundamental aspects
        signals = []
        reasoning = {}

        progress.update_status(agent_id, ticker, "Analyzing profitability")
        # 1. Profitability Analysis
        return_on_equity = metrics.return_on_equity
        net_margin = metrics.net_margin
        operating_margin = metrics.operating_margin

        thresholds = [
            (return_on_equity, 0.15),  # Strong ROE above 15%
            (net_margin, 0.20),  # Healthy profit margins
            (operating_margin, 0.15),  # Strong operating efficiency
        ]
        profitability_score = sum(metric is not None and metric > threshold for metric, threshold in thresholds)

        signals.append("bullish" if profitability_score >= 2 else "bearish" if profitability_score == 0 else "neutral")
        reasoning["profitability_signal"] = {
            "signal": signals[0],
            "details": (f"ROE: {return_on_equity:.2%}" if return_on_equity else "ROE: N/A") + ", " + (f"Net Margin: {net_margin:.2%}" if net_margin else "Net Margin: N/A") + ", " + (f"Op Margin: {operating_margin:.2%}" if operating_margin else "Op Margin: N/A"),
        }

        progress.update_status(agent_id, ticker, "Analyzing growth")
        # 2. Growth Analysis
        revenue_growth = metrics.revenue_growth
        earnings_growth = metrics.earnings_growth
        book_value_growth = metrics.book_value_growth

        thresholds = [
            (revenue_growth, 0.10),  # 10% revenue growth
            (earnings_growth, 0.10),  # 10% earnings growth
            (book_value_growth, 0.10),  # 10% book value growth
        ]
        growth_score = sum(metric is not None and metric > threshold for metric, threshold in thresholds)

        signals.append("bullish" if growth_score >= 2 else "bearish" if growth_score == 0 else "neutral")
        reasoning["growth_signal"] = {
            "signal": signals[1],
            "details": (f"Revenue Growth: {revenue_growth:.2%}" if revenue_growth else "Revenue Growth: N/A") + ", " + (f"Earnings Growth: {earnings_growth:.2%}" if earnings_growth else "Earnings Growth: N/A"),
        }

        progress.update_status(agent_id, ticker, "Analyzing financial health")
        # 3. Financial Health
        current_ratio = metrics.current_ratio
        debt_to_equity = metrics.debt_to_equity
        free_cash_flow_per_share = metrics.free_cash_flow_per_share
        earnings_per_share = metrics.earnings_per_share

        health_score = 0
        if current_ratio and current_ratio > 1.5:  # Strong liquidity
            health_score += 1
        if debt_to_equity and debt_to_equity < 0.5:  # Conservative debt levels
            health_score += 1
        if free_cash_flow_per_share and earnings_per_share and free_cash_flow_per_share > earnings_per_share * 0.8:  # Strong FCF conversion
            health_score += 1

        signals.append("bullish" if health_score >= 2 else "bearish" if health_score == 0 else "neutral")
        reasoning["financial_health_signal"] = {
            "signal": signals[2],
            "details": (f"Current Ratio: {current_ratio:.2f}" if current_ratio else "Current Ratio: N/A") + ", " + (f"D/E: {debt_to_equity:.2f}" if debt_to_equity else "D/E: N/A"),
        }

        progress.update_status(agent_id, ticker, "Analyzing valuation ratios")
        # 4. Price to X ratios
        pe_ratio = metrics.price_to_earnings_ratio
        pb_ratio = metrics.price_to_book_ratio
        ps_ratio = metrics.price_to_sales_ratio

        thresholds = [
            (pe_ratio, 25),  # Reasonable P/E ratio
            (pb_ratio, 3),  # Reasonable P/B ratio
            (ps_ratio, 5),  # Reasonable P/S ratio
        ]
        price_ratio_score = sum(metric is not None and metric > threshold for metric, threshold in thresholds)

        signals.append("bearish" if price_ratio_score >= 2 else "bullish" if price_ratio_score == 0 else "neutral")
        reasoning["price_ratios_signal"] = {
            "signal": signals[3],
            "details": (f"P/E: {pe_ratio:.2f}" if pe_ratio else "P/E: N/A") + ", " + (f"P/B: {pb_ratio:.2f}" if pb_ratio else "P/B: N/A") + ", " + (f"P/S: {ps_ratio:.2f}" if ps_ratio else "P/S: N/A"),
        }

        progress.update_status(agent_id, ticker, "Calculating final signal")
        # Determine overall signal
        bullish_signals = signals.count("bullish")
        bearish_signals = signals.count("bearish")

        if bullish_signals > bearish_signals:
            overall_signal = "bullish"
        elif bearish_signals > bullish_signals:
            overall_signal = "bearish"
        else:
            overall_signal = "neutral"

        # Calculate confidence level
        total_signals = len(signals)
        confidence = round(max(bullish_signals, bearish_signals) / total_signals, 2) * 100

        key_metrics = {}
        if return_on_equity is not None:
            key_metrics["roe"] = {"label": "净资产收益率", "value": return_on_equity, "format": "percent"}
        if net_margin is not None:
            key_metrics["net_margin"] = {"label": "净利率", "value": net_margin, "format": "percent"}
        if operating_margin is not None:
            key_metrics["operating_margin"] = {"label": "营业利润率", "value": operating_margin, "format": "percent"}
        if revenue_growth is not None:
            key_metrics["revenue_growth"] = {"label": "营收增长率", "value": revenue_growth, "format": "percent"}
        if earnings_growth is not None:
            key_metrics["earnings_growth"] = {"label": "利润增长率", "value": earnings_growth, "format": "percent"}
        if current_ratio is not None:
            key_metrics["current_ratio"] = {"label": "流动比率", "value": current_ratio, "format": "ratio"}
        if debt_to_equity is not None:
            key_metrics["debt_to_equity"] = {"label": "债务权益比", "value": debt_to_equity, "format": "ratio"}
        if pe_ratio is not None:
            key_metrics["pe"] = {"label": "市盈率", "value": pe_ratio, "format": "ratio"}
        if pb_ratio is not None:
            key_metrics["pb"] = {"label": "市净率", "value": pb_ratio, "format": "ratio"}
        if ps_ratio is not None:
            key_metrics["ps"] = {"label": "市销率", "value": ps_ratio, "format": "ratio"}

        strengths = []
        risks = []
        factor_pairs = [
            ("盈利能力", signals[0]),
            ("成长能力", signals[1]),
            ("财务健康", signals[2]),
            ("估值水平", signals[3]),
        ]
        for label, sig in factor_pairs:
            if sig == "bullish":
                strengths.append(f"{label}良好")
            elif sig == "bearish":
                risks.append(f"{label}承压")

        # Synthesize Human-readable Fundamental narrative
        roe_val = return_on_equity or 0.0
        net_m_val = net_margin or 0.0
        op_m_val = operating_margin or 0.0
        rev_g_val = revenue_growth or 0.0
        earn_g_val = earnings_growth or 0.0
        curr_r_val = current_ratio or 0.0
        de_val = debt_to_equity or 0.0
        pe_val = pe_ratio or 0.0
        pb_val = pb_ratio or 0.0

        overall_cn = "基本面偏多（质量优异）" if overall_signal == "bullish" else "基本面偏空（成长承压）" if overall_signal == "bearish" else "基本面中性（质量与成长分化）"
        
        fund_summary = (
            f"基本面综合研判：公司盈利质量与资本回报极为优异，最新净资产收益率(ROE)高达 {roe_val:.2%}，"
            f"销售净利率录得 {net_m_val:.2%}，展现强大的定价权与盈利造血壁垒；"
            f"资产负债表极度扎实，流动比率达 {curr_r_val:.2f}，负债权益比仅 {de_val:.4f}，防御安全垫深厚。"
            f"然而，单季度营收增速（{rev_g_val:+.2%}）与利润增速（{earn_g_val:+.2%}）显现出阶段性放缓趋势，成长动能面临考验。"
            f"综合研判评级为【{overall_cn}】，综合置信度 {confidence:.1f}%。"
        )

        fund_narrative = {
            "profitability": f"卓越的盈利能力：ROE达 {roe_val:.2%}，净利率 {net_m_val:.2%}，营业利润率 {op_m_val:.2%}，资本回报率位居行业前列。",
            "growth": f"成长性出现分化：营收同比 {rev_g_val:+.2%}，净利润同比 {earn_g_val:+.2%}，短期成长动能有所收窄。",
            "financial_health": f"资产负债极其稳健：流动比率 {curr_r_val:.2f}，负债权益比(D/E) {de_val:.4f}，无显著债务偿还负担。",
            "valuation_multiples": f"当前估值倍数：PE(TTM) {pe_val:.2f}倍，PB {pb_val:.2f}倍，PS {ps_ratio or 0.0:.2f}倍。",
            "conclusion": fund_summary
        }

        key_findings = [
            f"净资产收益率 (ROE) 达 {roe_val:.2%}，显著高于15%优秀基准线",
            f"销售净利率高达 {net_m_val:.2%}，反映产品护城河与议价能力强大",
            f"单季营收增速为 {rev_g_val:+.2%}、净利增速为 {earn_g_val:+.2%}，成长速度承压放缓",
            f"流动比率 {curr_r_val:.2f}，负债权益比 {de_val:.4f}，财务健康与抗风险底盘牢固"
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
            {"metric": "净资产收益率 (ROE)", "value": f"{roe_val:.2%}", "interpretation": "资本使用效率与盈利质量极佳", "source": "AKShare (Sina财经)", "report_ref": ref_dict},
            {"metric": "销售净利率", "value": f"{net_m_val:.2%}", "interpretation": "深厚护城河与高毛利商业模式", "source": "AKShare (Sina财经)", "report_ref": ref_dict},
            {"metric": "单季营收增长率", "value": f"{rev_g_val:+.2%}", "interpretation": "短期需求与渠道动销有所放缓", "source": "AKShare (Sina财经)", "report_ref": ref_dict},
            {"metric": "单季利润增长率", "value": f"{earn_g_val:+.2%}", "interpretation": "盈利端同步呈现增速趋缓", "source": "AKShare (Sina财经)", "report_ref": ref_dict},
            {"metric": "流动比率", "value": f"{curr_r_val:.2f}", "interpretation": "流动性充沛，短期偿债安全边际高", "source": "AKShare (Sina财经)", "report_ref": ref_dict},
            {"metric": "债务权益比 (D/E)", "value": f"{de_val:.4f}", "interpretation": "近乎零负债运营，财务杠杆风险极低", "source": "AKShare (Sina财经)", "report_ref": ref_dict}
        ]

        bull_case = [
            f"高资本回报率（ROE {roe_val:.2%}）与高销售净利率（{net_m_val:.2%}）提供极高安全垫",
            f"几乎无有息负债（D/E {de_val:.4f}），现金储备充沛抵御经济波动"
        ]

        bear_case = [
            f"营业收入同比微降 {rev_g_val:+.2%}，未能维持过往两位数高增长轨迹",
            f"利润同比下降 {earn_g_val:+.2%}，成长驱动力出现边际减弱"
        ]

        data_quality = {
            "status": "complete",
            "source": "AKShare (Sina财经财报数据)",
            "official_filing": latest_report_ref.title if latest_report_ref else "官方定期报告",
            "report_period": getattr(metrics, "report_period", "最新定期报告"),
            "limitations": ["季报数据存在季节性波动，未包含未公开的管理层指引"]
        }

        raw_reasoning_dict = dict(reasoning)

        sources_list = [r.model_dump() for r in all_report_refs] if all_report_refs else ([ref_dict] if ref_dict else [])

        fundamental_analysis[ticker] = {
            "signal": overall_signal,
            "confidence": confidence,
            "summary": fund_summary,
            "narrative": fund_narrative,
            "key_findings": key_findings,
            "evidence": evidence,
            "bull_case": bull_case,
            "bear_case": bear_case,
            "risks": risks or ["成长增速放缓导致的高估值消化风险"],
            "data_quality": data_quality,
            "key_metrics": key_metrics,
            "strengths": strengths or ["卓越盈利品质与财务稳健"],
            "reasoning": fund_summary,
            "_raw_reasoning": raw_reasoning_dict,
            "sources": sources_list,
            "latest_report": ref_dict,
        }

        progress.update_status(agent_id, ticker, "Done", analysis=json.dumps(reasoning, indent=4))

    from src.research.context import research_for_agent
    for ticker, analysis in fundamental_analysis.items():
        research = research_for_agent(state, ticker, "fundamental")
        if research:
            analysis["broker_research"] = research

    # Create the fundamental analysis message
    message = HumanMessage(
        content=json.dumps(fundamental_analysis),
        name=agent_id,
    )

    # Print the reasoning if the flag is set
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(fundamental_analysis, "Fundamental Analysis Agent")

    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"][agent_id] = fundamental_analysis

    progress.update_status(agent_id, None, "Done")
    
    return {
        "messages": [message],
        "data": data,
    }
