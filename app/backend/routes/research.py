"""Research Mode and Shadow Engine API routes."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Query

from app.backend.models.research_schemas import (
    CorpusHealthSummaryDTO,
    InvestorDetailDTO,
    ShadowInvestorCardDTO,
    SnapshotItemDTO,
    StockResearchOverviewDTO,
)
from app.backend.services.research_service import ResearchService

router = APIRouter(prefix="/api/research", tags=["research"])


@router.get("/stocks/{ticker}", response_model=StockResearchOverviewDTO)
async def get_stock_research(
    ticker: str,
    as_of: str | None = Query(default=None, description="Point-in-time ISO date (e.g., 2026-09-27)"),
) -> StockResearchOverviewDTO:
    """Retrieve comprehensive research overview for a stock across all 10 Shadow profiles."""
    return ResearchService.get_stock_overview(ticker, as_of)


@router.get("/stocks/{ticker}/investors", response_model=list[ShadowInvestorCardDTO])
async def get_stock_investor_cards(
    ticker: str,
    as_of: str | None = Query(default=None, description="Point-in-time ISO date"),
) -> list[ShadowInvestorCardDTO]:
    """Retrieve the 10 Shadow investor cards for a stock."""
    overview = ResearchService.get_stock_overview(ticker, as_of)
    return overview.investor_cards + overview.not_ready_cards


@router.get("/stocks/{ticker}/investors/{profile_id}", response_model=InvestorDetailDTO)
async def get_stock_investor_detail(
    ticker: str,
    profile_id: str,
    as_of: str | None = Query(default=None, description="Point-in-time ISO date"),
) -> InvestorDetailDTO:
    """Retrieve full factor contributions, gate checks, and confidence breakdown for one investor."""
    return ResearchService.get_investor_detail(ticker, profile_id, as_of)


@router.get("/shadow/{ticker}/{profile_id}", response_model=InvestorDetailDTO)
async def get_shadow_evaluation(
    ticker: str,
    profile_id: str,
    as_of: str | None = Query(default=None, description="Point-in-time ISO date"),
) -> InvestorDetailDTO:
    """Direct alias to retrieve shadow evaluation details for a ticker and profile."""
    return ResearchService.get_investor_detail(ticker, profile_id, as_of)


@router.get("/corpus/summary", response_model=CorpusHealthSummaryDTO)
async def get_corpus_summary() -> CorpusHealthSummaryDTO:
    """Retrieve prospective shadow corpus health metrics, distributions, and warnings."""
    return ResearchService.get_corpus_summary()


@router.get("/corpus/snapshots", response_model=list[SnapshotItemDTO])
async def get_corpus_snapshots(
    ticker: str | None = Query(default=None, description="Filter by stock ticker"),
    limit: int = Query(default=50, ge=1, le=200, description="Max snapshots to return"),
) -> list[SnapshotItemDTO]:
    """List accumulated point-in-time snapshots and evaluation summaries."""
    return ResearchService.get_corpus_snapshots(ticker, limit)


@router.get("/corpus/snapshots/{snapshot_id}", response_model=dict[str, Any])
async def get_corpus_snapshot_detail(
    snapshot_id: str,
) -> dict[str, Any]:
    """Retrieve full 10-profile evaluations for a specific frozen snapshot."""
    return ResearchService.get_corpus_snapshot_detail(snapshot_id)
