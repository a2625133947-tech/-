"""Typed, source-independent inputs and outputs for Phase B factors."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field, field_validator, model_validator

from src.data.capabilities import Capability
from src.data.domain import Adjustment, DataStatus, PriceBar, Provenance, Quality, Unit


class FactorStatus(StrEnum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    INSUFFICIENT_HISTORY = "insufficient_history"
    NOT_AVAILABLE_AS_OF = "not_available_as_of"
    INVALID_INPUT = "invalid_input"
    DEGRADED = "degraded"


class FactorType(StrEnum):
    DIRECT = "direct"
    PROXY = "proxy"


class FactorCategory(StrEnum):
    QUALITY = "quality"
    GROWTH = "growth"
    CASH_FLOW = "cash_flow"
    VALUATION = "valuation"
    PRICE_BEHAVIOR = "price_behavior"


class RawMetricPoint(BaseModel):
    metric_id: str
    value: Decimal
    observed_date: date
    period: str
    provenance: Provenance
    source_inputs: tuple[Provenance, ...] = ()

    @model_validator(mode="after")
    def consistent(self):
        if not self.value.is_finite():
            raise ValueError("raw metric must be finite")
        if self.provenance.observed_date != self.observed_date:
            raise ValueError("metric date and provenance date differ")
        return self


class RawMetricSeries(BaseModel):
    metric_id: str
    points: tuple[RawMetricPoint, ...] = ()
    source_status: DataStatus = DataStatus.PRESENT

    @model_validator(mode="after")
    def consistent(self):
        if any(point.metric_id != self.metric_id for point in self.points):
            raise ValueError("metric_id mismatch")
        if self.points and self.source_status is not DataStatus.PRESENT:
            raise ValueError("non-present source cannot contain points")
        dates = [point.observed_date for point in self.points]
        if len(dates) != len(set(dates)):
            raise ValueError("duplicate raw metric date")
        return self

    def visible(self, as_of: datetime) -> tuple[RawMetricPoint, ...]:
        return tuple(sorted((point for point in self.points
                             if point.provenance.visible_as_of(as_of) and point.observed_date <= as_of.date()),
                            key=lambda point: point.observed_date))


class PriceInput(BaseModel):
    bars: tuple[PriceBar, ...] = ()
    provenance: Provenance | None = None
    status: DataStatus = DataStatus.UNSUPPORTED
    conflict: bool = False


class FactorContext(BaseModel):
    ticker: str
    as_of: datetime
    metrics: dict[str, RawMetricSeries] = Field(default_factory=dict)
    prices: PriceInput = Field(default_factory=PriceInput)

    @field_validator("as_of")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        return value.astimezone(timezone.utc)

    def series(self, metric_id: str) -> tuple[RawMetricPoint, ...]:
        item = self.metrics.get(metric_id)
        return item.visible(self.as_of) if item else ()


class FactorResult(BaseModel):
    factor_id: str
    version: str
    factor_type: FactorType = FactorType.DIRECT
    raw_value: Decimal | None = None
    raw_unit: Unit = Unit.NONE
    normalized_score: Decimal | None = Field(default=None, ge=-1, le=1)
    status: FactorStatus
    quality: Quality | None = None
    coverage: Decimal = Field(ge=0, le=1)
    as_of: datetime
    window: str
    inputs: tuple[RawMetricPoint, ...] = ()
    provenance: tuple[Provenance, ...] = ()
    reason: str | None = None
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def valid_score(self):
        if self.status in (FactorStatus.UNAVAILABLE, FactorStatus.INSUFFICIENT_HISTORY,
                           FactorStatus.NOT_AVAILABLE_AS_OF, FactorStatus.INVALID_INPUT):
            if self.normalized_score is not None:
                raise ValueError("unavailable factor cannot have a score")
        elif self.normalized_score is None or self.raw_value is None:
            raise ValueError("available factor needs raw value and normalized score")
        expected = tuple(source for point in self.inputs
                         for source in (point.provenance, *point.source_inputs))
        if self.inputs and self.provenance != expected:
            raise ValueError("provenance must match consumed inputs")
        if self.factor_type is FactorType.PROXY and not self.limitations:
            raise ValueError("proxy factor must declare limitations")
        return self


@runtime_checkable
class Factor(Protocol):
    factor_id: str
    display_name: str
    category: FactorCategory
    version: str
    factor_type: FactorType
    required_capabilities: frozenset[Capability]
    optional_capabilities: frozenset[Capability]
    required_history: int
    time_horizon: str
    dependencies: tuple[str, ...]

    def calculate(self, context: FactorContext) -> FactorResult: ...
    def evaluate(self, context: FactorContext) -> FactorResult: ...


QUALITY_RANK = {Quality.VALIDATED: 2, Quality.UNVERIFIED: 1, Quality.DEGRADED: 0}


def aggregate_quality(inputs: tuple[RawMetricPoint, ...], *, conflict: bool = False) -> Quality | None:
    if not inputs:
        return None
    if conflict:
        return Quality.DEGRADED
    return min((source.quality for point in inputs
                for source in (point.provenance, *point.source_inputs)),
               key=QUALITY_RANK.__getitem__)


def clamp_score(value: Decimal) -> Decimal:
    return max(Decimal("-1"), min(Decimal("1"), value))
