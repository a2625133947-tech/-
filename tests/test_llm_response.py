"""Regression tests for providers that return unstructured JSON text."""

from types import SimpleNamespace

from pydantic import BaseModel

from src.utils import llm as llm_utils


class DecisionOutput(BaseModel):
    decisions: dict


def test_extract_json_accepts_plain_and_fenced_objects():
    payload = '{"decisions":{"600519":{"action":"buy","quantity":13}}}'
    expected = {"decisions": {"600519": {"action": "buy", "quantity": 13}}}

    assert llm_utils.extract_json_from_response(payload) == expected
    assert llm_utils.extract_json_from_response(f"```json\n{payload}\n```") == expected
    assert llm_utils.extract_json_from_response("not JSON") is None
    assert llm_utils.extract_json_from_response("[]") is None


def test_call_llm_uses_caller_fallback_when_all_responses_are_invalid(monkeypatch):
    attempts = []

    class FakeModel:
        def invoke(self, _prompt):
            attempts.append(1)
            return SimpleNamespace(content="not JSON")

    monkeypatch.setattr(llm_utils, "get_model_info", lambda *_args: SimpleNamespace(has_json_mode=lambda: False))
    monkeypatch.setattr(llm_utils, "get_model", lambda *_args: FakeModel())
    fallback = DecisionOutput(decisions={"600519": {"action": "hold", "quantity": 0}})

    result = llm_utils.call_llm("prompt", DecisionOutput, max_retries=2, default_factory=lambda: fallback)

    assert result is fallback
    assert len(attempts) == 2
