"""Provider independent, citation-bearing research contracts."""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, model_validator

PROMPT_VERSION = "extractive-grounding-v4"
PARSER_VERSION = "pages-v2"


class ResearchPeriod(str, Enum):
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"
    CUSTOM = "custom"


class PeriodRange(BaseModel):
    period: ResearchPeriod
    start: date
    end: date

    @model_validator(mode="after")
    def ordered(self):
        if self.start > self.end:
            raise ValueError("start must not be after end")
        if (self.end - self.start).days > 3660:
            raise ValueError("research period cannot exceed ten years")
        return self

    @classmethod
    def resolve(cls, period=ResearchPeriod.MONTH, start=None, end=None):
        period = ResearchPeriod(period)
        end = date.fromisoformat(end) if isinstance(end, str) else end
        start = date.fromisoformat(start) if isinstance(start, str) else start
        end = end or datetime.now(ZoneInfo("Asia/Shanghai")).date()
        if period == ResearchPeriod.CUSTOM:
            if start is None:
                raise ValueError("custom requires start and end dates")
        else:
            if start is not None:
                raise ValueError("start is only valid for custom periods")
            if period == ResearchPeriod.WEEK:
                start = end - timedelta(weeks=1) + timedelta(days=1)
            else:
                year = end.year - (period == ResearchPeriod.YEAR)
                month = end.month
                if period == ResearchPeriod.MONTH:
                    month -= 1
                    if not month:
                        year, month = year - 1, 12
                start = date(year, month, min(end.day, calendar.monthrange(year, month)[1])) + timedelta(days=1)
        return cls(period=period, start=start, end=end)


class ResearchReportMetadata(BaseModel):
    report_id: str
    canonical_report_id: str = ""
    ticker: str
    company_name: str
    market: str
    title: str = Field(min_length=1)
    institution: str = Field(min_length=1)
    analyst: list[str] = Field(default_factory=list)
    published_at: date
    provider_published_at: date | None = None
    report_type: str = "company_research"
    rating: str = ""
    target_price: float | None = None
    source_url: str
    pdf_url: str = ""
    source_urls: list[str] = Field(default_factory=list)
    source_provider: str
    language: str = "zh"
    content_hash: str = ""
    pdf_hash: str = ""
    # Discovery snippets are metadata and must never become evidence.


class Chunk(BaseModel):
    chunk_id: str
    report_id: str
    page: int | None = None
    section: str = "正文"
    start: int
    end: int
    text: str


class ParsedDocument(BaseModel):
    metadata: ResearchReportMetadata
    text: str
    chunks: list[Chunk]
    content_kind: Literal["full_text", "abstract"] = "full_text"
    parser_version: str = PARSER_VERSION


class Citation(BaseModel):
    citation_id: str
    report_id: str
    chunk_id: str
    page: int | None = None
    section: str
    source_url: str
    quote: str
    title: str
    institution: str
    published_at: date
    analyst: list[str] = Field(default_factory=list)


class Claim(BaseModel):
    claim: str
    citations: list[str] = Field(min_length=1)
    # Safe mode only accepts claims that are literal evidence extracts.
    kind: Literal["extract", "statistic"] = "extract"


class CitedValue(BaseModel):
    metric: str
    value: float | str
    year: int | None = None
    unit: str = ""
    currency: str = ""
    citations: list[str] = Field(min_length=1)


class ReportSummary(BaseModel):
    report_id: str
    status: str = "INSUFFICIENT_EVIDENCE"
    findings: list[Claim] = Field(default_factory=list)
    risks: list[Claim] = Field(default_factory=list)
    catalysts: list[Claim] = Field(default_factory=list)
    ratings: list[CitedValue] = Field(default_factory=list)
    target_prices: list[CitedValue] = Field(default_factory=list)
    earnings_forecasts: list[CitedValue] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    rejected_claims: int = 0


class Coverage(BaseModel):
    discovered: int = 0
    unique_reports: int = 0
    full_text: int = 0
    abstract_only: int = 0
    failed: int = 0
    duplicates: int = 0
    out_of_period: int = 0
    evidence_coverage: float = 0
    source_diversity: float = 0
    source_agreement: float | None = None
    time_coverage: float = 0
    level: Literal["HIGH", "MEDIUM", "LOW"] = "LOW"
    discovery_complete: bool = True
    formulas: dict[str, str] = Field(
        default_factory=lambda: {
            "evidence_coverage": "(full_text + 0.5 * abstract_only) / unique_reports; zero if no reports",
            "source_diversity": "unique institutions / parsed reports; zero if no reports",
            "source_agreement": "null: raw ratings are not interchangeable and agreement is not inferred",
            "time_coverage": "days with parsed reports / calendar days in requested period; not internet coverage",
            "level": "HIGH: coverage>=0.8, >=10 parsed, >=3 institutions; MEDIUM: coverage>=0.5, >=3 parsed; otherwise LOW; incomplete discovery caps at LOW",
        }
    )


class ResearchContext(BaseModel):
    ticker: str
    company_name: str
    market: str
    exchange: str
    period: PeriodRange
    report_count: int
    institutions: list[str]
    status: str
    synthesis_mode: str = "verified_extractive"
    consensus: list[Claim] = Field(default_factory=list)
    disagreements: list[Claim] = Field(default_factory=list)
    ratings: list[CitedValue] = Field(default_factory=list)
    target_prices: list[CitedValue] = Field(default_factory=list)
    target_price_statistics: dict = Field(default_factory=dict)
    earnings_forecasts: list[CitedValue] = Field(default_factory=list)
    themes: list[Claim] = Field(default_factory=list)
    risks: list[Claim] = Field(default_factory=list)
    catalysts: list[Claim] = Field(default_factory=list)
    changes: list[Claim] = Field(default_factory=list)
    timeline: list[dict] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    coverage: Coverage
    reports: list[dict] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    metrics: dict = Field(default_factory=dict)
    prompt_version: str = PROMPT_VERSION


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    DISCOVERING = "DISCOVERING"
    DOWNLOADING = "DOWNLOADING"
    PARSING = "PARSING"
    SUMMARIZING = "SUMMARIZING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
