"""Service layer for Research Mode and Shadow Engine APIs.

Connects FastAPI backend directly to DataService, FactorEngine, StrategyEvaluator,
and TemporalCatalog. Does NOT shell out to CLI or invoke external LLMs.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
import logging
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from app.backend.models.research_schemas import (
    ConfidenceBreakdownDTO,
    CorpusHealthSummaryDTO,
    FactorContributionDTO,
    InvestorDetailDTO,
    LegacyComparisonDTO,
    ProductionDecisionDTO,
    ShadowInvestorCardDTO,
    SignalExplanationDTO,
    SnapshotItemDTO,
    StockResearchOverviewDTO,
)
from src.agents.a_share_investors import (
    PROFILES as LEGACY_PROFILES,
    _build_key_metrics,
    _build_strengths_and_risks,
    _decision as legacy_decision,
    _factors as legacy_factors,
)
from src.cli.metadata import stock_names
from src.cli.shadow_renderer import FACTOR_NAMES_CN, ROLE_NAMES_CN
from src.investors.collector import TemporalCatalog
from src.investors.monitoring import generate_corpus_summary
from src.investors.profiles import SHADOW_PROFILES, get_profile
from src.investors.runtime import evaluate_ticker, to_analyst_result
from src.tools.api import get_financial_metrics, get_prices

logger = logging.getLogger(__name__)

NOT_READY_PROFILES: dict[str, dict[str, str]] = {
    "wang_yawei": {
        "name": "王亚伟",
        "reason": "缺少重组重仓、筹码集中度与席位流向数据 (Missing restructuring / flow data)",
        "lens": "估值、盈利变化与趋势",
    },
    "lin_yuan": {
        "name": "林园",
        "reason": "缺少细分垄断壁垒、成瘾性产品与自主定价权量化代理 (Missing monopoly / pricing power proxy)",
        "lens": "持续盈利、成长与现金创造",
    },
}

CATALOG_PATH = Path("docs/baselines/shadow/live/temporal_catalog.json")

SHADOW_ORDER: tuple[str, ...] = (
    "zhang_kun",
    "feng_liu",
    "fu_pengbo",
    "duan_yongping",
    "deng_xiaofeng",
    "zhu_shaoxing",
    "liu_yanchun",
    "xie_zhiyu",
    "dong_chengfei",
    "chen_guangming",
)

SIGNAL_DISPLAY = {
    "bullish": "↑ 看多 (bullish)",
    "neutral": "— 中性 (neutral)",
    "bearish": "↓ 看空 (bearish)",
}

ACTION_DISPLAY = {
    "buy": "买入 (BUY)",
    "short": "做空 (SHORT)",
    "hold": "观望 (HOLD)",
}


class ResearchService:
    @staticmethod
    def _validate_ticker(ticker: str) -> str:
        clean = ticker.strip().upper()
        if clean.startswith(("SH", "SZ")):
            clean = clean[2:]
        if not (clean.isdigit() and len(clean) == 6):
            raise HTTPException(status_code=400, detail=f"无效的股票代码格式: {ticker} (应为6位数字代码)")
        return clean

    @classmethod
    def _resolve_stock_name(cls, ticker: str) -> str:
        names = stock_names([ticker])
        return names.get(ticker) or f"A股 {ticker}"

    @classmethod
    def _get_catalog(cls) -> TemporalCatalog:
        return TemporalCatalog.load_or_create(CATALOG_PATH)

    @classmethod
    def _evaluate_legacy_safely(cls, ticker: str, end_date: str, profile_key: str) -> dict[str, Any]:
        """Compute legacy signal and metrics without invoking LLM."""
        start_date = (date.fromisoformat(end_date) - timedelta(days=183)).isoformat()
        try:
            metrics = get_financial_metrics(ticker, end_date, period="ttm", limit=1)
        except Exception:
            metrics = []
        try:
            prices = get_prices(ticker, start_date, end_date)
        except Exception:
            prices = []

        if profile_key not in LEGACY_PROFILES:
            return {"signal": "neutral", "confidence": 0.0, "key_metrics": {}, "strengths": [], "risks": []}

        profile = LEGACY_PROFILES[profile_key]
        if metrics:
            scores, raw = legacy_factors(metrics[0], prices)
            signal, confidence, coverage, _ = legacy_decision(profile, scores)
            key_metrics = _build_key_metrics(profile, raw)
            strengths, risks = _build_strengths_and_risks(profile, scores)
            return {
                "signal": signal,
                "confidence": confidence,
                "coverage": coverage,
                "key_metrics": key_metrics,
                "strengths": strengths,
                "risks": risks,
            }
        return {
            "signal": "neutral",
            "confidence": 0.0,
            "coverage": 0.0,
            "key_metrics": {},
            "strengths": [],
            "risks": [],
        }

    @classmethod
    def _build_signal_checks(cls, explanation: Any) -> list[str]:
        if not explanation:
            return []
        gate_id = getattr(explanation, "gate_id", None) or (explanation.get("gate_id") if isinstance(explanation, dict) else None)
        gate_passed = getattr(explanation, "gate_passed", None) if not isinstance(explanation, dict) else explanation.get("gate_passed")
        gate_inputs = getattr(explanation, "gate_inputs", {}) if not isinstance(explanation, dict) else explanation.get("gate_inputs", {})

        checks = []
        if gate_id == "low_expectation_proxy_and_operating_improvement":
            proxy = gate_inputs.get("low_expectation_proxy")
            if proxy is not None:
                ok = float(proxy) > 0
                checks.append(f"{'✓' if ok else '✗'} 低预期代理{'成立' if ok else '未成立'} (score: {float(proxy):+.3f})")
            else:
                checks.append("✗ 低预期代理数据缺失，无法核验该门槛")
            mean_val = gate_inputs.get("operating_improvement_mean")
            if mean_val is not None:
                mf = float(mean_val)
                if mf >= 0.15:
                    checks.append(f"✓ 经营改善证据成立 (均值: {mf:+.3f} >= +0.150)")
                elif mf <= -0.20:
                    checks.append(f"✗ 经营证据恶化 (均值: {mf:+.3f} <= -0.200)")
                else:
                    checks.append(f"✗ 经营改善证据不足 (均值: {mf:+.3f} < +0.150)")
            else:
                checks.append("✗ 经营改善证据缺失，无法核验该门槛")
        elif gate_id == "long_term_quality_core_evidence":
            checks.append(f"{'✓' if gate_passed else '✗'} 核心经营质量因子完备性{'达标' if gate_passed else '不足'}")
        elif gate_id == "growth_quality_not_deteriorating":
            mean_val = gate_inputs.get("growth_evidence_mean")
            if mean_val is not None:
                mf = float(mean_val)
                checks.append(f"{'✓' if gate_passed else '✗'} 成长动能{'未恶化' if gate_passed else '显著恶化'} (均值: {mf:+.3f})")
            else:
                checks.append(f"{'✓' if gate_passed else '✗'} 成长质量门槛检验{'通过' if gate_passed else '未通过'}")
        elif gate_id:
            checks.append(f"{'✓' if gate_passed else '✗'} 策略门槛检验: {gate_id} ({'通过' if gate_passed else '未通过'})")
        return checks

    @classmethod
    def get_stock_overview(cls, ticker: str, as_of: str | None = None) -> StockResearchOverviewDTO:
        clean_ticker = cls._validate_ticker(ticker)
        stock_name = cls._resolve_stock_name(clean_ticker)

        catalog = cls._get_catalog()
        latest_entry = catalog.find_latest_entry(clean_ticker)

        as_of_str = as_of or (latest_entry.as_of if latest_entry else datetime.now(timezone.utc).isoformat())
        end_date = as_of_str[:10]
        market_data_date = latest_entry.market_data_date if latest_entry else end_date
        snapshot_id = latest_entry.snapshot_id if latest_entry else None
        quality_status = latest_entry.quality_status if latest_entry else "HEALTHY"

        # 1. 10 SHADOW Investor Cards
        investor_cards: list[ShadowInvestorCardDTO] = []
        for pid in SHADOW_ORDER:
            prof = get_profile(pid)
            lens = getattr(prof, "description", "")

            # Check if pre-evaluated in latest catalog entry
            summary = latest_entry.shadow_evaluations.get(pid) if latest_entry else None
            if summary:
                investor_cards.append(ShadowInvestorCardDTO(
                    profile_id=pid,
                    display_name=prof.display_name,
                    profile_version=prof.version,
                    lens=lens,
                    signal=summary.signal,
                    signal_display=SIGNAL_DISPLAY.get(summary.signal, summary.signal),
                    confidence=float(summary.confidence),
                    strategy_score=float(summary.strategy_score) if summary.strategy_score is not None else None,
                    strategy_evidence_coverage=float(summary.strategy_evidence_coverage),
                    core_coverage=float(summary.strategy_evidence_coverage),
                    supporting_coverage=float(summary.implemented_factor_coverage),
                    implemented_factor_coverage=float(summary.implemented_factor_coverage),
                    status="READY",
                ))
            else:
                # Live point-in-time factor evaluation
                try:
                    eval_res = evaluate_ticker(pid, clean_ticker, end_date)
                    investor_cards.append(ShadowInvestorCardDTO(
                        profile_id=pid,
                        display_name=prof.display_name,
                        profile_version=prof.version,
                        lens=lens,
                        signal=eval_res.signal,
                        signal_display=SIGNAL_DISPLAY.get(eval_res.signal, eval_res.signal),
                        confidence=float(eval_res.confidence),
                        strategy_score=float(eval_res.strategy_score) if eval_res.strategy_score is not None else None,
                        strategy_evidence_coverage=float(eval_res.strategy_evidence_coverage),
                        core_coverage=float(eval_res.core_coverage),
                        supporting_coverage=float(eval_res.supporting_coverage),
                        implemented_factor_coverage=float(eval_res.implemented_factor_coverage),
                        status="READY",
                    ))
                except Exception as exc:
                    logger.warning("Dynamic evaluation failed for %s on %s: %s", pid, clean_ticker, exc)
                    investor_cards.append(ShadowInvestorCardDTO(
                        profile_id=pid,
                        display_name=prof.display_name,
                        profile_version=prof.version,
                        lens=lens,
                        signal="neutral",
                        signal_display=SIGNAL_DISPLAY["neutral"],
                        confidence=0.0,
                        strategy_score=None,
                        status="READY",
                    ))

        # 2. NOT_READY Investor Cards (王亚伟, 林园)
        not_ready_cards: list[ShadowInvestorCardDTO] = []
        for pid, info in NOT_READY_PROFILES.items():
            not_ready_cards.append(ShadowInvestorCardDTO(
                profile_id=pid,
                display_name=info["name"],
                profile_version="legacy-only",
                lens=info["lens"],
                signal="neutral",
                signal_display="NOT READY",
                confidence=0.0,
                strategy_score=None,
                status="NOT_READY",
                not_ready_reason=info["reason"],
            ))

        # 3. Production Decision (Explicitly from LEGACY)
        # We aggregate legacy opinions across investors
        legacy_signals = [
            cls._evaluate_legacy_safely(clean_ticker, end_date, pid)
            for pid in list(SHADOW_ORDER[:3])
        ]
        bullish_count = sum(1 for s in legacy_signals if s["signal"] == "bullish")
        bearish_count = sum(1 for s in legacy_signals if s["signal"] == "bearish")
        action = "buy" if bullish_count > bearish_count else "short" if bearish_count > bullish_count else "hold"
        mean_conf = sum(s["confidence"] for s in legacy_signals) / max(len(legacy_signals), 1)

        production_decision = ProductionDecisionDTO(
            mode="LEGACY",
            action=action,
            action_display=ACTION_DISPLAY.get(action, action.upper()),
            confidence=round(mean_conf, 1),
            quantity=15 if action != "hold" else 0,
            reasoning="生产交易决策依据现有 Production LEGACY 策略规则生成，SHADOW 研究结果与模型输出被严格隔离。",
        )

        return StockResearchOverviewDTO(
            ticker=clean_ticker,
            stock_name=stock_name,
            as_of=as_of_str,
            market_data_date=market_data_date,
            snapshot_id=snapshot_id,
            snapshot_status="PRESENT" if latest_entry else "LIVE_EVALUATED",
            data_quality=quality_status,
            production_decision=production_decision,
            investor_cards=investor_cards,
            not_ready_cards=not_ready_cards,
        )

    @classmethod
    def get_investor_detail(cls, ticker: str, profile_id: str, as_of: str | None = None) -> InvestorDetailDTO:
        clean_ticker = cls._validate_ticker(ticker)
        as_of_date = as_of or datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
        end_date = as_of_date[:10]

        # Handle NOT_READY profiles
        if profile_id in NOT_READY_PROFILES:
            info = NOT_READY_PROFILES[profile_id]
            legacy_eval = cls._evaluate_legacy_safely(clean_ticker, end_date, profile_id)
            return InvestorDetailDTO(
                profile_id=profile_id,
                display_name=info["name"],
                profile_version="legacy-only",
                description=f"{info['name']}策略原型（待迁移）",
                time_horizon="—",
                signal="neutral",
                signal_display="NOT READY",
                confidence=0.0,
                confidence_semantics="该策略原型暂未完成因子重构与 Shadow 就绪验证，仅保留 Legacy 运行。",
                status="NOT_READY",
                not_ready_reason=info["reason"],
                legacy_comparison=LegacyComparisonDTO(
                    legacy_signal=legacy_eval["signal"],
                    legacy_signal_display=SIGNAL_DISPLAY.get(legacy_eval["signal"], legacy_eval["signal"]),
                    legacy_confidence=legacy_eval["confidence"],
                    legacy_key_metrics=legacy_eval["key_metrics"],
                    legacy_strengths=legacy_eval["strengths"],
                    legacy_risks=legacy_eval["risks"],
                    new_signal="NOT_READY",
                    new_signal_display="NOT READY",
                    new_confidence=0.0,
                    signal_changed=False,
                    confidence_changed=False,
                    core_difference="新模型尚未迁移，暂无 New 因子输出。",
                ),
            )

        if profile_id not in SHADOW_PROFILES:
            raise HTTPException(status_code=404, detail=f"未找到该投资人策略原型: {profile_id}")

        profile = get_profile(profile_id)

        # 1. Run StrategyEvaluator
        eval_res = evaluate_ticker(profile_id, clean_ticker, end_date)
        res_dict = to_analyst_result(eval_res)

        # 2. Factor contributions DTOs
        factor_contributions: list[FactorContributionDTO] = []
        for fc in res_dict.get("factor_contributions", []):
            fid = fc.get("factor_id", "")
            factor_contributions.append(FactorContributionDTO(
                factor_id=fid,
                display_name=FACTOR_NAMES_CN.get(fid, fid),
                version=fc.get("version", "v1"),
                role=fc.get("role", "core"),
                role_display=ROLE_NAMES_CN.get(fc.get("role", "core"), fc.get("role", "core")),
                score=float(fc["score"]) if fc.get("score") is not None else None,
                weight=float(fc.get("weight", 0)),
                weighted_contribution=float(fc["weighted_contribution"]) if fc.get("weighted_contribution") is not None else None,
                status=fc.get("status", "AVAILABLE"),
                factor_type=fc.get("factor_type", "continuous"),
                raw_value=float(fc["raw_value"]) if fc.get("raw_value") is not None else None,
                raw_unit=str(fc.get("raw_unit", "fraction")),
                limitations=list(fc.get("limitations") or []),
            ))

        # 3. Signal explanation DTO
        sig_exp = res_dict.get("signal_explanation")
        signal_explanation_dto = None
        if sig_exp:
            signal_explanation_dto = SignalExplanationDTO(
                signal=sig_exp["signal"],
                signal_display=SIGNAL_DISPLAY.get(sig_exp["signal"], sig_exp["signal"]),
                strategy_score=float(sig_exp["strategy_score"]) if sig_exp.get("strategy_score") is not None else None,
                bullish_threshold=float(sig_exp["bullish_threshold"]),
                bearish_threshold=float(sig_exp["bearish_threshold"]),
                policy_style=sig_exp["policy_style"],
                gate_id=sig_exp.get("gate_id"),
                gate_passed=sig_exp.get("gate_passed"),
                gate_checks=cls._build_signal_checks(sig_exp),
                reason_code=sig_exp.get("reason_code", "unknown"),
                signal_reason=res_dict.get("signal_reason", ""),
            )

        # 4. Confidence breakdown DTO
        conf_comp = res_dict.get("confidence_components")
        confidence_breakdown_dto = None
        if conf_comp:
            confidence_breakdown_dto = ConfidenceBreakdownDTO(
                final_confidence=float(conf_comp["final_confidence"]),
                maximum_possible=float(conf_comp.get("maximum_possible", 90.0)),
                core_coverage=float(conf_comp.get("core_coverage", 0.0)),
                supporting_coverage=float(conf_comp.get("supporting_coverage", 0.0)),
                optional_coverage=float(conf_comp.get("optional_coverage", 0.0)),
                coverage_score=float(conf_comp.get("coverage_score", 0.0)),
                evidence_quality=float(conf_comp.get("evidence_quality", 0.0)),
                unconstrained_confidence=float(conf_comp.get("unconstrained_confidence", 0.0)),
                strategy_evidence_cap=float(conf_comp["strategy_evidence_cap"]) if conf_comp.get("strategy_evidence_cap") is not None else None,
                proxy_cap=float(conf_comp["proxy_cap"]) if conf_comp.get("proxy_cap") is not None else None,
                critical_capability_cap=float(conf_comp["critical_capability_cap"]) if conf_comp.get("critical_capability_cap") is not None else None,
                active_cap_name=conf_comp.get("active_cap_name"),
                active_cap_value=float(conf_comp["active_cap_value"]) if conf_comp.get("active_cap_value") is not None else None,
                applied_caps={k: float(v) for k, v in conf_comp.get("applied_caps", {}).items()},
            )

        # 5. Legacy comparison DTO
        legacy_eval = cls._evaluate_legacy_safely(clean_ticker, end_date, profile_id)
        leg_sig = legacy_eval["signal"]
        new_sig = res_dict["signal"]
        leg_conf = legacy_eval["confidence"]
        new_conf = res_dict["confidence"]

        legacy_comparison_dto = LegacyComparisonDTO(
            legacy_signal=leg_sig,
            legacy_signal_display=SIGNAL_DISPLAY.get(leg_sig, leg_sig),
            legacy_confidence=leg_conf,
            legacy_key_metrics=legacy_eval["key_metrics"],
            legacy_strengths=legacy_eval["strengths"],
            legacy_risks=legacy_eval["risks"],
            new_signal=new_sig,
            new_signal_display=SIGNAL_DISPLAY.get(new_sig, new_sig),
            new_confidence=new_conf,
            signal_changed=leg_sig != new_sig,
            confidence_changed=leg_conf != new_conf,
            core_difference="Legacy 基于固定财务指标打分规则；New 模型基于连续因子引擎、多维证据覆盖率与策略门槛验证。",
        )

        return InvestorDetailDTO(
            profile_id=profile_id,
            display_name=profile.display_name,
            profile_version=profile.version,
            description=profile.description,
            time_horizon=profile.time_horizon,
            signal=new_sig,
            signal_display=SIGNAL_DISPLAY.get(new_sig, new_sig),
            confidence=new_conf,
            confidence_semantics=res_dict.get("confidence_semantics", "数据支撑与当前策略结论可信程度；不是上涨概率、盈利概率或交易胜率"),
            strategy_score=float(res_dict["strategy_score"]) if res_dict.get("strategy_score") is not None else None,
            data_coverage=res_dict.get("data_coverage", {}),
            factor_contributions=factor_contributions,
            signal_explanation=signal_explanation_dto,
            confidence_breakdown=confidence_breakdown_dto,
            strengths=res_dict.get("strengths", []),
            risks=res_dict.get("risks", []),
            known_missing_dimensions=res_dict.get("known_missing_dimensions", []),
            limitations=res_dict.get("limitations", []),
            legacy_comparison=legacy_comparison_dto,
            status="READY",
        )

    @classmethod
    def get_corpus_summary(cls) -> CorpusHealthSummaryDTO:
        if not CATALOG_PATH.exists():
            return CorpusHealthSummaryDTO(
                generated_at=datetime.now(timezone.utc).isoformat(),
                snapshot_count=0,
                ticker_count=0,
                date_range=None,
                health_status="Empty Corpus",
            )
        report = generate_corpus_summary(CATALOG_PATH)
        warnings_present = bool(
            report.data_drift_warnings
            or report.distribution_warnings
            or report.factor_drift_warnings
            or report.partial_runs_count > 0
        )
        return CorpusHealthSummaryDTO(
            generated_at=report.generated_at.isoformat(),
            snapshot_count=report.snapshot_count,
            ticker_count=report.ticker_count,
            date_range=list(report.date_range) if report.date_range else None,
            partial_runs_count=report.partial_runs_count,
            degraded_snapshots_count=report.degraded_snapshots_count,
            signal_distribution=report.signal_distribution,
            confidence_distribution=report.confidence_distribution,
            data_drift_warnings=[w.model_dump(mode="json") for w in report.data_drift_warnings],
            factor_drift_warnings=[w.model_dump(mode="json") for w in report.factor_drift_warnings],
            distribution_warnings=[w.model_dump(mode="json") for w in report.distribution_warnings],
            health_status="Warnings Detected" if warnings_present else "Healthy",
        )

    @classmethod
    def get_corpus_snapshots(cls, ticker: str | None = None, limit: int = 50) -> list[SnapshotItemDTO]:
        catalog = cls._get_catalog()
        entries = catalog.entries
        if ticker:
            clean = ticker.strip()
            entries = [e for e in entries if e.ticker == clean]

        results = []
        for e in reversed(entries[-limit:]):
            evals = {}
            for pid, s in e.shadow_evaluations.items():
                evals[pid] = {
                    "signal": s.signal,
                    "confidence": s.confidence,
                    "strategy_score": s.strategy_score,
                    "strategy_evidence_coverage": s.strategy_evidence_coverage,
                    "implemented_factor_coverage": s.implemented_factor_coverage,
                }
            results.append(SnapshotItemDTO(
                snapshot_id=e.snapshot_id,
                ticker=e.ticker,
                captured_at=e.captured_at,
                as_of=e.as_of,
                market_data_date=e.market_data_date,
                quality_status=e.quality_status,
                retention_tags=e.retention_tags,
                evaluation_complete=e.evaluation_complete,
                run_status=getattr(e, "run_status", "COMPLETE"),
                evaluations_summary=evals,
            ))
        return results

    @classmethod
    def get_corpus_snapshot_detail(cls, snapshot_id: str) -> dict[str, Any]:
        catalog = cls._get_catalog()
        entry = next((e for e in catalog.entries if e.snapshot_id == snapshot_id), None)
        if not entry:
            raise HTTPException(status_code=404, detail=f"未找到 Snapshot: {snapshot_id}")

        evaluations = {}
        for pid, s in entry.shadow_evaluations.items():
            prof = get_profile(pid)
            evaluations[pid] = {
                "display_name": prof.display_name,
                "version": prof.version,
                "signal": s.signal,
                "confidence": s.confidence,
                "strategy_score": s.strategy_score,
                "strategy_evidence_coverage": s.strategy_evidence_coverage,
                "implemented_factor_coverage": s.implemented_factor_coverage,
                "known_missing_dimensions": s.known_missing_dimensions,
                "proxy_dependence": s.proxy_dependence,
                "quality_status": s.quality_status,
            }

        return {
            "snapshot_id": entry.snapshot_id,
            "ticker": entry.ticker,
            "stock_name": cls._resolve_stock_name(entry.ticker),
            "captured_at": entry.captured_at,
            "as_of": entry.as_of,
            "market_data_date": entry.market_data_date,
            "quality_status": entry.quality_status,
            "retention_tags": entry.retention_tags,
            "capability_coverage": entry.capability_coverage,
            "evaluation_complete": entry.evaluation_complete,
            "run_status": getattr(entry, "run_status", "COMPLETE"),
            "evaluations": evaluations,
        }
