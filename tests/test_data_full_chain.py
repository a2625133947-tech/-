"""Freeze the LLM boundary while checking the complete selected workflow."""

import json
from pathlib import Path

from src.agents import a_share_investors, portfolio_manager, risk_manager
from src.data.models import FinancialMetrics, Price
from src.main import run_hedge_fund

BASELINE = json.loads((Path(__file__).resolve().parents[1] /
                       "docs/baselines/stage1_600519_before.json").read_text())


def test_mock_llm_chain_matches_deterministic_600519_baseline(monkeypatch):
    metrics = [FinancialMetrics(**item) for item in BASELINE["financial_metrics"]["data"]]
    prices = [Price(**item) for item in BASELINE["prices"]["data"]]
    monkeypatch.setattr(a_share_investors, "get_financial_metrics", lambda *_args, **_kwargs: metrics)
    monkeypatch.setattr(a_share_investors, "get_prices",
                        lambda _ticker, start, end: [p for p in prices if start <= p.time <= end])
    monkeypatch.setattr(risk_manager, "get_prices", lambda *_args, **_kwargs: prices)
    monkeypatch.setattr(a_share_investors, "call_llm",
                        lambda _prompt, model, **_kwargs: model(reasoning="固定测试解释"))

    def fixed_portfolio(_prompt=None, pydantic_model=None, **_kwargs):
        return pydantic_model(decisions={"600519": {
            "action": "buy", "quantity": 15, "confidence": 66, "reasoning": "mock LLM"
        }})

    monkeypatch.setattr(portfolio_manager, "call_llm", fixed_portfolio)
    ticker = "600519"
    portfolio = {
        "cash": 100000.0, "margin_requirement": 0.0, "margin_used": 0.0,
        "positions": {ticker: {"long": 0, "short": 0, "long_cost_basis": 0.0,
                               "short_cost_basis": 0.0, "short_margin_used": 0.0}},
        "realized_gains": {ticker: {"long": 0.0, "short": 0.0}},
    }
    result = run_hedge_fund([ticker], "2026-03-25", "2026-09-25", portfolio,
                            selected_analysts=["duan_yongping"], model_name="mock",
                            model_provider="DeepSeek", progress_display=False)
    baseline_signals = BASELINE["workflow"]["data"]["analyst_signals"]
    analyst = result["analyst_signals"]["duan_yongping_agent"][ticker]
    expected_analyst = baseline_signals["duan_yongping_agent"][ticker]
    for key in ("signal", "confidence", "key_metrics", "strengths", "risks"):
        assert analyst[key] == expected_analyst[key]
    assert result["analyst_signals"]["risk_management_agent"][ticker] == (
        baseline_signals["risk_management_agent"][ticker])
    decision = result["decisions"][ticker]
    assert decision["action"] == "buy"
    assert decision["quantity"] == 15
    assert 0 <= decision["confidence"] <= 100
    risk = result["analyst_signals"]["risk_management_agent"][ticker]
    assert decision["quantity"] <= int(risk["remaining_position_limit"] // risk["current_price"])
