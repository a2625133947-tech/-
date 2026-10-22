"""Presentation DTO models for Research Mode and Shadow Engine APIs.

Decouples internal StrategyEvaluationResult and Factor contracts from Web representation.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class FactorContributionDTO(BaseModel):
    factor_id: str
    display_name: str
    version: str
    role: str  # "core", "supporting", "optional"
    role_display: str
    score: float | None = None
    weight: float
    weighted_contribution: float | None = None
    status: str
    factor_type: str
    raw_value: float | None = None
    raw_unit: str = "fraction"
    limitations: list[str] = Field(default_factory=list)


class SignalExplanationDTO(BaseModel):
    signal: str
    signal_display: str
    strategy_score: float | None = None
    bullish_threshold: float
    bearish_threshold: float
    policy_style: str
    gate_id: str | None = None
    gate_passed: bool | None = None
    gate_checks: list[str] = Field(default_factory=list)
    reason_code: str
    signal_reason: str


class ConfidenceBreakdownDTO(BaseModel):
    final_confidence: float
    maximum_possible: float = 90.0
    core_coverage: float = 0.0
    supporting_coverage: float = 0.0
    optional_coverage: float = 0.0
    coverage_score: float = 0.0
    evidence_quality: float = 0.0
    unconstrained_confidence: float = 0.0
    strategy_evidence_cap: float | None = None
    proxy_cap: float | None = None
    critical_capability_cap: float | None = None
    active_cap_name: str | None = None
    active_cap_value: float | None = None
    applied_caps: dict[str, float] = Field(default_factory=dict)
    notice: str = "置信度表示当前策略判断的数据支撑程度，不代表上涨概率或胜率。"


class LegacyComparisonDTO(BaseModel):
    legacy_signal: str
    legacy_signal_display: str
    legacy_confidence: float
    legacy_key_metrics: dict[str, Any] = Field(default_factory=dict)
    legacy_strengths: list[str] = Field(default_factory=list)
    legacy_risks: list[str] = Field(default_factory=list)
    new_signal: str
    new_signal_display: str
    new_confidence: float
    signal_changed: bool
    confidence_changed: bool
    core_difference: str
    research_disclaimer: str = "仅供策略原型对照研究，不代表模型优劣评判。"


class ShadowInvestorCardDTO(BaseModel):
    profile_id: str
    display_name: str
    profile_version: str
    lens: str
    signal: str
    signal_display: str
    confidence: float
    strategy_score: float | None = None
    strategy_evidence_coverage: float = 0.0
    core_coverage: float = 0.0
    supporting_coverage: float = 0.0
    implemented_factor_coverage: float = 0.0
    status: str = "READY"  # "READY" | "NOT_READY"
    not_ready_reason: str | None = None


class ProductionDecisionDTO(BaseModel):
    mode: str = "LEGACY"
    action: str
    action_display: str
    confidence: float
    quantity: int
    reasoning: str
    notice: str = "生产交易决策始终由 LEGACY 引擎驱动，SHADOW 研究结果不参与实盘执行。"


class StockResearchOverviewDTO(BaseModel):
    ticker: str
    stock_name: str
    as_of: str
    market_data_date: str | None = None
    snapshot_id: str | None = None
    snapshot_status: str = "PRESENT"
    data_quality: str = "HEALTHY"
    production_decision: ProductionDecisionDTO
    investor_cards: list[ShadowInvestorCardDTO] = Field(default_factory=list)
    not_ready_cards: list[ShadowInvestorCardDTO] = Field(default_factory=list)
    research_mode_banner: str = (
        "RESEARCH MODE · Shadow results are not production trading decisions. 生产交易状态：LEGACY"
    )


class InvestorDetailDTO(BaseModel):
    profile_id: str
    display_name: str
    profile_version: str
    description: str
    time_horizon: str
    signal: str
    signal_display: str
    confidence: float
    confidence_semantics: str
    strategy_score: float | None = None
    data_coverage: dict[str, float] = Field(default_factory=dict)
    factor_contributions: list[FactorContributionDTO] = Field(default_factory=list)
    signal_explanation: SignalExplanationDTO | None = None
    confidence_breakdown: ConfidenceBreakdownDTO | None = None
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    known_missing_dimensions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    legacy_comparison: LegacyComparisonDTO | None = None
    status: str = "READY"
    not_ready_reason: str | None = None


class CorpusHealthSummaryDTO(BaseModel):
    generated_at: str
    snapshot_count: int
    ticker_count: int
    date_range: list[str] | None = None
    partial_runs_count: int = 0
    degraded_snapshots_count: int = 0
    signal_distribution: dict[str, dict[str, int]] = Field(default_factory=dict)
    confidence_distribution: dict[str, dict[str, float]] = Field(default_factory=dict)
    data_drift_warnings: list[dict[str, Any]] = Field(default_factory=list)
    factor_drift_warnings: list[dict[str, Any]] = Field(default_factory=list)
    distribution_warnings: list[dict[str, Any]] = Field(default_factory=list)
    health_status: str = "Healthy"


class SnapshotItemDTO(BaseModel):
    snapshot_id: str
    ticker: str
    captured_at: str
    as_of: str
    market_data_date: str | None = None
    quality_status: str
    retention_tags: list[str] = Field(default_factory=list)
    evaluation_complete: bool = True
    run_status: str = "COMPLETE"
    evaluations_summary: dict[str, dict[str, Any]] = Field(default_factory=dict)
