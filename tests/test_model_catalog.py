"""Model discovery tests use fake credentials and never contact providers."""

import asyncio
import os
from contextlib import nullcontext
from datetime import timedelta

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

os.environ["AI_HEDGE_FUND_SKIP_DOTENV"] = "1"

from app.backend.database.models import ApiKey, Base, ModelCatalogCache  # noqa: E402
from app.backend.services import model_catalog  # noqa: E402
from app.backend.routes import api_keys as api_key_routes  # noqa: E402
from app.backend.routes import language_models as model_routes  # noqa: E402
from app.backend.database import get_db  # noqa: E402
from app.backend.models.schemas import ApiKeyCreateRequest  # noqa: E402
from src.llm.credentials import configured_credentials, credential_status, resolve_key  # noqa: E402


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_database_key_precedes_environment_without_exposing_value(db, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "env-example")
    db.add(ApiKey(provider="OPENAI_API_KEY", key_value="saved-example", is_active=True))
    db.commit()

    assert configured_credentials(db)["OPENAI_API_KEY"] == "saved-example"
    status = next(item for item in credential_status(db) if item["provider"] == "OpenAI")
    assert status["source"] == "database"
    assert "saved-example" not in str(status)

    from app.backend import database

    monkeypatch.setattr(database, "SessionLocal", lambda: nullcontext(db))
    assert resolve_key("OPENAI_API_KEY", {"OPENAI_API_KEY": "request-example"}) == "saved-example"


def test_provider_model_list_filter_and_google_pagination():
    calls = []

    def respond(request):
        calls.append(request)
        if "pageToken" in str(request.url):
            return httpx.Response(200, json={"models": [{"name": "models/gemini-new", "supportedGenerationMethods": ["generateContent"]}]})
        return httpx.Response(200, json={"models": [
            {"name": "models/gemini-first", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]},
        ], "nextPageToken": "second"})

    async def fetch():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await model_catalog._request_models(client, "Google", "fake-key")

    models = model_catalog._normalize("Google", asyncio.run(fetch()))
    assert [model["model_name"] for model in models] == ["gemini-first", "gemini-new"]
    assert len(calls) == 2
    assert all(request.headers["x-goog-api-key"] == "fake-key" for request in calls)


def test_refresh_ttl_new_models_and_manual_refresh(db, monkeypatch):
    monkeypatch.setattr(model_catalog, "configured_credentials", lambda _db: {"OPENAI_API_KEY": "fake-key"})
    listing = [{"id": "gpt-old"}]
    fetches = []

    async def fake_fetch(_client, provider, _key):
        fetches.append(provider)
        return list(listing)

    monkeypatch.setattr(model_catalog, "_request_models", fake_fetch)
    asyncio.run(model_catalog.refresh_catalog(db))
    assert [model["model_name"] for model in model_catalog.catalog_snapshot(db)["models"]] == ["gpt-old"]

    listing.append({"id": "gpt-new"})
    asyncio.run(model_catalog.refresh_catalog(db))
    assert fetches == ["OpenAI"]
    assert len(model_catalog.catalog_snapshot(db)["models"]) == 1

    row = db.get(ModelCatalogCache, "OpenAI")
    row.synced_at -= timedelta(hours=25)
    db.commit()
    asyncio.run(model_catalog.refresh_catalog(db))
    assert fetches == ["OpenAI", "OpenAI"]
    assert len(model_catalog.catalog_snapshot(db)["models"]) == 2

    listing.append({"id": "gpt-latest"})
    asyncio.run(model_catalog.refresh_catalog(db, provider="OpenAI", force=True))
    assert len(model_catalog.catalog_snapshot(db)["models"]) == 3


def test_failed_provider_keeps_last_success_and_others_continue(db, monkeypatch):
    monkeypatch.setattr(model_catalog, "configured_credentials", lambda _db: {
        "OPENAI_API_KEY": "fake-openai", "OPENROUTER_API_KEY": "fake-router",
    })

    async def fake_fetch(_client, provider, _key):
        return [{"id": "shared-model"}]

    monkeypatch.setattr(model_catalog, "_request_models", fake_fetch)
    asyncio.run(model_catalog.refresh_catalog(db))
    snapshot = model_catalog.catalog_snapshot(db)
    assert {(model["provider"], model["model_name"]) for model in snapshot["models"]} == {
        ("OpenAI", "shared-model"), ("OpenRouter", "shared-model"),
    }

    async def one_fails(_client, provider, _key):
        if provider == "OpenAI":
            raise httpx.TimeoutException("timeout")
        return [{"id": "router-new"}]

    monkeypatch.setattr(model_catalog, "_request_models", one_fails)
    asyncio.run(model_catalog.refresh_catalog(db, force=True))
    snapshot = model_catalog.catalog_snapshot(db)
    assert ("OpenAI", "shared-model") in {(model["provider"], model["model_name"]) for model in snapshot["models"]}
    assert ("OpenRouter", "router-new") in {(model["provider"], model["model_name"]) for model in snapshot["models"]}
    assert next(status for status in snapshot["sync_status"] if status["provider"] == "OpenAI")["last_error"] == "Provider request timed out"


def test_initial_failure_uses_static_fallback(db, monkeypatch):
    monkeypatch.setattr(model_catalog, "configured_credentials", lambda _db: {"OPENAI_API_KEY": "fake-key"})

    async def fake_fetch(_client, _provider, _key):
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(model_catalog, "_request_models", fake_fetch)
    asyncio.run(model_catalog.refresh_catalog(db))
    snapshot = model_catalog.catalog_snapshot(db)
    assert any(model["provider"] == "OpenAI" for model in snapshot["models"])
    assert next(status for status in snapshot["sync_status"] if status["provider"] == "OpenAI")["source"] == "fallback"


def test_saving_key_triggers_only_its_provider_refresh(db, monkeypatch):
    refreshed = []

    async def fake_refresh(_db, provider=None, force=False):
        refreshed.append((provider, force))

    monkeypatch.setattr(api_key_routes, "refresh_catalog", fake_refresh)
    request = ApiKeyCreateRequest(provider="GROQ_API_KEY", key_value="fake-key")
    asyncio.run(api_key_routes.create_or_update_api_key(request, db))
    assert refreshed == [("Groq", True)]
    assert db.query(ApiKey).filter_by(provider="GROQ_API_KEY").count() == 1


def test_unauthorized_refresh_reports_status_without_key(db, monkeypatch):
    monkeypatch.setattr(model_catalog, "configured_credentials", lambda _db: {"OPENAI_API_KEY": "fake-secret"})

    async def unauthorized(_client, _provider, _key):
        request = httpx.Request("GET", "https://api.openai.com/v1/models")
        response = httpx.Response(401, request=request)
        raise httpx.HTTPStatusError("unauthorized", request=request, response=response)

    monkeypatch.setattr(model_catalog, "_request_models", unauthorized)
    asyncio.run(model_catalog.refresh_catalog(db))
    status = next(item for item in model_catalog.catalog_snapshot(db)["sync_status"] if item["provider"] == "OpenAI")
    assert status["last_error"] == "Provider returned HTTP 401"
    assert "fake-secret" not in str(status)


def test_cli_catalog_uses_same_cached_models(db, monkeypatch):
    from app.backend import database

    monkeypatch.setattr(database, "engine", db.get_bind())
    monkeypatch.setattr(database, "SessionLocal", lambda: nullcontext(db))
    monkeypatch.setattr(model_catalog, "configured_credentials", lambda _db: {"GROQ_API_KEY": "fake-key"})

    async def fake_fetch(_client, _provider, _key):
        return [{"id": "new-groq-chat"}]

    monkeypatch.setattr(model_catalog, "_request_models", fake_fetch)
    assert any(model["model_name"] == "new-groq-chat" for model in model_catalog.cli_cloud_models())


def test_gigachat_sdk_model_id_field(monkeypatch):
    import gigachat

    class FakeClient:
        def __init__(self, credentials):
            assert credentials == "fake-key"

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get_models(self):
            return type("Result", (), {"data": [type("Model", (), {"id_": "GigaChat-New"})()]})()

    monkeypatch.setattr(gigachat, "GigaChat", FakeClient)
    assert model_catalog._gigachat_models("fake-key") == [{"id": "GigaChat-New", "name": "GigaChat-New"}]


def test_api_save_list_and_manual_refresh(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    for key_name in model_catalog.PROVIDER_KEYS.values():
        monkeypatch.delenv(key_name, raising=False)
    listing = [{"id": "gpt-initial"}]

    async def fake_fetch(_client, _provider, _key):
        return list(listing)

    async def no_ollama():
        return []

    monkeypatch.setattr(model_catalog, "_request_models", fake_fetch)
    monkeypatch.setattr(model_routes.ollama_service, "get_available_models", no_ollama)
    app = FastAPI()
    app.include_router(api_key_routes.router)
    app.include_router(model_routes.router)

    def test_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    with TestClient(app) as client:
        saved = client.post("/api-keys/", json={"provider": "OPENAI_API_KEY", "key_value": "fake-key"})
        assert saved.status_code == 200
        assert client.get("/api-keys/status").json()["providers"][4]["source"] == "database"
        assert "fake-key" not in str(client.get("/api-keys/status").json())
        assert [item["model_name"] for item in client.get("/language-models/").json()["models"]] == ["gpt-initial"]

        listing.append({"id": "gpt-new"})
        refreshed = client.post("/language-models/refresh?provider=OpenAI")
        assert refreshed.status_code == 200
        assert {item["model_name"] for item in refreshed.json()["models"]} == {"gpt-initial", "gpt-new"}
    engine.dispose()


def test_deepseek_catalog_normalization_merges_canonical_models():
    raw_dynamic = [
        {"id": "deepseek-flash", "name": "DeepSeek-V4.1-Flash"},
        {"id": "deepseek-v4-pro", "name": "DeepSeek-V4-Pro"},
    ]
    models = model_catalog._normalize("DeepSeek", raw_dynamic)
    names = {m["model_name"] for m in models}
    assert "deepseek-chat" in names
    assert "deepseek-reasoner" in names
    assert "deepseek-flash" in names
    assert "deepseek-v4-pro" in names
    chat = next(m for m in models if m["model_name"] == "deepseek-chat")
    assert chat["display_name"] == "DeepSeek V3"
    assert chat["compatibility"] == "verified"


def test_default_model_choice_and_placeholder_filtering(db, monkeypatch):
    from src.llm.credentials import is_valid_key_value
    from src.llm.models import get_default_model_choice, ModelProvider

    assert not is_valid_key_value("your-deepseek-api-key")
    assert not is_valid_key_value("your-openai-api-key")
    assert not is_valid_key_value("")
    assert not is_valid_key_value(None)
    assert is_valid_key_value("sk-valid-key-12345")

    # When only deepseek is configured in db
    monkeypatch.setenv("OPENAI_API_KEY", "your-openai-api-key")
    db.add(ApiKey(provider="DEEPSEEK_API_KEY", key_value="sk-real-deepseek-key", is_active=True))
    db.commit()

    model_name, provider = get_default_model_choice(db)
    assert model_name == "deepseek-chat"
    assert provider == ModelProvider.DEEPSEEK


def test_normalize_model_provider_variations():
    from src.llm.models import normalize_model_provider, ModelProvider

    assert normalize_model_provider("DeepSeek") == ModelProvider.DEEPSEEK
    assert normalize_model_provider("deepseek") == ModelProvider.DEEPSEEK
    assert normalize_model_provider("DEEPSEEK") == ModelProvider.DEEPSEEK
    assert normalize_model_provider(ModelProvider.DEEPSEEK) == ModelProvider.DEEPSEEK
    assert normalize_model_provider("OpenAI") == ModelProvider.OPENAI
    assert normalize_model_provider("OPENAI") == ModelProvider.OPENAI


def test_graph_extract_base_agent_key_portfolio_manager():
    from app.backend.services.graph import extract_base_agent_key

    assert extract_base_agent_key("portfolio-manager-node") == "portfolio_manager"
    assert extract_base_agent_key("portfolio-manager") == "portfolio_manager"
    assert extract_base_agent_key("portfolio_manager_abc123") == "portfolio_manager"
    assert extract_base_agent_key("warren_buffett_xyz789") == "warren_buffett"


def test_hedge_fund_request_defaults_to_configured_provider(monkeypatch):
    from app.backend.models.schemas import BaseHedgeFundRequest
    from src.llm.models import ModelProvider

    monkeypatch.setattr("src.llm.models.get_default_model_choice", lambda _db=None: ("deepseek-chat", ModelProvider.DEEPSEEK))

    req = BaseHedgeFundRequest(
        tickers=["600519"],
        graph_nodes=[],
        graph_edges=[],
    )
    name, prov = req.get_agent_model_config("warren_buffett")
    assert name == "deepseek-chat"
    assert prov == ModelProvider.DEEPSEEK
