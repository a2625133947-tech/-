"""A-share investor-inspired strategy prototypes.

These are project-defined, observable factor models.  They are not the named
investors' actual holdings, advice, or a reconstruction of private methods.
"""

from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass
from datetime import date, timedelta
from functools import partial

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from src.graph.state import AgentState, show_agent_reasoning
from src.investors.contracts import InvestorMode
from src.investors.profiles import PILOT_PROFILES, SHADOW_PROFILES
from src.investors.runtime import evaluate_ticker, to_analyst_result
from src.tools.api import get_financial_metrics, get_prices
from src.utils.llm import call_llm
from src.utils.progress import progress

logger = logging.getLogger(__name__)


class InvestorNarrative(BaseModel):
    reasoning: str


@dataclass(frozen=True)
class InvestorProfile:
    name: str
    lens: str
    weights: dict[str, float]


# Weights are modeling choices for distinct, testable lenses, not attributed
# formulas or claims about any person's current portfolio.
PROFILES: dict[str, InvestorProfile] = {
    "duan_yongping": InvestorProfile("段永平", "长期经营质量与合理估值", {"profitability": 3, "cash_flow": 3, "balance_sheet": 2, "valuation": 2}),
    "deng_xiaofeng": InvestorProfile("邓晓峰", "价值与盈利修复", {"valuation": 3, "earnings_growth": 2, "profitability": 2, "balance_sheet": 1, "momentum": 1}),
    "feng_liu": InvestorProfile("冯柳", "低预期与基本面改善", {"valuation": 3, "earnings_growth": 3, "revenue_growth": 1, "balance_sheet": 1}),
    "fu_pengbo": InvestorProfile("傅鹏博", "成长与经营质量", {"revenue_growth": 3, "earnings_growth": 2, "profitability": 2, "cash_flow": 1, "valuation": 1}),
    "zhu_shaoxing": InvestorProfile("朱少醒", "均衡的质量、成长与估值", {"profitability": 2, "revenue_growth": 2, "valuation": 2, "cash_flow": 2, "balance_sheet": 1}),
    "zhang_kun": InvestorProfile("张坤", "持续盈利能力与现金创造", {"profitability": 3, "cash_flow": 3, "balance_sheet": 2, "valuation": 1}),
    "liu_yanchun": InvestorProfile("刘彦春", "盈利质量与成长", {"profitability": 3, "earnings_growth": 2, "revenue_growth": 2, "cash_flow": 2}),
    "xie_zhiyu": InvestorProfile("谢治宇", "成长与估值匹配", {"revenue_growth": 2, "earnings_growth": 2, "valuation": 2, "profitability": 2, "balance_sheet": 1}),
    "dong_chengfei": InvestorProfile("董承非", "估值纪律与财务稳健", {"valuation": 3, "balance_sheet": 3, "cash_flow": 2, "profitability": 1}),
    "wang_yawei": InvestorProfile("王亚伟", "估值、盈利变化与趋势", {"valuation": 2, "earnings_growth": 3, "momentum": 2, "balance_sheet": 1}),
    "chen_guangming": InvestorProfile("陈光明", "质量价值与现金流", {"profitability": 3, "cash_flow": 3, "valuation": 2, "balance_sheet": 2}),
    "lin_yuan": InvestorProfile("林园", "持续盈利、成长与现金创造", {"profitability": 3, "revenue_growth": 2, "earnings_growth": 2, "cash_flow": 2}),
}


def _finite(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _grade(value: float | None, good: float, bad: float, *, lower_is_better: bool = False) -> float | None:
    value = _finite(value)
    if value is None:
        return None
    if lower_is_better:
        if value < 0 or (value == 0 and good >= 1):  # Nonpositive P/E/P/B is not cheap.
            return -1.0
        return 1.0 if value <= good else -1.0 if value >= bad else 0.0
    return 1.0 if value >= good else -1.0 if value <= bad else 0.0


def _factors(metric, prices: list) -> tuple[dict[str, float | None], dict[str, float | None]]:
    raw = {
        "roe": _finite(getattr(metric, "return_on_equity", None)),
        "net_margin": _finite(getattr(metric, "net_margin", None)),
        "revenue_growth": _finite(getattr(metric, "revenue_growth", None)),
        "earnings_growth": _finite(getattr(metric, "earnings_growth", None)),
        "fcf_yield": _finite(getattr(metric, "free_cash_flow_yield", None)),
        "debt_to_equity": _finite(getattr(metric, "debt_to_equity", None)),
        "pe": _finite(getattr(metric, "price_to_earnings_ratio", None)),
        "pb": _finite(getattr(metric, "price_to_book_ratio", None)),
    }
    if len(prices) >= 60 and (date.fromisoformat(str(prices[-1].time)[:10]) - date.fromisoformat(str(prices[0].time)[:10])).days >= 120:
        first, last = _finite(prices[0].close), _finite(prices[-1].close)
        raw["six_month_return"] = last / first - 1 if first and last else None
    else:
        raw["six_month_return"] = None

    quality = [_grade(raw["roe"], 0.15, 0.03), _grade(raw["net_margin"], 0.15, 0.02)]
    valuation = [_grade(raw["pe"], 15, 40, lower_is_better=True), _grade(raw["pb"], 2, 6, lower_is_better=True)]
    available_quality = [score for score in quality if score is not None]
    available_valuation = [score for score in valuation if score is not None]
    scores = {
        "profitability": sum(available_quality) / len(available_quality) if available_quality else None,
        "revenue_growth": _grade(raw["revenue_growth"], 0.15, -0.05),
        "earnings_growth": _grade(raw["earnings_growth"], 0.15, -0.05),
        "cash_flow": _grade(raw["fcf_yield"], 0.05, 0.0),
        "balance_sheet": _grade(raw["debt_to_equity"], 0.5, 1.5, lower_is_better=True),
        "valuation": sum(available_valuation) / len(available_valuation) if available_valuation else None,
        "momentum": _grade(raw["six_month_return"], 0.1, -0.1),
    }
    return scores, raw


def _decision(profile: InvestorProfile, scores: dict[str, float | None]) -> tuple[str, float, float, int]:
    observed = [(profile.weights[key], scores[key]) for key in profile.weights if scores[key] is not None]
    coverage = sum(weight for weight, _ in observed) / sum(profile.weights.values())
    if len(observed) < 2 or coverage < 0.5:
        return "neutral", 0.0, coverage, len(observed)
    weighted = sum(weight * score for weight, score in observed) / sum(weight for weight, _ in observed)
    signal = "bullish" if weighted >= 0.3 else "bearish" if weighted <= -0.3 else "neutral"
    confidence = round(min(85.0, abs(weighted) * 65 + 20) * coverage, 1)
    return signal, confidence, coverage, len(observed)


def _fallback_reasoning(profile: InvestorProfile, ticker: str, signal: str, coverage: float, raw: dict) -> str:
    observed = ", ".join(f"{key}={value:.3g}" for key, value in raw.items() if value is not None)
    if not observed:
        observed = "无可用指标"
    return (
        f"{profile.name}理念启发的{profile.lens}策略原型；{ticker}的可用证据：{observed}。"
        f"指标覆盖率 {coverage:.0%}，规则信号为 {signal}。这是项目模型判断，并非本人观点。"
    )


FACTOR_NARRATIVES = {
    "profitability": {"positive": "盈利质量较强", "negative": "盈利质量承压"},
    "cash_flow": {"positive": "自由现金流表现良好", "negative": "自由现金流承压"},
    "balance_sheet": {"positive": "资产负债表稳健", "negative": "资产负债压力较大"},
    "revenue_growth": {"positive": "营收增长良好", "negative": "营收增长承压"},
    "earnings_growth": {"positive": "盈利增长强劲", "negative": "盈利增长承压"},
    "valuation": {"positive": "估值具备吸引力", "negative": "当前估值吸引力有限"},
    "momentum": {"positive": "近期价格动量向好", "negative": "近期价格动量偏弱"},
}

A_SHARE_METRIC_CONFIG = {
    "roe": {"label": "ROE", "format": "percent"},
    "net_margin": {"label": "净利率", "format": "percent"},
    "fcf_yield": {"label": "自由现金流收益率", "format": "percent"},
    "revenue_growth": {"label": "营收增长", "format": "percent"},
    "earnings_growth": {"label": "盈利增长", "format": "percent"},
    "six_month_return": {"label": "六个月回报", "format": "percent"},
    "pe": {"label": "市盈率", "format": "ratio"},
    "pb": {"label": "市净率", "format": "ratio"},
    "debt_to_equity": {"label": "资产负债率", "format": "percent"},
}


def _build_key_metrics(profile: InvestorProfile, raw: dict[str, float | None]) -> dict[str, dict[str, any]]:
    metrics = {}
    candidate_keys = [
        "roe", "net_margin", "fcf_yield", "revenue_growth", "earnings_growth", "six_month_return",
    ]
    if "valuation" in profile.weights:
        candidate_keys.extend(["pe", "pb"])
    if "balance_sheet" in profile.weights:
        candidate_keys.append("debt_to_equity")

    for key in candidate_keys:
        val = raw.get(key)
        if val is not None and key in A_SHARE_METRIC_CONFIG:
            cfg = A_SHARE_METRIC_CONFIG[key]
            metrics[key] = {
                "label": cfg["label"],
                "value": val,
                "format": cfg["format"],
            }
    return metrics


def _build_strengths_and_risks(profile: InvestorProfile, scores: dict[str, float | None]) -> tuple[list[str], list[str]]:
    weighted_factors = sorted(profile.weights.keys(), key=lambda k: profile.weights[k], reverse=True)
    other_factors = [k for k in FACTOR_NARRATIVES if k not in profile.weights]
    factor_order = weighted_factors + other_factors

    strengths = []
    risks = []
    for factor in factor_order:
        score = scores.get(factor)
        if score is None:
            continue
        if score >= 0.5:
            strengths.append(FACTOR_NARRATIVES[factor]["positive"])
        elif score <= -0.5:
            risks.append(FACTOR_NARRATIVES[factor]["negative"])
    return strengths, risks


def investor_agent(state: AgentState, *, profile_key: str, agent_id: str | None = None) -> dict:
    profile = PROFILES[profile_key]
    agent_id = agent_id or f"{profile_key}_agent"
    data = state["data"]
    end_date = data["end_date"]
    start_date = (date.fromisoformat(end_date) - timedelta(days=183)).isoformat()
    results = {}
    configured_mode = state.get("metadata", {}).get("investor_mode") or os.getenv("A_SHARE_INVESTOR_MODE", "legacy")
    raw_mode = configured_mode.lower()
    if profile_key in PILOT_PROFILES:
        mode = InvestorMode(raw_mode)
    elif profile_key in SHADOW_PROFILES and raw_mode == "shadow":
        mode = InvestorMode.SHADOW
    else:
        # Non-pilots ignore "new" mode and remain strictly on LEGACY
        mode = InvestorMode.LEGACY

    for ticker in data["tickers"]:
        if mode is InvestorMode.NEW:
            progress.update_status(agent_id, ticker, "Evaluating factors")
            evaluation = evaluate_ticker(profile_key, ticker, end_date)
            prose = evaluation.reasoning
            if any(item.score is not None for item in evaluation.used_factors):
                prompt = ChatPromptTemplate.from_messages([
                    ("system", """你只负责用中文解释已确定的项目策略原型结论。不得修改 signal、confidence、
strengths、risks、factor score 或填补缺失数据。不得声称还原投资人私人模型。"""),
                    ("human", """股票：{ticker}\n策略：{profile}\n规则信号：{signal}\n规则置信度：{confidence}\n"
                     "因子：{factors}\n优势：{strengths}\n风险：{risks}\n局限：{limitations}\n"
                     "仅返回 JSON：{{\"reasoning\":\"...\"}}"""),
                ]).invoke({
                    "ticker": ticker, "profile": PILOT_PROFILES[profile_key].description,
                    "signal": evaluation.signal, "confidence": evaluation.confidence,
                    "factors": json.dumps([item.model_dump(mode="json") for item in evaluation.used_factors], ensure_ascii=False),
                    "strengths": json.dumps(evaluation.strengths, ensure_ascii=False),
                    "risks": json.dumps(evaluation.risks, ensure_ascii=False),
                    "limitations": json.dumps(evaluation.limitations, ensure_ascii=False),
                })
                narrative = call_llm(prompt, InvestorNarrative, agent_name=agent_id, state=state,
                                     default_factory=lambda: InvestorNarrative(reasoning=prose))
                prose = narrative.reasoning.strip() or prose
            # Provider prose cannot erase the strategy's mandatory limitations.
            if profile_key == "feng_liu" and PILOT_PROFILES[profile_key].limitations[0] not in prose:
                prose += " 局限：" + PILOT_PROFILES[profile_key].limitations[0] + "。"
            results[ticker] = to_analyst_result(evaluation, reasoning=prose)
            progress.update_status(agent_id, ticker, "Done", analysis=prose)
            continue
        progress.update_status(agent_id, ticker, "Fetching A-share data")
        errors = []
        try:
            metrics = get_financial_metrics(ticker, end_date, period="ttm", limit=1)
        except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
            logger.debug("Financial metrics unavailable for %s", ticker, exc_info=True)
            metrics = []
            errors.append(f"financial metrics: {exc}")
        try:
            prices = get_prices(ticker, start_date, end_date)
        except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
            logger.debug("Price history unavailable for %s", ticker, exc_info=True)
            prices = []
            errors.append(f"prices: {exc}")

        if metrics:
            scores, raw = _factors(metrics[0], prices)
            signal, confidence, coverage, observed_count = _decision(profile, scores)
            key_metrics = _build_key_metrics(profile, raw)
            strengths, risks = _build_strengths_and_risks(profile, scores)
        else:
            scores, raw = {}, {}
            signal, confidence, coverage, observed_count = "neutral", 0.0, 0.0, 0
            key_metrics = {}
            strengths, risks = [], []

        fallback = _fallback_reasoning(profile, ticker, signal, coverage, raw)
        if errors:
            fallback += " 数据获取异常：" + "; ".join(errors)
        if observed_count < 2 or coverage < 0.5:
            reasoning = fallback + "；关键指标不足，保持中性。"
        else:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """你是A股策略研究助手。请用中文解释一个受{investor}公开投资理念启发的策略原型，
重点是{lens}。这不是投资人本人发言、持仓或建议；不要模仿其口吻，不要编造行业、公司业务、
管理层、新闻、未提供的财务数据或引用。规则信号已确定，不要改变它。只解释给定指标、
缺失项及局限；数值必须与输入一致。reasoning 请控制在 180 字以内。"""),
                ("human", """股票：{ticker}\n规则信号：{signal}\n置信度：{confidence}\n指标覆盖率：{coverage}\n原始指标：{raw}\n分项评分：{scores}\n只返回 JSON：{{"reasoning":"..."}}"""),
            ]).invoke({
                "investor": profile.name, "lens": profile.lens, "ticker": ticker,
                "signal": signal, "confidence": confidence, "coverage": round(coverage, 2),
                "raw": json.dumps(raw, ensure_ascii=False),
                "scores": json.dumps(scores, ensure_ascii=False),
            })
            narrative = call_llm(
                prompt, InvestorNarrative, agent_name=agent_id, state=state,
                default_factory=lambda: InvestorNarrative(reasoning=fallback),
            )
            explanation = narrative.reasoning.strip() or fallback
            reasoning = f"{profile.name}理念启发的项目策略原型（非本人观点）。{explanation}"

        # Build unified evidence list
        evidence_list = []
        for k, v in (raw or {}).items():
            if v is not None:
                lbl = key_metrics.get(k, {}).get("label") or k
                fmt = key_metrics.get(k, {}).get("format")
                val_str = f"{v:.2%}" if fmt == "percent" else f"{v:.2f}" if isinstance(v, (int, float)) else str(v)
                evidence_list.append({
                    "metric": lbl,
                    "value": val_str,
                    "interpretation": f"策略原型特征指标: {lbl}",
                    "source": "BaoStock + AKShare"
                })

        data_quality_info = {
            "status": "complete" if coverage >= 0.75 else "partial" if coverage >= 0.5 else "insufficient",
            "source": "BaoStock + AKShare",
            "coverage": round(coverage, 2),
            "limitations": list(profile.limitations) if hasattr(profile, "limitations") else ["公开理念启发的策略模型，非投资人本人观点"]
        }

        resolved_signal = signal if coverage >= 0.5 else "insufficient_evidence"

        results[ticker] = {
            "signal": resolved_signal,
            "confidence": confidence,
            "summary": reasoning,
            "narrative": {"conclusion": reasoning},
            "key_findings": strengths + risks,
            "evidence": evidence_list[:6],
            "bull_case": strengths or ["长期质地较为扎实"],
            "bear_case": risks or ["估值与宏观周期扰动"],
            "risks": risks or ["模型覆盖度受限风险"],
            "data_quality": data_quality_info,
            "key_metrics": key_metrics,
            "strengths": strengths,
            "risks": risks,
            "reasoning": reasoning,
            "_raw_reasoning": {"scores": scores, "raw": raw},
        }
        if mode is InvestorMode.SHADOW:
            try:
                evaluation = evaluate_ticker(profile_key, ticker, end_date)
                new = to_analyst_result(evaluation)
                data.setdefault("investor_shadow", {}).setdefault(agent_id, {})[ticker] = {
                    "legacy": {"factor_scores": scores, "signal": signal,
                               "confidence": confidence, "coverage": coverage,
                               "key_metrics": key_metrics, "strengths": strengths, "risks": risks},
                    "new": new,
                    "signal_changed": signal != new["signal"],
                    "confidence_changed": confidence != new["confidence"],
                }
            except Exception as exc:  # Shadow research must never replace production output.
                logger.debug("Pilot shadow evaluation failed for %s", ticker, exc_info=True)
                data.setdefault("investor_shadow", {}).setdefault(agent_id, {})[ticker] = {
                    "legacy": {"factor_scores": scores, "signal": signal,
                               "confidence": confidence, "coverage": coverage},
                    "new_error": type(exc).__name__,
                }
        progress.update_status(agent_id, ticker, "Done", analysis=reasoning)

    data["analyst_signals"][agent_id] = results
    if state["metadata"].get("show_reasoning"):
        show_agent_reasoning(results, profile.name)
    progress.update_status(agent_id, None, "Done")
    return {"messages": [HumanMessage(content=json.dumps(results, ensure_ascii=False), name=agent_id)], "data": data}


AGENTS = {key: partial(investor_agent, profile_key=key) for key in PROFILES}
