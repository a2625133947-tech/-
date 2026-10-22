"""UI-independent result shape for CLI, API, and future Web presentation."""

from typing import Any
from pydantic import BaseModel, Field, field_validator


class MetricItem(BaseModel):
    label: str
    value: Any = None
    format: str | None = None
    formatted: str = ""

    def __str__(self) -> str:
        return f"{self.label}：{self.formatted}" if self.formatted else self.label

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return str(self) == other or self.label == other or self.formatted == other or f"{self.label}: {self.formatted}" == other
        if isinstance(other, MetricItem):
            return (self.label, self.value, self.formatted) == (other.label, other.value, other.formatted)
        return super().__eq__(other)

    def __contains__(self, item: str) -> bool:
        return item in str(self) or (self.value is not None and item in str(self.value)) or item in self.label or item in self.formatted


class AgentAnalysis(BaseModel):
    name: str
    signal: str
    confidence: float
    key_metrics: list[MetricItem] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    reasoning: str = ""

    @field_validator("key_metrics", mode="before")
    @classmethod
    def _normalize_key_metrics(cls, v: Any) -> list[MetricItem]:
        if isinstance(v, dict):
            items = []
            for k, item in v.items():
                if isinstance(item, dict):
                    items.append(MetricItem(
                        label=item.get("label", k),
                        value=item.get("value"),
                        format=item.get("format"),
                        formatted=item.get("formatted", ""),
                    ))
                elif isinstance(item, MetricItem):
                    items.append(item)
                else:
                    items.append(MetricItem(label=k, value=item, formatted=str(item)))
            return items
        if isinstance(v, list):
            items = []
            for item in v:
                if isinstance(item, MetricItem):
                    items.append(item)
                elif isinstance(item, dict):
                    items.append(MetricItem(**item))
                elif isinstance(item, str):
                    if "：" in item:
                        lbl, _, fmtd = item.partition("：")
                    elif ": " in item:
                        lbl, _, fmtd = item.partition(": ")
                    else:
                        lbl, fmtd = item, ""
                    items.append(MetricItem(label=lbl, formatted=fmtd))
                else:
                    items.append(MetricItem(label=str(item)))
            return items
        return v


class StockAnalysis(BaseModel):
    ticker: str
    stock_name: str | None = None
    action: str
    confidence: float
    quantity: int
    portfolio_strategy: str
    agents: list[AgentAnalysis] = Field(default_factory=list)
    shadow_evaluations: dict[str, Any] = Field(default_factory=dict)


class AnalysisResult(BaseModel):
    stocks: list[StockAnalysis]
    progress: list[tuple[str, str]] = Field(default_factory=list)
    investor_mode: str = "legacy"
    show_reasoning: bool = False
    debug_state: bool = False
