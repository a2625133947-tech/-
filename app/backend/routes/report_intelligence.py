"""Broker report routes extend the research namespace without touching Shadow APIs."""
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.backend.database.connection import get_db
from app.backend.services.api_key_service import ApiKeyService
from app.backend.services.report_intelligence_service import get_report_service
from src.research.grounding import answer_question
from src.research.models import PeriodRange, ResearchPeriod

router = APIRouter(prefix="/api/research/intelligence", tags=["research-intelligence"])


class RefreshRequest(BaseModel):
    period: ResearchPeriod = ResearchPeriod.MONTH
    start: str | None = None
    end: str | None = None
    limit: int = Field(default=100, ge=1, le=200)
    refresh_discovery: bool = False
    regenerate_summary: bool = False
    use_llm: bool = False
    model_name: str | None = None
    model_provider: str | None = None


def period_range(period, start, end):
    try:
        if period == ResearchPeriod.CUSTOM and (not start or not end):
            raise ValueError("custom requires both start and end")
        return PeriodRange.resolve(period, start, end)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/stocks/{query}/refresh", status_code=202)
def refresh(query: str, body: RefreshRequest, db: Session = Depends(get_db)):
    period = period_range(body.period, body.start, body.end)
    llm_state = None
    if body.use_llm:
        from src.llm.models import get_default_model_choice

        name, provider = get_default_model_choice(db)
        name, provider = body.model_name or name, body.model_provider or provider
        provider = provider.value if hasattr(provider, "value") else str(provider)
        llm_state = {"metadata": {"model_name": name, "model_provider": provider, "request": SimpleNamespace(api_keys=ApiKeyService(db).get_api_keys_dict())}}
    try:
        return get_report_service().start(query, period, limit=body.limit, refresh=body.refresh_discovery, regenerate=body.regenerate_summary, llm_state=llm_state)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(429, str(exc)) from exc


@router.get("/tasks/{task_id}")
def get_task(task_id: str):
    task = get_report_service().store.task(task_id)
    if task is None:
        raise HTTPException(404, "research task not found")
    return task


@router.get("/stocks/{query}/summary")
def get_summary(query: str, period: ResearchPeriod = ResearchPeriod.MONTH, start: str | None = None, end: str | None = None):
    service = get_report_service()
    try:
        security = service.resolve(query)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    ctx = service.store.latest_context(security.canonical_symbol, period_range(period, start, end))
    if ctx is None:
        raise HTTPException(404, "no cached research summary; start a refresh task")
    return ctx.model_dump(mode="json")


@router.get("/stocks/{query}/reports")
def get_reports(query: str, period: ResearchPeriod = ResearchPeriod.MONTH, start: str | None = None, end: str | None = None):
    return get_summary(query, period, start, end)["reports"]


@router.get("/reports/{report_id}")
def get_report(report_id: str):
    result = get_report_service().store.document_detail(report_id)
    if result is None:
        raise HTTPException(404, "research document not found")
    return result


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    period: ResearchPeriod = ResearchPeriod.MONTH
    start: str | None = None
    end: str | None = None


@router.post("/stocks/{query}/answer")
def answer(query: str, body: Question):
    from src.research.models import ResearchContext

    ctx = ResearchContext.model_validate(get_summary(query, body.period, body.start, body.end))
    return answer_question(ctx, body.question)
