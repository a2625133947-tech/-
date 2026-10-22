"""Resolve provider credentials consistently for the web app and CLI."""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.exc import OperationalError


def _load_project_env() -> None:
    if os.getenv("AI_HEDGE_FUND_SKIP_DOTENV") != "1":
        load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def is_valid_key_value(val: str | None) -> bool:
    """Filter out empty strings and template placeholder tokens like 'your-openai-api-key'."""
    if not val or not isinstance(val, str):
        return False
    stripped = val.strip()
    if not stripped or stripped.startswith("your-") or "your-" in stripped.lower() or stripped == "placeholder":
        return False
    return True


PROVIDER_KEYS = {
    "Anthropic": "ANTHROPIC_API_KEY",
    "DeepSeek": "DEEPSEEK_API_KEY",
    "Google": "GOOGLE_API_KEY",
    "Groq": "GROQ_API_KEY",
    "OpenAI": "OPENAI_API_KEY",
    "OpenRouter": "OPENROUTER_API_KEY",
    "xAI": "XAI_API_KEY",
    "GigaChat": "GIGACHAT_API_KEY",
    "Azure OpenAI": "AZURE_OPENAI_API_KEY",
}


def configured_credentials(db=None) -> dict[str, str]:
    """Active database keys override environment keys; never serialize this result."""
    _load_project_env()
    result = {name: value for name in PROVIDER_KEYS.values() if (value := os.getenv(name)) and is_valid_key_value(value)}
    if "GIGACHAT_API_KEY" not in result and is_valid_key_value(os.getenv("GIGACHAT_CREDENTIALS")):
        result["GIGACHAT_API_KEY"] = os.environ["GIGACHAT_CREDENTIALS"]
    if db is not None:
        from app.backend.database.models import ApiKey

        for entry in db.query(ApiKey).filter(ApiKey.is_active.is_(True)).all():
            if entry.provider in PROVIDER_KEYS.values() and is_valid_key_value(entry.key_value):
                result[entry.provider] = entry.key_value
    else:
        try:
            from app.backend.database import SessionLocal
            from app.backend.database.models import ApiKey

            with SessionLocal() as session:
                for entry in session.query(ApiKey).filter(ApiKey.is_active.is_(True)).all():
                    if entry.provider in PROVIDER_KEYS.values() and is_valid_key_value(entry.key_value):
                        result[entry.provider] = entry.key_value
        except (OperationalError, Exception):
            pass
    return result


def credential_status(db) -> list[dict]:
    """Only configuration state, never key material, reaches the browser."""
    from app.backend.database.models import ApiKey

    _load_project_env()
    stored = {
        entry.provider
        for entry in db.query(ApiKey).filter(ApiKey.is_active.is_(True)).all()
        if is_valid_key_value(entry.key_value)
    }
    return [
        {
            "provider": provider,
            "key_name": key_name,
            "has_key": key_name in stored or is_valid_key_value(os.getenv(key_name)) or (provider == "GigaChat" and is_valid_key_value(os.getenv("GIGACHAT_CREDENTIALS"))),
            "source": "database" if key_name in stored else "environment" if is_valid_key_value(os.getenv(key_name)) or (provider == "GigaChat" and is_valid_key_value(os.getenv("GIGACHAT_CREDENTIALS"))) else None,
        }
        for provider, key_name in PROVIDER_KEYS.items()
    ]


def resolve_key(key_name: str, supplied: dict | None = None) -> str | None:
    _load_project_env()
    from app.backend.database import SessionLocal
    from app.backend.database.models import ApiKey

    try:
        with SessionLocal() as db:
            entry = db.query(ApiKey).filter(ApiKey.provider == key_name, ApiKey.is_active.is_(True)).first()
            if entry and is_valid_key_value(entry.key_value):
                return entry.key_value
    except OperationalError:
        # A CLI-only installation may not have initialized the web database yet.
        pass
    supplied_val = (supplied or {}).get(key_name)
    if is_valid_key_value(supplied_val):
        return supplied_val
    env_val = os.getenv(key_name)
    if is_valid_key_value(env_val):
        return env_val
    if key_name == "GIGACHAT_API_KEY":
        giga_val = os.getenv("GIGACHAT_CREDENTIALS")
        if is_valid_key_value(giga_val):
            return giga_val
    return None
