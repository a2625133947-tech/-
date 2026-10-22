import os
import json
from langchain_anthropic import ChatAnthropic
from langchain_deepseek import ChatDeepSeek
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_xai import ChatXAI
from langchain_openai import ChatOpenAI, AzureChatOpenAI
from langchain_openai import ChatOpenAI
from langchain_gigachat import GigaChat
from langchain_ollama import ChatOllama
from enum import Enum
from pydantic import BaseModel
from typing import Tuple, List
from pathlib import Path
from src.llm.credentials import resolve_key


class ModelProvider(str, Enum):
    """Enum for supported LLM providers"""

    ALIBABA = "Alibaba"
    ANTHROPIC = "Anthropic"
    DEEPSEEK = "DeepSeek"
    GOOGLE = "Google"
    GROQ = "Groq"
    META = "Meta"
    MISTRAL = "Mistral"
    OPENAI = "OpenAI"
    OLLAMA = "Ollama"
    OPENROUTER = "OpenRouter"
    GIGACHAT = "GigaChat"
    AZURE_OPENAI = "Azure OpenAI"
    XAI = "xAI"


class LLMModel(BaseModel):
    """Represents an LLM model configuration"""

    display_name: str
    model_name: str
    provider: ModelProvider

    def to_choice_tuple(self) -> Tuple[str, str, str]:
        """Convert to format needed for questionary choices"""
        return (self.display_name, self.model_name, self.provider.value)

    def is_custom(self) -> bool:
        """Check if the model is a Gemini model"""
        return self.model_name == "-"

    def has_json_mode(self) -> bool:
        """Check if the model supports JSON mode"""
        if self.is_deepseek() or self.is_gemini():
            return False
        # Only certain Ollama models support JSON mode
        if self.is_ollama():
            return "llama3" in self.model_name or "neural-chat" in self.model_name
        # OpenRouter models generally support JSON mode
        if self.provider == ModelProvider.OPENROUTER:
            return True
        return True

    def is_deepseek(self) -> bool:
        """Check if the model is a DeepSeek model"""
        return self.model_name.startswith("deepseek")

    def is_gemini(self) -> bool:
        """Check if the model is a Gemini model"""
        return self.model_name.startswith("gemini")

    def is_ollama(self) -> bool:
        """Check if the model is an Ollama model"""
        return self.provider == ModelProvider.OLLAMA


# Load models from JSON file
def load_models_from_json(json_path: str) -> List[LLMModel]:
    """Load models from a JSON file"""
    with open(json_path, 'r') as f:
        models_data = json.load(f)
    
    models = []
    for model_data in models_data:
        # Convert string provider to ModelProvider enum
        provider_enum = ModelProvider(model_data["provider"])
        models.append(
            LLMModel(
                display_name=model_data["display_name"],
                model_name=model_data["model_name"],
                provider=provider_enum
            )
        )
    return models


# Get the path to the JSON files
current_dir = Path(__file__).parent
models_json_path = current_dir / "api_models.json"
ollama_models_json_path = current_dir / "ollama_models.json"

# Load available models from JSON
AVAILABLE_MODELS = load_models_from_json(str(models_json_path))

# Load Ollama models from JSON
OLLAMA_MODELS = load_models_from_json(str(ollama_models_json_path))

# Create LLM_ORDER in the format expected by the UI
LLM_ORDER = [model.to_choice_tuple() for model in AVAILABLE_MODELS]

# Create Ollama LLM_ORDER separately
OLLAMA_LLM_ORDER = [model.to_choice_tuple() for model in OLLAMA_MODELS]


def normalize_model_provider(provider: str | ModelProvider | None) -> ModelProvider:
    """Normalize model provider string or enum to ModelProvider enum."""
    if isinstance(provider, ModelProvider):
        return provider
    if not provider:
        return ModelProvider.OPENAI
    provider_str = str(provider).strip()
    for p in ModelProvider:
        if p.value.lower() == provider_str.lower() or p.name.lower() == provider_str.lower():
            return p
    return ModelProvider(provider_str)


def get_default_model_choice(db=None) -> tuple[str, ModelProvider]:
    """Return the default (model_name, ModelProvider) based on currently configured credentials."""
    from src.llm.credentials import configured_credentials
    creds = configured_credentials(db)

    # When DeepSeek is configured (common local/domestic setup), prioritize it
    if creds.get("DEEPSEEK_API_KEY"):
        return "deepseek-chat", ModelProvider.DEEPSEEK
    if creds.get("OPENAI_API_KEY"):
        return "gpt-4.1", ModelProvider.OPENAI
    if creds.get("ANTHROPIC_API_KEY"):
        return "claude-sonnet-4-5-20250929", ModelProvider.ANTHROPIC
    if creds.get("GROQ_API_KEY"):
        return "llama-3.3-70b-versatile", ModelProvider.GROQ
    if creds.get("GOOGLE_API_KEY"):
        return "gemini-2.5-flash", ModelProvider.GOOGLE
    if creds.get("OPENROUTER_API_KEY"):
        return "deepseek/deepseek-chat", ModelProvider.OPENROUTER
    if creds.get("XAI_API_KEY"):
        return "grok-4-0709", ModelProvider.XAI
    if creds.get("GIGACHAT_API_KEY"):
        return "GigaChat-2-Max", ModelProvider.GIGACHAT

    return "gpt-4.1", ModelProvider.OPENAI


def get_model_info(model_name: str, model_provider: str | ModelProvider) -> LLMModel | None:
    """Get model information by model_name"""
    try:
        norm_provider = normalize_model_provider(model_provider).value
    except Exception:
        norm_provider = str(model_provider)
    all_models = AVAILABLE_MODELS + OLLAMA_MODELS
    match = next((model for model in all_models if model.model_name == model_name and model.provider == norm_provider), None)
    if match:
        return match
    try:
        return LLMModel(display_name=model_name, model_name=model_name, provider=ModelProvider(norm_provider))
    except ValueError:
        return None


def find_model_by_name(model_name: str) -> LLMModel | None:
    """Find a model by its name across all available models."""
    all_models = AVAILABLE_MODELS + OLLAMA_MODELS
    return next((model for model in all_models if model.model_name == model_name), None)


def get_models_list():
    """Get the list of models for API responses."""
    return [
        {
            "display_name": model.display_name,
            "model_name": model.model_name,
            "provider": model.provider.value
        }
        for model in AVAILABLE_MODELS
    ]


def get_model(model_name: str, model_provider: ModelProvider | str, api_keys: dict = None) -> ChatOpenAI | ChatGroq | ChatOllama | GigaChat | None:
    if isinstance(model_provider, str):
        try:
            model_provider = normalize_model_provider(model_provider)
        except Exception:
            pass
    if model_provider == ModelProvider.GROQ:
        api_key = resolve_key("GROQ_API_KEY", api_keys)
        if not api_key:
            # Print error to console
            print(f"API Key Error: Please make sure GROQ_API_KEY is set in your .env file or provided via API keys.")
            raise ValueError("Groq API key not found.  Please make sure GROQ_API_KEY is set in your .env file or provided via API keys.")
        return ChatGroq(model=model_name, api_key=api_key)
    elif model_provider == ModelProvider.OPENAI:
        # Get and validate API key
        api_key = resolve_key("OPENAI_API_KEY", api_keys)
        base_url = os.getenv("OPENAI_API_BASE")
        if not api_key:
            # Print error to console
            print(f"API Key Error: Please make sure OPENAI_API_KEY is set in your .env file or provided via API keys.")
            raise ValueError("OpenAI API key not found.  Please make sure OPENAI_API_KEY is set in your .env file or provided via API keys.")
        return ChatOpenAI(model=model_name, api_key=api_key, base_url=base_url)
    elif model_provider == ModelProvider.ANTHROPIC:
        api_key = resolve_key("ANTHROPIC_API_KEY", api_keys)
        if not api_key:
            print(f"API Key Error: Please make sure ANTHROPIC_API_KEY is set in your .env file or provided via API keys.")
            raise ValueError("Anthropic API key not found.  Please make sure ANTHROPIC_API_KEY is set in your .env file or provided via API keys.")
        return ChatAnthropic(model=model_name, api_key=api_key)
    elif model_provider == ModelProvider.DEEPSEEK:
        api_key = resolve_key("DEEPSEEK_API_KEY", api_keys)
        if not api_key:
            print(f"API Key Error: Please make sure DEEPSEEK_API_KEY is set in your .env file or provided via API keys.")
            raise ValueError("DeepSeek API key not found.  Please make sure DEEPSEEK_API_KEY is set in your .env file or provided via API keys.")
        return ChatDeepSeek(model=model_name, api_key=api_key)
    elif model_provider == ModelProvider.GOOGLE:
        api_key = resolve_key("GOOGLE_API_KEY", api_keys)
        if not api_key:
            print(f"API Key Error: Please make sure GOOGLE_API_KEY is set in your .env file or provided via API keys.")
            raise ValueError("Google API key not found.  Please make sure GOOGLE_API_KEY is set in your .env file or provided via API keys.")
        return ChatGoogleGenerativeAI(model=model_name, api_key=api_key)
    elif model_provider == ModelProvider.OLLAMA:
        # For Ollama, we use a base URL instead of an API key
        # Check if OLLAMA_HOST is set (for Docker on macOS)
        ollama_host = os.getenv("OLLAMA_HOST", "localhost")
        base_url = os.getenv("OLLAMA_BASE_URL", f"http://{ollama_host}:11434")
        return ChatOllama(
            model=model_name,
            base_url=base_url,
        )
    elif model_provider == ModelProvider.OPENROUTER:
        api_key = resolve_key("OPENROUTER_API_KEY", api_keys)
        if not api_key:
            print(f"API Key Error: Please make sure OPENROUTER_API_KEY is set in your .env file or provided via API keys.")
            raise ValueError("OpenRouter API key not found. Please make sure OPENROUTER_API_KEY is set in your .env file or provided via API keys.")
        
        # Get optional site URL and name for headers
        site_url = os.getenv("YOUR_SITE_URL", "https://github.com/virattt/ai-hedge-fund")
        site_name = os.getenv("YOUR_SITE_NAME", "AI Hedge Fund")
        
        return ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,
            openai_api_base="https://openrouter.ai/api/v1",
            model_kwargs={
                "extra_headers": {
                    "HTTP-Referer": site_url,
                    "X-Title": site_name,
                }
            }
        )
    elif model_provider == ModelProvider.XAI:
        api_key = resolve_key("XAI_API_KEY", api_keys)
        if not api_key:
            print(f"API Key Error: Please make sure XAI_API_KEY is set in your .env file or provided via API keys.")
            raise ValueError("xAI API key not found. Please make sure XAI_API_KEY is set in your .env file or provided via API keys.")
        return ChatXAI(model=model_name, api_key=api_key)
    elif model_provider == ModelProvider.GIGACHAT:
        api_key = resolve_key("GIGACHAT_API_KEY", api_keys) or os.getenv("GIGACHAT_CREDENTIALS")
        if api_key:
            return GigaChat(credentials=api_key, model=model_name)
        if os.getenv("GIGACHAT_USER") or os.getenv("GIGACHAT_PASSWORD"):
            return GigaChat(model=model_name)
        raise ValueError("GigaChat API key not found. Please make sure GIGACHAT_API_KEY is set in your .env file or provided via API keys.")
    elif model_provider == ModelProvider.AZURE_OPENAI:
        # Get and validate API key
        api_key = resolve_key("AZURE_OPENAI_API_KEY", api_keys)
        if not api_key:
            # Print error to console
            print(f"API Key Error: Please make sure AZURE_OPENAI_API_KEY is set in your .env file.")
            raise ValueError("Azure OpenAI API key not found.  Please make sure AZURE_OPENAI_API_KEY is set in your .env file.")
        # Get and validate Azure Endpoint
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        if not azure_endpoint:
            # Print error to console
            print(f"Azure Endpoint Error: Please make sure AZURE_OPENAI_ENDPOINT is set in your .env file.")
            raise ValueError("Azure OpenAI endpoint not found.  Please make sure AZURE_OPENAI_ENDPOINT is set in your .env file.")
        # get and validate deployment name
        azure_deployment_name = model_name or os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        if not azure_deployment_name:
            # Print error to console
            print(f"Azure Deployment Name Error: Please make sure AZURE_OPENAI_DEPLOYMENT_NAME is set in your .env file.")
            raise ValueError("Azure OpenAI deployment name not found.  Please make sure AZURE_OPENAI_DEPLOYMENT_NAME is set in your .env file.")
        return AzureChatOpenAI(azure_endpoint=azure_endpoint, azure_deployment=azure_deployment_name, api_key=api_key, api_version="2024-10-21")
