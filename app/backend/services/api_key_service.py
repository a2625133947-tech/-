from sqlalchemy.orm import Session
from typing import Dict, Optional
from app.backend.repositories.api_key_repository import ApiKeyRepository
from src.llm.credentials import configured_credentials


class ApiKeyService:
    """Simple service to load API keys for requests"""
    
    def __init__(self, db: Session):
        self.repository = ApiKeyRepository(db)
    
    def get_api_keys_dict(self) -> Dict[str, str]:
        """
        Load all active API keys from database and return as a dictionary
        suitable for injecting into requests
        """
        return configured_credentials(self.repository.db)
    
    def get_api_key(self, provider: str) -> Optional[str]:
        """Get a specific API key by provider"""
        return configured_credentials(self.repository.db).get(provider)
