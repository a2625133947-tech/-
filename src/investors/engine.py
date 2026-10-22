"""Deterministic, profile-specific strategy evaluation over versioned factors."""

from __future__ import annotations

from decimal import Decimal

from src.data.domain import Quality, Unit
from src.factors.contracts import FactorResult, FactorStatus, FactorType, clamp_score
from src.factors.engine import FactorRegistry, default_registry
from src.investors.contracts import (
    ConfidenceComponents, FactorContribution, InvestorProfile, SignalExplanation,
    StrategyEvaluationResult, UsedFactor,
)
from src.investors.profiles import PROXY_ID

D = Decimal
_VALID = {FactorStatus.AVAILABLE, FactorStatus.PARTIAL, FactorStatus.DEGRADED}
_QUALITY = {Quality.VALIDATED: D(1), Quality.UNVERIFIED: D("0.85"),
            Quality.DEGRADED: D("0.60")}


def low_expectation_proxy(factors: dict[str, FactorResult]) -> FactorResult:
    """Valuation and price-pressure proxy; never a claim about actual expectations."""
    valuation = [factors.get(key) for key in ("valuation_percentile", "valuation_level")]
    valuation = [item for item in valuation if item and item.status in _VALID]
    pressure = [factors.get(key) for key in ("drawdown_6m", "momentum_1m")]
    pressure = [item for item in pressure if item and item.status in _VALID]
    source = next(iter(factors.values()))
    base = dict(factor_id=PROXY_ID, version="v1", factor_type=FactorType.PROXY,
                as_of=source.as_of, window="latest valuation and adjusted price",
                raw_unit=Unit.NONE,
                limitations=("仅为估值与价格压制代理，不代表真实市场预期或分析师预测",))
    if not valuation or not pressure:
        return FactorResult(**base, status=FactorStatus.UNAVAILABLE, coverage=D(0),
                            reason="need valuation and adjusted price-pressure evidence")
    cheap = sum((item.normalized_score for item in valuation), D(0)) / D(len(valuation))
    pressed = sum((-item.normalized_score for item in pressure), D(0)) / D(len(pressure))
    score = clamp_score(D("0.6") * cheap + D("0.4") * pressed)
    consumed = valuation + pressure
    inputs = tuple(point for item in consumed for point in item.inputs)
    quality = min((item.quality for item in consumed if item.quality is not None),
                  key=_QUALITY.__getitem__, default=None)
    coverage = D(len(consumed)) / D(4)
    return FactorResult(**base, raw_value=score, normalized_score=score,
                        status=(FactorStatus.DEGRADED if quality is Quality.DEGRADED else
                                FactorStatus.PARTIAL if coverage < 1 else FactorStatus.AVAILABLE),
                        quality=quality, coverage=coverage, inputs=inputs,
                        provenance=tuple(p for point in inputs
                                         for p in (point.provenance, *point.source_inputs)))


class StrategyEvaluator:
    def __init__(self, registry: FactorRegistry | None = None):
        self.registry = registry or default_registry()

    def evaluate(self, profile: InvestorProfile,
                 factors: dict[str, FactorResult]) -> StrategyEvaluationResult:
        if not factors or len({result.as_of for result in factors.values()}) != 1:
            raise ValueError("factor results must share one as_of")
        for factor_id in profile.factor_ids:
            if factor_id == PROXY_ID:
                continue
            registered = self.registry.get(factor_id)
            if registered.version != profile.factor_versions[factor_id]:
                raise ValueError(f"factor version mismatch: {factor_id}")
        selected = dict(factors)
        if PROXY_ID in profile.factor_ids:
            selected[PROXY_ID] = low_expectation_proxy(factors)
        missing = set(profile.factor_ids) - set(selected)
        if missing:
            raise ValueError(f"factor results missing: {sorted(missing)}")
        used = []
        for factor_id in profile.factor_ids:
            result = selected[factor_id]
            if result.version != profile.factor_versions[factor_id]:
                raise ValueError(f"factor result version mismatch: {factor_id}")
            used.append(UsedFactor(factor_id=factor_id, version=result.version,
                score=result.normalized_score if result.status in _VALID else None,
                status=result.status, quality=result.quality,
                coverage=result.coverage, weight=profile.factor_weights[factor_id],
                role=profile.role(factor_id), factor_type=result.factor_type,
                limitations=result.limitations))

        def coverage(ids):
            return (sum((selected[key].coverage if selected[key].status in _VALID else D(0)
                         for key in ids), D(0)) / D(len(ids))) if ids else D(1)

        core = coverage(profile.core_factors)
        supporting = coverage(profile.supporting_factors)
        optional = coverage(profile.optional_factors)
        total = coverage(profile.factor_ids)
        implemented_coverage = total
        total_dims = len(profile.factor_ids) + len(profile.known_missing_dimensions)
        strategy_evidence_coverage = (
            (total * D(len(profile.factor_ids)) / D(total_dims))
            if total_dims > 0
            else total
        )
        observed = [(item.weight, item.score) for item in used if item.score is not None]
        active_weight = sum((weight for weight, _ in observed), D(0))
        strategy_score = (sum((weight * score for weight, score in observed), D(0)) /
                          active_weight) if observed else None
        signal = self._signal(profile, selected, strategy_score)
        signal_reason = self._signal_reason(profile, selected, strategy_score, signal)
        signal_explanation = self._signal_explanation(profile, selected, strategy_score, signal)
        contributions = []
        active_contribution_ids = [item.factor_id for item in used if item.score is not None]
        accumulated_contribution = D(0)
        for item in used:
            factor_result = selected[item.factor_id]
            weighted_contribution = None
            if item.score is not None and active_weight:
                if item.factor_id == active_contribution_ids[-1]:
                    # Decimal division can leave a final 1e-28 residual. Put
                    # that accounting remainder on the final active item so
                    # the published contributions reconcile exactly to score.
                    weighted_contribution = strategy_score - accumulated_contribution
                else:
                    weighted_contribution = item.weight * item.score / active_weight
                    accumulated_contribution += weighted_contribution
            contributions.append(FactorContribution(
                factor_id=item.factor_id, version=item.version,
                raw_value=factor_result.raw_value, raw_unit=factor_result.raw_unit,
                score=item.score, weight=item.weight,
                weighted_contribution=weighted_contribution,
                role=item.role, status=item.status, factor_type=item.factor_type,
                inputs=factor_result.inputs, provenance=factor_result.provenance))

        evidence = [selected[item.factor_id] for item in used if item.score is not None]
        quality = (sum((_QUALITY.get(item.quality, D("0.7")) *
                        (D("0.85") if item.status is FactorStatus.PARTIAL else D(1))
                        for item in evidence), D(0)) / D(len(evidence))) if evidence else D(0)
        cp = profile.confidence_policy
        coverage_score = cp.core_weight * core + cp.supporting_weight * supporting + cp.optional_weight * optional
        base_confidence = D(cp.maximum) * coverage_score * quality
        audit_trail = [
            f"Base: maximum({cp.maximum}) * coverage({coverage_score:.3f}) * quality({quality:.3f}) = {base_confidence:.1f}"
        ]

        limitations = list(profile.limitations)
        missing_policy = profile.missing_data_policy
        applied_caps: dict[str, D] = {}

        if core < 1:
            applied_caps["core_missing_cap"] = D(missing_policy.core_missing_cap)
            limitations.append("核心因子不完整，置信度受限")
        if any(selected[key].status is FactorStatus.INSUFFICIENT_HISTORY
               for key in profile.core_factors):
            applied_caps["history_missing_cap"] = D(missing_policy.history_missing_cap)
            limitations.append("核心因子历史长度不足")
        if core < profile.minimum_factor_coverage:
            applied_caps["minimum_coverage_cap"] = D(40)

        critical_evidence_absent = []
        for capability in sorted(profile.critical_capabilities, key=lambda item: item.value):
            related = [key for key in profile.core_factors if key != PROXY_ID and
                       capability in self.registry.get(key).required_capabilities]
            if related and all(selected[key].status in
                               (FactorStatus.UNAVAILABLE, FactorStatus.NOT_AVAILABLE_AS_OF)
                               for key in related):
                critical_evidence_absent.append(capability.value)
        if PROXY_ID in profile.core_factors and selected[PROXY_ID].status is FactorStatus.UNAVAILABLE:
            critical_evidence_absent.append("low_expectation_proxy")
        if critical_evidence_absent:
            applied_caps["critical_capability_cap"] = D(35)
            limitations.append("关键能力证据不可用：" + "、".join(critical_evidence_absent))

        if missing_policy.proxy_cap is not None:
            applied_caps["proxy_cap"] = D(missing_policy.proxy_cap)
            limitations.extend(missing_policy.specific_limitations)
        elif any(selected[key].status not in _VALID for key in profile.core_factors):
            limitations.extend(missing_policy.specific_limitations)

        # Strategy evidence cap based on known_missing_dimensions
        if profile.known_missing_dimensions:
            n_declared = len(profile.factor_ids)
            n_total = n_declared + len(profile.known_missing_dimensions)
            evidence_cap = D("40") + D("50") * (D(n_declared) / D(n_total))
            applied_caps["strategy_evidence_cap"] = round(evidence_cap, 1)

        confidence = base_confidence
        active_cap_name = None
        active_cap_value = None

        if applied_caps:
            min_cap_name, min_cap_val = min(applied_caps.items(), key=lambda x: x[1])
            if min_cap_val < confidence:
                confidence = min_cap_val
                active_cap_name = min_cap_name
                active_cap_value = float(min_cap_val)
                audit_trail.append(f"Cap applied: {min_cap_name}={min_cap_val:.1f}")

        degraded_penalty_applied = False
        if any(item.status is FactorStatus.DEGRADED for item in used):
            degraded_penalty_applied = True
            confidence *= D("0.85")
            audit_trail.append("Degraded data penalty: 0.85 multiplier applied")

        final_confidence = round(float(max(D(0), min(D(100), confidence))), 1)
        audit_trail.append(f"Final confidence: {final_confidence}")

        confidence_components = ConfidenceComponents(
            maximum_possible=float(cp.maximum),
            core_coverage=float(core),
            supporting_coverage=float(supporting),
            optional_coverage=float(optional),
            coverage_score=float(coverage_score),
            evidence_quality=float(quality),
            unconstrained_confidence=float(base_confidence),
            core_missing_cap=float(missing_policy.core_missing_cap) if "core_missing_cap" in applied_caps else None,
            history_missing_cap=float(missing_policy.history_missing_cap) if "history_missing_cap" in applied_caps else None,
            minimum_coverage_cap=40.0 if "minimum_coverage_cap" in applied_caps else None,
            critical_capability_cap=35.0 if "critical_capability_cap" in applied_caps else None,
            proxy_cap=float(missing_policy.proxy_cap) if "proxy_cap" in applied_caps else None,
            strategy_evidence_cap=float(applied_caps["strategy_evidence_cap"]) if "strategy_evidence_cap" in applied_caps else None,
            applied_caps={k: float(v) for k, v in applied_caps.items()},
            active_cap_name=active_cap_name,
            active_cap_value=active_cap_value,
            degraded_penalty_applied=degraded_penalty_applied,
            degraded_penalty_multiplier=0.85 if degraded_penalty_applied else 1.0,
            final_confidence=final_confidence,
            audit_trail=audit_trail,
        )

        interpretations = {}
        strengths, risks = [], []
        for item in used:
            if item.score is None:
                continue
            rules = profile.interpretation_rules.get(item.factor_id)
            if rules:
                interpretations[item.factor_id] = rules[0] if item.score >= D("0.25") else (
                    rules[1] if item.score <= D("-0.25") else rules[2])
            if item.score >= D("0.25") and item.factor_id in profile.strength_rules:
                strengths.append(profile.strength_rules[item.factor_id])
            if item.score <= D("-0.25") and item.factor_id in profile.risk_rules:
                risks.append(profile.risk_rules[item.factor_id])
        if profile.signal_policy.style == "growth_quality":
            growth = [selected[key].normalized_score for key in
                      ("revenue_growth_yoy", "earnings_growth_yoy", "growth_acceleration")
                      if selected[key].status in _VALID]
            if growth and sum(growth, D(0)) / D(len(growth)) <= D("-0.25"):
                risks.append("成长质量冲突：盈利质量不能抵消明显的成长转弱")
        elif profile.signal_policy.style == "balanced_quality_growth":
            quality_vals = [selected[key].normalized_score for key in
                            ("profitability_quality", "cash_conversion")
                            if selected[key].status in _VALID]
            if any(v <= D("-0.25") for v in quality_vals):
                risks.append("成长质量冲突：高成长不能掩盖盈利质量或现金流恶化")
        elif profile.signal_policy.style == "value_turnaround":
            val_cheap = any(selected[key].normalized_score > 0 for key in
                            ("valuation_level", "valuation_percentile")
                            if selected[key].status in _VALID)
            op_bad = (selected.get("earnings_growth_yoy") and selected["earnings_growth_yoy"].normalized_score is not None
                      and selected["earnings_growth_yoy"].normalized_score <= D("-0.20")
                      and selected.get("margin_trend") and selected["margin_trend"].normalized_score is not None
                      and selected["margin_trend"].normalized_score <= D("-0.20"))
            if val_cheap and op_bad:
                risks.append("价值陷阱风险：估值折价但基本面尚未见修复拐点")
        elif profile.signal_policy.style == "consumer_quality_growth":
            rev = selected.get("revenue_growth_yoy")
            earn = selected.get("earnings_growth_yoy")
            if (rev and rev.normalized_score is not None and rev.normalized_score <= D("-0.20")
                    and earn and earn.normalized_score is not None and earn.normalized_score <= D("-0.20")):
                risks.append("消费动能冲突：高盈利质量面临终端需求收缩压力")
        elif profile.signal_policy.style == "growth_valuation_balance":
            ga = selected.get("growth_acceleration")
            earn = selected.get("earnings_growth_yoy")
            if (ga and ga.normalized_score is not None and ga.normalized_score <= D("-0.25")
                    and earn and earn.normalized_score is not None and earn.normalized_score <= 0):
                risks.append("成长减速风险：业务扩张斜率放缓压缩估值溢价")
        elif profile.signal_policy.style == "value_discipline_safety":
            bs = selected.get("balance_sheet_safety")
            if bs and bs.normalized_score is not None and bs.normalized_score <= D("-0.25"):
                risks.append("资产负债风险：债务杠杆超出防守安全边界")
        elif profile.signal_policy.style == "quality_value_cash":
            cc = selected.get("cash_conversion")
            if cc and cc.normalized_score is not None and cc.normalized_score <= D("-0.25"):
                risks.append("现金流质量冲突：高资本回报缺乏充沛自由现金流支撑")
        metrics = {}
        for factor_id in profile.key_metric_priority:
            result = selected[factor_id]
            if result.status not in _VALID or result.raw_value is None:
                continue
            label = ("低估值与价格压制代理" if factor_id == PROXY_ID else
                     self.registry.get(factor_id).display_name)
            metrics[factor_id] = {"label": label, "value": float(result.raw_value),
                                  "format": ("percent" if result.raw_unit is Unit.FRACTION else
                                             "ratio" if result.raw_unit is Unit.MULTIPLE else "score")}
        reasoning = (f"{profile.display_name}公开理念启发的项目策略原型：规则信号 {signal}，"
                     f"置信度 {confidence:.1f}%。"
                     + ("优势：" + "；".join(strengths) + "。" if strengths else "")
                     + ("风险：" + "；".join(risks) + "。" if risks else "")
                     + "局限：" + "；".join(limitations) + "。")
        return StrategyEvaluationResult(profile_id=profile.profile_id,
            profile_version=profile.version, strategy_score=strategy_score,
            signal=signal, signal_reason=signal_reason, confidence=final_confidence,
            confidence_components=confidence_components,
            used_factors=tuple(used), contributions=tuple(contributions),
            signal_explanation=signal_explanation,
            core_coverage=core, supporting_coverage=supporting, overall_coverage=total,
            known_missing_dimensions=profile.known_missing_dimensions,
            key_metrics=metrics, strengths=tuple(strengths), risks=tuple(risks),
            interpretations=interpretations, limitations=tuple(limitations), reasoning=reasoning)

    @staticmethod
    def _signal_explanation(profile, factors, score, signal):
        """Expose the deterministic threshold and profile gate used by _signal."""
        policy = profile.signal_policy
        gate_id = None
        gate_passed = None
        gate_inputs = {}
        reason_code = "threshold_neutral"
        threshold_relation = "between_thresholds"

        if score is None:
            reason_code = "no_strategy_score"
            threshold_relation = "no_score"
        elif policy.style == "long_term_quality":
            gate_id = "long_term_quality_core_evidence"
            gate_inputs = {key: factors[key].normalized_score
                           if factors[key].status in _VALID else None
                           for key in profile.core_factors}
            gate_passed = any(value is not None for value in gate_inputs.values())
            if not gate_passed:
                reason_code = "core_evidence_unavailable"
                threshold_relation = "gate_blocked"
        elif policy.style == "proxy_plus_improvement":
            gate_id = "low_expectation_proxy_and_operating_improvement"
            proxy = factors[PROXY_ID]
            gate_inputs[PROXY_ID] = (proxy.normalized_score
                                     if proxy.status in _VALID else None)
            proxy_ready = proxy.status in _VALID and proxy.normalized_score > 0
            improvements = [key for key in
                            ("growth_acceleration", "margin_trend", "earnings_growth_yoy")
                            if factors[key].status in _VALID]
            gate_inputs.update({key: factors[key].normalized_score for key in improvements})
            if not proxy_ready:
                gate_passed = False
                reason_code = "proxy_not_established"
                threshold_relation = "gate_blocked"
            elif not improvements:
                gate_passed = False
                reason_code = "improvement_evidence_unavailable"
                threshold_relation = "gate_blocked"
            else:
                mean = sum((factors[key].normalized_score for key in improvements), D(0)) / D(len(improvements))
                gate_inputs["operating_improvement_mean"] = mean
                gate_passed = mean >= D("0.15")
                if mean <= D("-0.20"):
                    reason_code = "operating_evidence_deteriorating"
                    threshold_relation = "profile_gate_bearish"
                elif not gate_passed:
                    reason_code = "improvement_below_gate"
                    threshold_relation = "gate_blocked"
        elif policy.style == "growth_quality":
            gate_id = "growth_quality_not_deteriorating"
            growth_ids = ("revenue_growth_yoy", "earnings_growth_yoy", "growth_acceleration")
            available = [key for key in growth_ids if factors[key].status in _VALID]
            gate_inputs.update({key: factors[key].normalized_score for key in available})
            if not available:
                gate_passed = False
                reason_code = "growth_evidence_unavailable"
                threshold_relation = "gate_blocked"
            else:
                mean = sum((factors[key].normalized_score for key in available), D(0)) / D(len(available))
                gate_inputs["growth_evidence_mean"] = mean
                gate_passed = mean > D("-0.25")
                if not gate_passed:
                    reason_code = "growth_gate_blocks_bullish"
                    threshold_relation = "growth_gate"
        elif policy.style == "value_turnaround":
            gate_id = "valuation_and_earnings_recovery"
            earn = factors.get("earnings_growth_yoy")
            margin = factors.get("margin_trend")
            val_lvl = factors.get("valuation_level")
            gate_inputs = {
                "earnings_growth_yoy": earn.normalized_score if earn and earn.status in _VALID else None,
                "margin_trend": margin.normalized_score if margin and margin.status in _VALID else None,
                "valuation_level": val_lvl.normalized_score if val_lvl and val_lvl.status in _VALID else None,
            }
            op_bad = (earn and earn.status in _VALID and earn.normalized_score <= D("-0.20") and
                      margin and margin.status in _VALID and margin.normalized_score <= D("-0.20"))
            val_expensive = val_lvl and val_lvl.status in _VALID and val_lvl.normalized_score <= D("-0.20")
            if op_bad:
                gate_passed = False
                reason_code = "operating_deterioration_blocks_turnaround"
                threshold_relation = "gate_blocked"
            elif val_expensive:
                gate_passed = False
                reason_code = "valuation_not_discounted"
                threshold_relation = "gate_blocked"
            else:
                gate_passed = True
        elif policy.style == "balanced_quality_growth":
            gate_id = "quality_not_failing"
            pq = factors.get("profitability_quality")
            cc = factors.get("cash_conversion")
            gate_inputs = {
                "profitability_quality": pq.normalized_score if pq and pq.status in _VALID else None,
                "cash_conversion": cc.normalized_score if cc and cc.status in _VALID else None,
            }
            weak_quality = ((pq and pq.status in _VALID and pq.normalized_score <= D("-0.25")) or
                            (cc and cc.status in _VALID and cc.normalized_score <= D("-0.25")))
            if weak_quality:
                gate_passed = False
                reason_code = "weak_quality_blocks_growth"
                threshold_relation = "gate_blocked"
            else:
                gate_passed = True
        elif policy.style == "consumer_quality_growth":
            gate_id = "growth_positive_gate"
            rev = factors.get("revenue_growth_yoy")
            earn = factors.get("earnings_growth_yoy")
            gate_inputs = {
                "revenue_growth_yoy": rev.normalized_score if rev and rev.status in _VALID else None,
                "earnings_growth_yoy": earn.normalized_score if earn and earn.status in _VALID else None,
            }
            contracting = (rev and rev.status in _VALID and rev.normalized_score <= D("-0.20") and
                           earn and earn.status in _VALID and earn.normalized_score <= D("-0.20"))
            if contracting:
                gate_passed = False
                reason_code = "revenue_contraction_blocks_bullish"
                threshold_relation = "gate_blocked"
            else:
                gate_passed = True
        elif policy.style == "growth_valuation_balance":
            gate_id = "growth_deceleration_gate"
            ga = factors.get("growth_acceleration")
            earn = factors.get("earnings_growth_yoy")
            gate_inputs = {
                "growth_acceleration": ga.normalized_score if ga and ga.status in _VALID else None,
                "earnings_growth_yoy": earn.normalized_score if earn and earn.status in _VALID else None,
            }
            decelerating = (ga and ga.status in _VALID and ga.normalized_score <= D("-0.25") and
                            earn and earn.status in _VALID and earn.normalized_score <= 0)
            if decelerating:
                gate_passed = False
                reason_code = "growth_deceleration_blocks_bullish"
                threshold_relation = "gate_blocked"
            else:
                gate_passed = True
        elif policy.style == "value_discipline_safety":
            gate_id = "balance_sheet_safety_gate"
            bs = factors.get("balance_sheet_safety")
            gate_inputs = {
                "balance_sheet_safety": bs.normalized_score if bs and bs.status in _VALID else None,
            }
            if bs and bs.status in _VALID and bs.normalized_score <= D("-0.25"):
                gate_passed = False
                reason_code = "balance_sheet_risk_blocks_bullish"
                threshold_relation = "gate_blocked"
            else:
                gate_passed = True
        elif policy.style == "quality_value_cash":
            gate_id = "cash_backing_gate"
            cc = factors.get("cash_conversion")
            gate_inputs = {
                "cash_conversion": cc.normalized_score if cc and cc.status in _VALID else None,
            }
            if cc and cc.status in _VALID and cc.normalized_score <= D("-0.25"):
                gate_passed = False
                reason_code = "weak_cash_conversion_blocks_bullish"
                threshold_relation = "gate_blocked"
            else:
                gate_passed = True

        if threshold_relation not in {"gate_blocked", "profile_gate_bearish", "growth_gate", "no_score"}:
            if signal == "bullish":
                threshold_relation = "gte_bullish_threshold"
                reason_code = "bullish_threshold_reached"
            elif signal == "bearish":
                threshold_relation = "lte_bearish_threshold"
                reason_code = "bearish_threshold_reached"
            elif reason_code == "threshold_neutral":
                reason_code = "between_signal_thresholds"

        return SignalExplanation(
            signal=signal, strategy_score=score,
            bullish_threshold=policy.bullish_at,
            bearish_threshold=policy.bearish_at,
            policy_style=policy.style, gate_id=gate_id,
            gate_passed=gate_passed, gate_inputs=gate_inputs,
            threshold_relation=threshold_relation, reason_code=reason_code,
        )

    @staticmethod
    def _signal(profile, factors, score):
        if score is None:
            return "neutral"
        policy = profile.signal_policy
        if policy.style == "long_term_quality" and not any(
                factors[key].status in _VALID for key in profile.core_factors):
            return "neutral"
        if policy.style == "proxy_plus_improvement":
            proxy = factors[PROXY_ID]
            if proxy.status not in _VALID or proxy.normalized_score <= 0:
                return "neutral"
            improvements = [factors[key].normalized_score for key in
                            ("growth_acceleration", "margin_trend", "earnings_growth_yoy")
                            if factors[key].status in _VALID]
            if not improvements:
                return "neutral"
            improvement = sum(improvements, D(0)) / D(len(improvements))
            if improvement <= D("-0.20"):
                return "bearish"
            if improvement < D("0.15"):
                return "neutral"
        if policy.style == "growth_quality":
            growth = [factors[key].normalized_score for key in
                      ("revenue_growth_yoy", "earnings_growth_yoy", "growth_acceleration")
                      if factors[key].status in _VALID]
            if not growth or sum(growth, D(0)) / D(len(growth)) <= D("-0.25"):
                return "bearish" if growth and score <= policy.bearish_at else "neutral"
        elif policy.style == "value_turnaround":
            earn = factors.get("earnings_growth_yoy")
            margin = factors.get("margin_trend")
            val_lvl = factors.get("valuation_level")
            op_bad = (earn and earn.status in _VALID and earn.normalized_score <= D("-0.20") and
                      margin and margin.status in _VALID and margin.normalized_score <= D("-0.20"))
            val_expensive = val_lvl and val_lvl.status in _VALID and val_lvl.normalized_score <= D("-0.20")
            if op_bad or val_expensive:
                return "bearish" if score <= policy.bearish_at else "neutral"
        elif policy.style == "balanced_quality_growth":
            pq = factors.get("profitability_quality")
            cc = factors.get("cash_conversion")
            weak_quality = ((pq and pq.status in _VALID and pq.normalized_score <= D("-0.25")) or
                            (cc and cc.status in _VALID and cc.normalized_score <= D("-0.25")))
            if weak_quality:
                return "bearish" if score <= policy.bearish_at else "neutral"
        elif policy.style == "consumer_quality_growth":
            rev = factors.get("revenue_growth_yoy")
            earn = factors.get("earnings_growth_yoy")
            contracting = (rev and rev.status in _VALID and rev.normalized_score <= D("-0.20") and
                           earn and earn.status in _VALID and earn.normalized_score <= D("-0.20"))
            if contracting:
                return "bearish" if score <= policy.bearish_at else "neutral"
        elif policy.style == "growth_valuation_balance":
            ga = factors.get("growth_acceleration")
            earn = factors.get("earnings_growth_yoy")
            decelerating = (ga and ga.status in _VALID and ga.normalized_score <= D("-0.25") and
                            earn and earn.status in _VALID and earn.normalized_score <= 0)
            if decelerating:
                return "bearish" if score <= policy.bearish_at else "neutral"
        elif policy.style == "value_discipline_safety":
            bs = factors.get("balance_sheet_safety")
            if bs and bs.status in _VALID and bs.normalized_score <= D("-0.25"):
                return "bearish" if score <= policy.bearish_at else "neutral"
        elif policy.style == "quality_value_cash":
            cc = factors.get("cash_conversion")
            if cc and cc.status in _VALID and cc.normalized_score <= D("-0.25"):
                return "bearish" if score <= policy.bearish_at else "neutral"
        return ("bullish" if score >= policy.bullish_at else
                "bearish" if score <= policy.bearish_at else "neutral")

    @staticmethod
    def _signal_reason(profile, factors, score, signal):
        if score is None:
            return "没有可用的已选因子，按规则保持 neutral。"
        style = profile.signal_policy.style
        if style == "long_term_quality" and not any(
                factors[key].status in _VALID for key in profile.core_factors):
            return "核心经营质量因子均不可用，长期质量策略按规则保持 neutral。"
        if style == "proxy_plus_improvement":
            proxy = factors[PROXY_ID]
            if proxy.status not in _VALID or proxy.normalized_score <= 0:
                return "低预期代理未成立，不能仅凭低估值或价格下跌转为 bullish。"
            improvements = [factors[key].normalized_score for key in
                            ("growth_acceleration", "margin_trend", "earnings_growth_yoy")
                            if factors[key].status in _VALID]
            if not improvements:
                return "低预期代理成立，但缺少经营改善证据，保持 neutral。"
            improvement = sum(improvements, D(0)) / D(len(improvements))
            if improvement <= D("-0.20"):
                return "低预期代理成立且经营证据恶化，策略门槛判定 bearish。"
            if improvement < D("0.15"):
                return "低预期代理成立，但经营改善未达门槛，保持 neutral。"
            if score >= profile.signal_policy.bullish_at:
                return "低预期代理与经营改善同时成立，且策略评分达到 bullish 门槛。"
        if style == "growth_quality":
            growth = [factors[key].normalized_score for key in
                      ("revenue_growth_yoy", "earnings_growth_yoy", "growth_acceleration")
                      if factors[key].status in _VALID]
            if not growth:
                return "缺少可用成长因子，成长质量策略不因盈利质量单独转为 bullish。"
            if sum(growth, D(0)) / D(len(growth)) <= D("-0.25"):
                return "成长因子均值低于策略门槛，盈利质量不能抵消成长转弱。"
        elif style == "value_turnaround":
            earn = factors.get("earnings_growth_yoy")
            margin = factors.get("margin_trend")
            val_lvl = factors.get("valuation_level")
            op_bad = (earn and earn.status in _VALID and earn.normalized_score <= D("-0.20") and
                      margin and margin.status in _VALID and margin.normalized_score <= D("-0.20"))
            val_expensive = val_lvl and val_lvl.status in _VALID and val_lvl.normalized_score <= D("-0.20")
            if op_bad:
                return "逆向价值策略：盈利与利润率均未见修复拐点，阻断 bullish 信号。"
            if val_expensive:
                return "逆向价值策略：估值折价优势不足，安全垫受限，不判定 bullish。"
        elif style == "balanced_quality_growth":
            pq = factors.get("profitability_quality")
            cc = factors.get("cash_conversion")
            if ((pq and pq.status in _VALID and pq.normalized_score <= D("-0.25")) or
                    (cc and cc.status in _VALID and cc.normalized_score <= D("-0.25"))):
                return "均衡质量成长策略：盈利质量或现金转化显著承压，成长不能掩盖质量恶化。"
        elif style == "consumer_quality_growth":
            rev = factors.get("revenue_growth_yoy")
            earn = factors.get("earnings_growth_yoy")
            if (rev and rev.status in _VALID and rev.normalized_score <= D("-0.20") and
                    earn and earn.status in _VALID and earn.normalized_score <= D("-0.20")):
                return "消费成长策略：营收与利润同时明显收缩，消费动能承压，不判定 bullish。"
        elif style == "growth_valuation_balance":
            ga = factors.get("growth_acceleration")
            earn = factors.get("earnings_growth_yoy")
            if (ga and ga.status in _VALID and ga.normalized_score <= D("-0.25") and
                    earn and earn.status in _VALID and earn.normalized_score <= 0):
                return "成长估值匹配策略：成长速度明显减速且利润增长停滞，阻断 bullish 信号。"
        elif style == "value_discipline_safety":
            bs = factors.get("balance_sheet_safety")
            if bs and bs.status in _VALID and bs.normalized_score <= D("-0.25"):
                return "财务纪律策略：资产负债安全性承压，违背防守底线，阻断 bullish 信号。"
        elif style == "quality_value_cash":
            cc = factors.get("cash_conversion")
            if cc and cc.status in _VALID and cc.normalized_score <= D("-0.25"):
                return "深度价值策略：利润缺少充沛现金流支撑，阻断 bullish 信号。"
        threshold = (profile.signal_policy.bullish_at if signal == "bullish" else
                     profile.signal_policy.bearish_at if signal == "bearish" else None)
        if threshold is not None:
            return f"strategy_score={score:.3f} 达到 profile {signal} 阈值 {threshold}。"
        return (f"strategy_score={score:.3f} 位于 bullish 阈值 {profile.signal_policy.bullish_at} "
                f"与 bearish 阈值 {profile.signal_policy.bearish_at} 之间。")
