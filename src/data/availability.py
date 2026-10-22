"""Request-level data coverage without InvestorProfile assumptions."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.data.capabilities import Capability
from src.data.domain import DataEnvelope, DataStatus, Quality


class DataAvailabilityReport(BaseModel):
    available_capabilities: list[Capability] = Field(default_factory=list)
    partial_capabilities: list[Capability] = Field(default_factory=list)
    missing_capabilities: list[Capability] = Field(default_factory=list)
    failed_capabilities: list[Capability] = Field(default_factory=list)
    coverage: float = Field(ge=0, le=1)
    requested: int = 0

    @classmethod
    def from_outcomes(cls, outcomes: dict[tuple[str, Capability], DataEnvelope]) -> DataAvailabilityReport:
        if not outcomes:
            return cls(coverage=0.0)
        by_capability: dict[Capability, list[DataEnvelope]] = {}
        for (_, capability), result in outcomes.items():
            by_capability.setdefault(capability, []).append(result)
        available, partial, missing, failed = [], [], [], []
        score = 0.0
        for capability, values in by_capability.items():
            statuses = {value.status for value in values}
            degraded = any(value.status is DataStatus.PRESENT and
                           value.observation.quality is Quality.DEGRADED for value in values)
            if statuses == {DataStatus.PRESENT} and not degraded:
                available.append(capability)
                score += len(values)
            elif DataStatus.PRESENT in statuses:
                partial.append(capability)
                score += sum(0.5 if value.observation.quality is Quality.DEGRADED else 1
                             for value in values if value.status is DataStatus.PRESENT)
            elif DataStatus.PROVIDER_FAILURE in statuses:
                failed.append(capability)
            else:
                missing.append(capability)
        return cls(available_capabilities=available, partial_capabilities=partial,
                   missing_capabilities=missing, failed_capabilities=failed,
                   coverage=round(score / len(outcomes), 4), requested=len(outcomes))
