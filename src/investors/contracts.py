"""Strategy contracts; distinct from legacy agent and CLI output shapes."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from src.data.capabilities import Capability
from src.factors.contracts import FactorStatus, FactorType
from src.data.domain import Provenance, Unit
from src.factors.contracts import RawMetricPoint


class InvestorMode(StrEnum):
    LEGACY = "legacy"
    NEW = "new"
    SHADOW = "shadow"


class FactorRole(StrEnum):
    CORE = "core"
    SUPPORTING = "supporting"
    OPTIONAL = "optional"


@dataclass(frozen=True)
class SignalPolicy:
    bullish_at: Decimal
    bearish_at: Decimal
    style: str


@dataclass(frozen=True)
class ConfidencePolicy:
    maximum: int = 90
    core_weight: Decimal = Decimal("0.65")
    supporting_weight: Decimal = Decimal("0.25")
    optional_weight: Decimal = Decimal("0.10")


@dataclass(frozen=True)
class MissingDataPolicy:
    core_missing_cap: int
    history_missing_cap: int
    proxy_cap: int | None = None
    specific_limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class InvestorProfile:
    profile_id: str
    display_name: str
    description: str
    version: str
    core_factors: tuple[str, ...]
    supporting_factors: tuple[str, ...]
    optional_factors: tuple[str, ...]
    factor_weights: dict[str, Decimal]
    factor_versions: dict[str, str]
    time_horizon: str
    critical_capabilities: frozenset[Capability]
    important_capabilities: frozenset[Capability]
    optional_capabilities: frozenset[Capability]
    minimum_factor_coverage: Decimal
    signal_policy: SignalPolicy
    confidence_policy: ConfidencePolicy
    missing_data_policy: MissingDataPolicy
    key_metric_priority: tuple[str, ...]
    strength_rules: dict[str, str]
    risk_rules: dict[str, str]
    interpretation_rules: dict[str, tuple[str, str, str]]
    limitations: tuple[str, ...] = ()
    known_missing_dimensions: tuple[str, ...] = ()

    def __post_init__(self):
        groups = self.core_factors + self.supporting_factors + self.optional_factors
        if len(groups) != len(set(groups)):
            raise ValueError("factor roles overlap")
        if set(groups) != set(self.factor_weights) or set(groups) != set(self.factor_versions):
            raise ValueError("factor weights and versions must match selected factors")
        if any(weight <= 0 for weight in self.factor_weights.values()):
            raise ValueError("factor weights must be positive")
        if not set(self.key_metric_priority) <= set(groups):
            raise ValueError("key metric priority contains an unselected factor")

    def role(self, factor_id: str) -> FactorRole:
        if factor_id in self.core_factors:
            return FactorRole.CORE
        if factor_id in self.supporting_factors:
            return FactorRole.SUPPORTING
        if factor_id in self.optional_factors:
            return FactorRole.OPTIONAL
        raise KeyError(factor_id)

    @property
    def factor_ids(self) -> tuple[str, ...]:
        return self.core_factors + self.supporting_factors + self.optional_factors


class UsedFactor(BaseModel):
    factor_id: str
    version: str
    score: Decimal | None = None
    status: FactorStatus
    quality: str | None = None
    coverage: Decimal = Field(ge=0, le=1)
    weight: Decimal
    role: FactorRole
    factor_type: FactorType
    limitations: tuple[str, ...] = ()


class FactorContribution(BaseModel):
    """Auditable link from a strategy score to its factor and source inputs."""

    factor_id: str
    version: str
    raw_value: Decimal | None
    raw_unit: Unit
    score: Decimal | None
    weight: Decimal
    weighted_contribution: Decimal | None
    role: FactorRole
    status: FactorStatus
    factor_type: FactorType
    inputs: tuple[RawMetricPoint, ...] = ()
    provenance: tuple[Provenance, ...] = ()


class SignalExplanation(BaseModel):
    """Machine-readable rule path from the score and profile gate to a signal."""

    signal: str
    strategy_score: Decimal | None
    bullish_threshold: Decimal
    bearish_threshold: Decimal
    policy_style: str
    gate_id: str | None = None
    gate_passed: bool | None = None
    gate_inputs: dict[str, Decimal | None] = Field(default_factory=dict)
    threshold_relation: str
    reason_code: str


class ConfidenceComponents(BaseModel):
    """Detailed deterministic breakdown of strategy confidence calculation."""

    maximum_possible: float = 90.0
    core_coverage: float
    supporting_coverage: float
    optional_coverage: float
    coverage_score: float
    evidence_quality: float
    unconstrained_confidence: float
    core_missing_cap: float | None = None
    history_missing_cap: float | None = None
    minimum_coverage_cap: float | None = None
    critical_capability_cap: float | None = None
    proxy_cap: float | None = None
    strategy_evidence_cap: float | None = None
    applied_caps: dict[str, float] = Field(default_factory=dict)
    active_cap_name: str | None = None
    active_cap_value: float | None = None
    degraded_penalty_applied: bool = False
    degraded_penalty_multiplier: float = 1.0
    final_confidence: float
    audit_trail: list[str] = Field(default_factory=list)


class StrategyEvaluationResult(BaseModel):
    profile_id: str
    profile_version: str
    strategy_score: Decimal | None
    signal: str
    confidence: float = Field(ge=0, le=100)
    confidence_semantics: str = (
        "数据支撑与当前策略结论可信程度；不是上涨概率、盈利概率或交易胜率"
    )
    confidence_components: ConfidenceComponents | None = Field(default=None, exclude=True)
    used_factors: tuple[UsedFactor, ...]
    contributions: tuple[FactorContribution, ...]
    signal_explanation: SignalExplanation | None = None
    signal_reason: str
    core_coverage: Decimal = Field(ge=0, le=1)
    supporting_coverage: Decimal = Field(ge=0, le=1)
    overall_coverage: Decimal = Field(ge=0, le=1)
    known_missing_dimensions: tuple[str, ...] = Field(default=(), exclude=True)
    key_metrics: dict[str, dict]
    strengths: tuple[str, ...]
    risks: tuple[str, ...]
    interpretations: dict[str, str] = Field(default_factory=dict)
    limitations: tuple[str, ...]
    reasoning: str

    @property
    def implemented_factor_coverage(self) -> Decimal:
        return self.overall_coverage

    @property
    def strategy_evidence_coverage(self) -> Decimal:
        dims = len(self.used_factors) + len(self.known_missing_dimensions)
        if dims > 0:
            return self.overall_coverage * Decimal(len(self.used_factors)) / Decimal(dims)
        return self.overall_coverage
