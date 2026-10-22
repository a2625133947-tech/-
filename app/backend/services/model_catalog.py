"""Discover and cache the models exposed by each configured provider."""

import asyncio
import os
from datetime import datetime, timedelta, timezone

import httpx

from app.backend.database.models import ModelCatalogCache
from src.llm.credentials import PROVIDER_KEYS, configured_credentials
from src.llm.models import AVAILABLE_MODELS


CATALOG_TTL = timedelta(hours=24)
FAILURE_RETRY = timedelta(hours=1)
NON_CHAT_PARTS = (
    "embedding", "whisper", "transcri", "tts", "speech", "audio", "image",
    "dall-e", "realtime", "moderation", "rerank", "guard", "safety",
)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize(provider: str, items: list[dict]) -> list[dict]:
    items_list = list(items)
    if provider == "DeepSeek":
        canonical = [
            {"id": "deepseek-chat", "name": "DeepSeek V3", "display_name": "DeepSeek V3"},
            {"id": "deepseek-reasoner", "name": "DeepSeek R1", "display_name": "DeepSeek R1"},
        ]
        existing_ids = {it.get("id") or it.get("name") for it in items_list if isinstance(it, dict)}
        for c in canonical:
            if c["id"] not in existing_ids:
                items_list.append(c)

    models: dict[str, dict] = {}
    for item in items_list:
        raw_id = item.get("id") or item.get("name")
        if not isinstance(raw_id, str) or not raw_id:
            continue
        model_id = raw_id.removeprefix("models/") if provider == "Google" else raw_id
        lower_id = model_id.lower()
        if any(part in lower_id for part in NON_CHAT_PARTS):
            continue
        if provider == "Google":
            methods = item.get("supportedGenerationMethods") or []
            if "generateContent" not in methods:
                continue
        if provider == "OpenRouter":
            architecture = item.get("architecture") or {}
            output = architecture.get("output_modalities") or []
            if output and "text" not in output:
                continue
        display = item.get("display_name") or item.get("displayName") or item.get("name") or model_id
        if provider == "Google" and isinstance(display, str) and display.startswith("models/"):
            display = model_id
        if provider == "DeepSeek":
            if model_id == "deepseek-chat":
                display = "DeepSeek V3"
            elif model_id == "deepseek-reasoner":
                display = "DeepSeek R1"
        models[model_id] = {
            "display_name": str(display),
            "model_name": model_id,
            "provider": provider,
            "compatibility": "verified" if provider in ("Google", "DeepSeek") else "unverified",
        }
    return sorted(models.values(), key=lambda model: model["model_name"].lower())


async def _request_models(client: httpx.AsyncClient, provider: str, key: str) -> list[dict]:
    endpoints = {
        "OpenAI": os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/") + "/models",
        "Anthropic": "https://api.anthropic.com/v1/models",
        "DeepSeek": "https://api.deepseek.com/models",
        "Google": "https://generativelanguage.googleapis.com/v1beta/models",
        "Groq": "https://api.groq.com/openai/v1/models",
        "OpenRouter": "https://openrouter.ai/api/v1/models",
        "xAI": "https://api.x.ai/v1/models",
    }
    if provider == "GigaChat":
        return await asyncio.wait_for(asyncio.to_thread(_gigachat_models, key), timeout=8.0)

    headers = {"Authorization": f"Bearer {key}"}
    if provider == "Anthropic":
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
    elif provider == "Google":
        headers = {"x-goog-api-key": key}

    url = endpoints[provider]
    items: list[dict] = []
    params: dict[str, str] = {}
    for _ in range(100):
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        payload = response.json()
        page = payload.get("models") if provider == "Google" else payload.get("data")
        if not isinstance(page, list):
            raise ValueError("Invalid model-list response")
        items.extend(item for item in page if isinstance(item, dict))
        if provider == "Google" and payload.get("nextPageToken"):
            params = {"pageToken": payload["nextPageToken"]}
        elif provider == "Anthropic" and payload.get("has_more") and payload.get("last_id"):
            params = {"after_id": payload["last_id"]}
        else:
            return items
    raise ValueError("Model listing exceeded page limit")


def _gigachat_models(key: str) -> list[dict]:
    from gigachat import GigaChat as GigaChatClient

    with GigaChatClient(credentials=key) as client:
        result = client.get_models()
    return [
        {"id": model.id_, "name": model.id_}
        for model in result.data
    ]


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, (httpx.TimeoutException, asyncio.TimeoutError)):
        return "Provider request timed out"
    if isinstance(exc, httpx.HTTPStatusError):
        return f"Provider returned HTTP {exc.response.status_code}"
    if isinstance(exc, httpx.RequestError):
        return "Provider connection failed"
    if isinstance(exc, ValueError):
        return "Provider returned an invalid model list"
    return "Provider model discovery failed"


async def refresh_catalog(db, provider: str | None = None, force: bool = False) -> None:
    """Fetch providers concurrently and write cache updates with this session."""
    credentials = configured_credentials(db)
    targets = [provider] if provider else list(PROVIDER_KEYS)
    now = _now()
    pending = []
    for name in targets:
        key = credentials.get(PROVIDER_KEYS[name]) if name in PROVIDER_KEYS else None
        if not key or name == "Azure OpenAI":
            continue
        row = db.get(ModelCatalogCache, name)
        if not force and row:
            if row.synced_at and now - row.synced_at < CATALOG_TTL:
                continue
            if row.last_error and row.attempted_at and now - row.attempted_at < FAILURE_RETRY:
                continue
        pending.append((name, key))
    if not pending:
        return

    async with httpx.AsyncClient(timeout=8.0) as client:
        results = await asyncio.gather(
            *(_request_models(client, name, key) for name, key in pending),
            return_exceptions=True,
        )
    for (name, _), result in zip(pending, results):
        row = db.get(ModelCatalogCache, name)
        if row is None:
            row = ModelCatalogCache(provider=name, models=[])
            db.add(row)
        row.attempted_at = now
        if isinstance(result, BaseException):
            row.last_error = _safe_error(result)
        else:
            normalized = _normalize(name, result)
            if result and not normalized:
                row.last_error = "Provider returned no usable chat models"
            else:
                row.models = normalized
                row.synced_at = now
                row.last_error = None
    db.commit()


def catalog_snapshot(db) -> dict:
    """Return cached lists, using legacy recommendations only before a first successful sync."""
    credentials = configured_credentials(db)
    models = []
    statuses = []
    for provider, key_name in PROVIDER_KEYS.items():
        configured = bool(credentials.get(key_name))
        row = db.get(ModelCatalogCache, provider)
        source = "none"
        provider_models = []
        if provider == "Azure OpenAI":
            deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
            if configured and deployment and os.getenv("AZURE_OPENAI_ENDPOINT"):
                provider_models = [{"display_name": f"Azure deployment: {deployment}", "model_name": deployment, "provider": provider, "compatibility": "unverified"}]
                source = "manual"
        elif configured:
            if row and row.synced_at is not None:
                provider_models = row.models or []
                source = "cache"
            elif row and row.last_error:
                provider_models = [
                    {**model.model_dump(), "provider": provider, "compatibility": "unverified"}
                    for model in AVAILABLE_MODELS if model.provider.value == provider and model.model_name
                ]
                source = "fallback"
        models.extend(provider_models)
        statuses.append({
            "provider": provider,
            "configured": configured,
            "source": source,
            "synced_at": row.synced_at.isoformat() + "Z" if row and row.synced_at else None,
            "last_error": row.last_error if row and configured else None,
            "model_count": len(provider_models),
        })
    return {"models": models, "sync_status": statuses}


def cli_cloud_models() -> list[dict]:
    """Use the same persisted catalog for both command-line selectors."""
    from app.backend.database import Base, SessionLocal, engine

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        asyncio.run(refresh_catalog(db))
        return catalog_snapshot(db)["models"]
