"""Helper functions for LLM"""

import json
import logging
from pydantic import BaseModel
from src.llm.models import get_model, get_model_info
from src.utils.progress import progress
from src.graph.state import AgentState

logger = logging.getLogger(__name__)


def call_llm(
    prompt: any,
    pydantic_model: type[BaseModel],
    agent_name: str | None = None,
    state: AgentState | None = None,
    max_retries: int = 3,
    default_factory=None,
) -> BaseModel:
    """
    Makes an LLM call with retry logic, handling both JSON supported and non-JSON supported models.

    Args:
        prompt: The prompt to send to the LLM
        pydantic_model: The Pydantic model class to structure the output
        agent_name: Optional name of the agent for progress updates and model config extraction
        state: Optional state object to extract agent-specific model configuration
        max_retries: Maximum number of retries (default: 3)
        default_factory: Optional factory function to create default response on failure

    Returns:
        An instance of the specified Pydantic model
    """
    
    # Extract model configuration if state is provided and agent_name is available
    if state and agent_name:
        model_name, model_provider = get_agent_model_config(state, agent_name)
    else:
        # Use system defaults when no state or agent_name is provided
        model_name = "gpt-4.1"
        model_provider = "OPENAI"

    # Extract API keys from state if available
    api_keys = None
    if state:
        request = state.get("metadata", {}).get("request")
        if request and hasattr(request, 'api_keys'):
            api_keys = request.api_keys

    model_info = get_model_info(model_name, model_provider)
    llm = get_model(model_name, model_provider, api_keys)

    # For non-JSON support models, we can use structured output
    if not (model_info and not model_info.has_json_mode()):
        llm = llm.with_structured_output(
            pydantic_model,
            method="json_mode",
        )

    # Call the LLM with retries
    for attempt in range(max_retries):
        try:
            # Call the LLM
            logger.debug("LLM call: provider=%s model=%s agent=%s attempt=%s", model_provider, model_name, agent_name, attempt + 1)
            result = llm.invoke(prompt)

            # For non-JSON support models, we need to extract and parse the JSON manually
            if model_info and not model_info.has_json_mode():
                parsed_result = extract_json_from_response(result.content)
                if parsed_result is None:
                    raise ValueError("LLM response did not contain a JSON object")
                return pydantic_model(**parsed_result)
            else:
                return result

        except Exception as e:
            if agent_name:
                progress.update_status(agent_name, None, f"Error - retry {attempt + 1}/{max_retries}")

            if attempt == max_retries - 1:
                logger.exception("LLM call failed after %s attempts", max_retries)
                # Use default_factory if provided, otherwise create a basic default
                if default_factory:
                    return default_factory()
                return create_default_response(pydantic_model)

    # Parsing failures also exhaust retries; keep the caller's safe fallback.
    if default_factory:
        return default_factory()
    return create_default_response(pydantic_model)


def create_default_response(model_class: type[BaseModel]) -> BaseModel:
    """Creates a safe default response based on the model's fields."""
    default_values = {}
    for field_name, field in model_class.model_fields.items():
        if field.annotation == str:
            default_values[field_name] = "Error in analysis, using default"
        elif field.annotation == float:
            default_values[field_name] = 0.0
        elif field.annotation == int:
            default_values[field_name] = 0
        elif hasattr(field.annotation, "__origin__") and field.annotation.__origin__ == dict:
            default_values[field_name] = {}
        else:
            # For other types (like Literal), try to use the first allowed value
            if hasattr(field.annotation, "__args__"):
                default_values[field_name] = field.annotation.__args__[0]
            else:
                default_values[field_name] = None

    return model_class(**default_values)


def extract_json_from_response(content: str) -> dict | None:
    """Extract a JSON object from plain text, markdown blocks, or surrounding text."""
    if not content:
        return None
    content_str = str(content).strip()

    # 1. Try markdown code block with ```json ... ```
    if "```json" in content_str:
        try:
            start = content_str.find("```json") + len("```json")
            end = content_str.find("```", start)
            if end != -1:
                parsed = json.loads(content_str[start:end].strip())
                if isinstance(parsed, dict):
                    return parsed
        except Exception:
            pass

    # 2. Try generic code block ``` ... ```
    if "```" in content_str:
        try:
            start = content_str.find("```") + len("```")
            end = content_str.find("```", start)
            if end != -1:
                parsed = json.loads(content_str[start:end].strip())
                if isinstance(parsed, dict):
                    return parsed
        except Exception:
            pass

    # 3. Direct JSON load
    try:
        parsed = json.loads(content_str)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    # 4. Find outermost { and }
    try:
        start = content_str.find("{")
        end = content_str.rfind("}")
        if start != -1 and end != -1 and end > start:
            parsed = json.loads(content_str[start:end + 1])
            if isinstance(parsed, dict):
                return parsed
    except Exception:
        pass

    return None


def get_agent_model_config(state, agent_name):
    """
    Get model configuration for a specific agent from the state.
    Falls back to global model configuration if agent-specific config is not available.
    Always returns valid model_name and model_provider values.
    """
    request = state.get("metadata", {}).get("request")
    
    if request and hasattr(request, 'get_agent_model_config'):
        # Get agent-specific model configuration
        model_name, model_provider = request.get_agent_model_config(agent_name)
        # Ensure we have valid values
        if model_name and model_provider:
            return model_name, model_provider.value if hasattr(model_provider, 'value') else str(model_provider)
    
    # Fall back to global configuration (system defaults)
    model_name = state.get("metadata", {}).get("model_name")
    model_provider = state.get("metadata", {}).get("model_provider")

    if not model_name or not model_provider:
        from src.llm.models import get_default_model_choice
        def_name, def_prov = get_default_model_choice()
        model_name = model_name or def_name
        model_provider = model_provider or def_prov
    
    # Convert enum to string if necessary
    if hasattr(model_provider, 'value'):
        model_provider = model_provider.value
    
    return model_name, model_provider
