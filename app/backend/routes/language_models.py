from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.backend.database import get_db
from app.backend.models.schemas import ErrorResponse
from app.backend.services.ollama_service import OllamaService
from app.backend.services.model_catalog import catalog_snapshot, refresh_catalog
from src.llm.credentials import PROVIDER_KEYS

router = APIRouter(prefix="/language-models")

# Initialize Ollama service
ollama_service = OllamaService()

@router.get(
    path="/",
    responses={
        200: {"description": "List of available language models"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_language_models(db: Session = Depends(get_db)):
    """Get the list of available cloud-based and Ollama language models."""
    try:
        await refresh_catalog(db)
        result = catalog_snapshot(db)
        
        # Add available Ollama models (handles all checking internally)
        ollama_models = await ollama_service.get_available_models()
        result["models"].extend(ollama_models)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve models: {str(e)}")

@router.get(
    path="/providers",
    responses={
        200: {"description": "List of available model providers"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_language_model_providers(db: Session = Depends(get_db)):
    """Get the list of available model providers with their models grouped."""
    try:
        await refresh_catalog(db)
        snapshot = catalog_snapshot(db)
        models = snapshot["models"]
        
        # Group models by provider
        providers = {}
        for model in models:
            provider_name = model["provider"]
            if provider_name not in providers:
                providers[provider_name] = {
                    "name": provider_name,
                    "models": []
                }
            providers[provider_name]["models"].append({
                "display_name": model["display_name"],
                "model_name": model["model_name"],
                "compatibility": model.get("compatibility", "unverified"),
            })
        return {"providers": list(providers.values()), "sync_status": snapshot["sync_status"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve providers: {str(e)}")


@router.post("/refresh")
async def force_refresh_language_models(provider: str | None = None, db: Session = Depends(get_db)):
    if provider is not None and provider not in PROVIDER_KEYS:
        raise HTTPException(status_code=400, detail="Unsupported provider")
    await refresh_catalog(db, provider=provider, force=True)
    return catalog_snapshot(db)
