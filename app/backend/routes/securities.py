"""Securities Search and Symbol Resolution API Routes."""

from __future__ import annotations

from fastapi import APIRouter, Query
from src.data.security_master import (
    SecurityMaster,
    SearchResponse,
    ResolveResponse,
)

router = APIRouter(prefix="/api/securities", tags=["securities"])


@router.get("/search", response_model=SearchResponse)
async def search_securities(
    q: str = Query(default="", description="股票代码（前缀/全码）、公司简称或拼音缩写"),
    limit: int = Query(default=10, ge=1, le=50, description="最大返回条数"),
) -> SearchResponse:
    """实时搜索证券标的，支持代码前缀、中文全名/部分名、拼音缩写及智能 Ranking 排序。"""
    sm = SecurityMaster.get_instance()
    return sm.search(query=q, limit=limit)


@router.get("/resolve", response_model=ResolveResponse)
async def resolve_security(
    q: str = Query(..., min_length=1, description="待解析的股票代码或公司名称"),
) -> ResolveResponse:
    """将输入的股票名称或代码确定性解析为系统标准股票对象，明确识别唯一标的或多重歧义。"""
    sm = SecurityMaster.get_instance()
    return sm.resolve(query=q)
