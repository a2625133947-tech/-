"""Pilot strategies are distinct decisions, not renamed legacy weights."""

import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from src.factors.contracts import FactorContext, FactorStatus, FactorType
from src.factors.engine import FactorEngine
from src.investors import PILOT_PROFILES, StrategyEvaluator
from src.investors.engine import low_expectation_proxy
from src.investors.profiles import PROXY_ID


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/factors/golden_v1.json").read_text())


def factors(ticker="600519"):
    return FactorEngine().evaluate(FactorContext.model_validate(FIXTURE["contexts"][ticker]))


def altered(factors_, factor_id, score):
    clone = dict(factors_)
    original = clone[factor_id]
    clone[factor_id] = original.model_copy(update={
        "normalized_score": Decimal(str(score)), "raw_value": Decimal(str(score)),
        "status": FactorStatus.AVAILABLE, "coverage": Decimal(1)})
    return clone


def test_profiles_have_distinct_factor_roles_priorities_rules_and_missing_policies():
    profiles = list(PILOT_PROFILES.values())
    for field in ("factor_ids", "core_factors", "key_metric_priority",
                  "interpretation_rules", "missing_data_policy"):
        assert len({repr(getattr(profile, field)) for profile in profiles}) == 3
    for profile in profiles:
        assert profile.version == {"zhang_kun": "v2", "feng_liu": "v1",
                                  "fu_pengbo": "v1"}[profile.profile_id]
        assert "原型" in profile.description
        assert all(profile.factor_versions[key] == "v1" for key in profile.factor_ids)


def test_same_momentum_and_valuation_receive_profile_specific_interpretations():
    available = factors()
    available = altered(available, "momentum_6m", "-0.8")
    available = altered(available, "valuation_percentile", "0.8")
    outputs = {key: StrategyEvaluator().evaluate(profile, available)
               for key, profile in PILOT_PROFILES.items()}
    assert len({out.interpretations["momentum_6m"] for out in outputs.values()}) == 3
    assert len({out.interpretations["valuation_percentile"] for out in outputs.values()}) == 3
    assert len({tuple(out.key_metrics) for out in outputs.values()}) == 3
    assert len({tuple(out.strengths) for out in outputs.values()}) == 3


def test_feng_proxy_requires_valuation_and_price_and_does_not_claim_real_expectations():
    current = factors()
    proxy = low_expectation_proxy(current)
    assert proxy.factor_type is FactorType.PROXY
    assert proxy.limitations and "不代表真实市场预期" in proxy.limitations[0]
    assert proxy.status is FactorStatus.PARTIAL
    assert low_expectation_proxy({key: result for key, result in current.items()
                                  if key not in {"momentum_1m", "drawdown_6m"}}).status is FactorStatus.UNAVAILABLE


def test_feng_low_valuation_and_deep_drawdown_needs_operating_improvement():
    current = factors()
    for key, score in (("valuation_level", "0.8"), ("valuation_percentile", "0.8"),
                       ("drawdown_6m", "-0.8"), ("momentum_1m", "-0.8")):
        current = altered(current, key, score)
    worsening = dict(current)
    for key in ("growth_acceleration", "margin_trend", "earnings_growth_yoy"):
        worsening = altered(worsening, key, "-0.8")
    evaluator = StrategyEvaluator()
    bad = evaluator.evaluate(PILOT_PROFILES["feng_liu"], worsening)
    assert bad.signal != "bullish"
    assert "真实市场预期" in bad.reasoning
    improving = dict(current)
    for key in ("growth_acceleration", "margin_trend", "earnings_growth_yoy"):
        improving = altered(improving, key, "0.8")
    good = evaluator.evaluate(PILOT_PROFILES["feng_liu"], improving)
    assert good.signal == "bullish"
    assert good.used_factors[0].factor_type is FactorType.PROXY


def test_zhang_negative_momentum_does_not_override_long_term_quality():
    current = factors()
    current = altered(current, "momentum_6m", "-1")
    result = StrategyEvaluator().evaluate(PILOT_PROFILES["zhang_kun"], current)
    assert result.signal == "bullish"
    assert result.strategy_score > 0
    assert "不单独推翻" in result.interpretations["momentum_6m"]


def test_fu_growth_deterioration_blocks_quality_only_bullish():
    current = factors()
    current = altered(current, "profitability_quality", "1")
    for key in ("revenue_growth_yoy", "earnings_growth_yoy", "growth_acceleration"):
        current = altered(current, key, "-1")
    result = StrategyEvaluator().evaluate(PILOT_PROFILES["fu_pengbo"], current)
    assert result.signal != "bullish"
    assert any("成长质量冲突" in risk for risk in result.risks)


def test_missing_is_not_zero_and_confidence_is_deterministic_and_capped():
    current = factors()
    profile = PILOT_PROFILES["zhang_kun"]
    full = StrategyEvaluator().evaluate(profile, current)
    missing = dict(current)
    old = missing["cash_conversion"]
    missing["cash_conversion"] = old.model_copy(update={
        "normalized_score": None, "raw_value": None,
        "status": FactorStatus.INSUFFICIENT_HISTORY, "coverage": Decimal(0)})
    evaluator = StrategyEvaluator()
    first = evaluator.evaluate(profile, missing)
    assert first == evaluator.evaluate(profile, missing)
    assert first.confidence < full.confidence
    assert first.confidence <= profile.missing_data_policy.core_missing_cap
    assert next(item for item in first.used_factors if item.factor_id == "cash_conversion").score is None
    assert 0 <= first.confidence <= 100


def test_strategy_refuses_mixed_as_of_and_factor_version():
    current = factors()
    changed = dict(current)
    old = changed["profitability_quality"]
    changed["profitability_quality"] = old.model_copy(update={"as_of": old.as_of + timedelta(days=1)})
    with pytest.raises(ValueError, match="share one as_of"):
        StrategyEvaluator().evaluate(PILOT_PROFILES["zhang_kun"], changed)
    changed["profitability_quality"] = old.model_copy(update={"version": "v2"})
    with pytest.raises(ValueError, match="version mismatch"):
        StrategyEvaluator().evaluate(PILOT_PROFILES["zhang_kun"], changed)


def test_fixture_profiles_differ_on_each_ticker_and_shadow_baseline_is_frozen():
    legacy = json.loads((ROOT / "docs/baselines/b4_legacy_fixture.json").read_text())
    assert set(legacy["tickers"]) == {"600519", "000001", "300750"}
    for ticker in legacy["tickers"]:
        results = {key: StrategyEvaluator().evaluate(profile, factors(ticker))
                   for key, profile in PILOT_PROFILES.items()}
        assert len({tuple(value.key_metrics) for value in results.values()}) == 3
        assert all(0 <= value.confidence <= 100 for value in results.values())
        assert set(legacy["tickers"][ticker]) == set(PILOT_PROFILES)


@pytest.mark.parametrize("profile_id", ["zhang_kun", "feng_liu", "fu_pengbo"])
def test_agent_shadow_keeps_legacy_output_and_new_mode_adds_audit_fields(monkeypatch, profile_id):
    from src.agents import a_share_investors as agents
    from src.data.models import FinancialMetrics, Price

    source = json.loads((ROOT / "docs/baselines/stage1_600519_before.json").read_text())
    metrics = [FinancialMetrics(**item) for item in source["financial_metrics"]["data"]]
    prices = [Price(**item) for item in source["prices"]["data"]]
    monkeypatch.setattr(agents, "get_financial_metrics", lambda *_args, **_kwargs: metrics)
    monkeypatch.setattr(agents, "get_prices", lambda *_args, **_kwargs: prices)
    monkeypatch.setattr(agents, "call_llm", lambda _prompt, model, **_kwargs: model(reasoning="只改文字"))
    fixed = StrategyEvaluator().evaluate(PILOT_PROFILES[profile_id], factors())
    monkeypatch.setattr(agents, "evaluate_ticker", lambda *_args, **_kwargs: fixed)

    def run(mode):
        state = {"messages": [], "data": {"tickers": ["600519"], "end_date": "2026-09-25",
                                          "analyst_signals": {}},
                 "metadata": {"investor_mode": mode, "show_reasoning": False}}
        agents.investor_agent(state, profile_key=profile_id)
        return state["data"]

    legacy = run("legacy")
    shadow = run("shadow")
    assert shadow["analyst_signals"] == legacy["analyst_signals"]
    record = shadow["investor_shadow"][f"{profile_id}_agent"]["600519"]
    assert record["legacy"]["signal"] == legacy["analyst_signals"][f"{profile_id}_agent"]["600519"]["signal"]
    assert record["new"]["profile_version"] == PILOT_PROFILES[profile_id].version
    assert record["new"]["used_factors"]
    assert record["new"]["factor_contributions"]
    assert record["new"]["signal_explanation"]["signal"] == record["new"]["signal"]
    assert "不是上涨概率" in record["new"]["confidence_semantics"]
    new = run("new")["analyst_signals"][f"{profile_id}_agent"]["600519"]
    assert new["signal"] == fixed.signal and new["confidence"] == fixed.confidence
    assert new["strengths"] == list(fixed.strengths) and new["risks"] == list(fixed.risks)
    assert "只改文字" in new["reasoning"]
    if profile_id == "feng_liu":
        assert "不能证明真实市场预期低" in new["reasoning"]


def test_workflow_returns_shadow_records_without_changing_legacy_analyst_signals(monkeypatch):
    from src.agents import a_share_investors as agents
    from src.agents import portfolio_manager, risk_manager
    from src.data.models import FinancialMetrics, Price
    from src.main import run_hedge_fund

    source = json.loads((ROOT / "docs/baselines/stage1_600519_before.json").read_text())
    metrics = [FinancialMetrics(**item) for item in source["financial_metrics"]["data"]]
    prices = [Price(**item) for item in source["prices"]["data"]]
    monkeypatch.setattr(agents, "get_financial_metrics", lambda *_args, **_kwargs: metrics)
    monkeypatch.setattr(agents, "get_prices", lambda *_args, **_kwargs: prices)
    monkeypatch.setattr(risk_manager, "get_prices", lambda *_args, **_kwargs: prices)
    monkeypatch.setattr(agents, "call_llm", lambda _prompt, model, **_kwargs: model(reasoning="固定解释"))
    monkeypatch.setattr(agents, "evaluate_ticker", lambda profile_id, *_args, **_kwargs:
                        StrategyEvaluator().evaluate(PILOT_PROFILES[profile_id], factors()))
    monkeypatch.setattr(portfolio_manager, "call_llm", lambda prompt=None, pydantic_model=None, **_kwargs:
                        pydantic_model(decisions={"600519": {"action": "hold", "quantity": 0,
                                                              "confidence": 50, "reasoning": "fixed"}}))
    portfolio = {"cash": 100000.0, "margin_requirement": 0.0, "margin_used": 0.0,
                 "positions": {"600519": {"long": 0, "short": 0, "long_cost_basis": 0.0,
                                           "short_cost_basis": 0.0, "short_margin_used": 0.0}},
                 "realized_gains": {"600519": {"long": 0.0, "short": 0.0}}}
    common = dict(tickers=["600519"], start_date="2026-03-25", end_date="2026-09-25",
                  portfolio=portfolio, selected_analysts=list(PILOT_PROFILES),
                  model_name="mock", model_provider="DeepSeek", progress_display=False)
    legacy = run_hedge_fund(**common, investor_mode="legacy")
    shadow = run_hedge_fund(**common, investor_mode="shadow")
    new = run_hedge_fund(**common, investor_mode="new")
    assert shadow["decisions"] == legacy["decisions"]
    assert shadow["analyst_signals"]["risk_management_agent"] == legacy["analyst_signals"]["risk_management_agent"]
    assert new["decisions"]["600519"]["action"] == "hold"
    assert "risk_management_agent" in new["analyst_signals"]
    for profile_id in PILOT_PROFILES:
        key = f"{profile_id}_agent"
        assert shadow["analyst_signals"][key] == legacy["analyst_signals"][key]
        assert shadow["investor_shadow"][key]["600519"]["new"]["used_factors"]
        assert new["analyst_signals"][key]["600519"]["used_factors"]


def test_new_agent_keeps_deterministic_result_when_llm_uses_fallback(monkeypatch):
    from src.agents import a_share_investors as agents

    expected = StrategyEvaluator().evaluate(PILOT_PROFILES["feng_liu"], factors())
    monkeypatch.setattr(agents, "evaluate_ticker", lambda *_args, **_kwargs: expected)
    monkeypatch.setattr(agents, "call_llm", lambda _prompt, _model, **kwargs:
                        kwargs["default_factory"]())
    state = {"messages": [], "data": {"tickers": ["600519"], "end_date": "2026-09-25",
                                      "analyst_signals": {}},
             "metadata": {"investor_mode": "new", "show_reasoning": False}}
    agents.investor_agent(state, profile_key="feng_liu")
    output = state["data"]["analyst_signals"]["feng_liu_agent"]["600519"]
    assert output["signal"] == expected.signal
    assert output["confidence"] == expected.confidence
    assert output["key_metrics"] == expected.key_metrics
    assert output["strengths"] == list(expected.strengths)
    assert output["risks"] == list(expected.risks)
    assert "不能证明真实市场预期低" in output["reasoning"]


def test_nonpilot_investor_ignores_new_mode(monkeypatch):
    from src.agents import a_share_investors as agents
    from src.data.models import FinancialMetrics, Price

    source = json.loads((ROOT / "docs/baselines/stage1_600519_before.json").read_text())
    metrics = [FinancialMetrics(**item) for item in source["financial_metrics"]["data"]]
    prices = [Price(**item) for item in source["prices"]["data"]]
    monkeypatch.setattr(agents, "get_financial_metrics", lambda *_args, **_kwargs: metrics)
    monkeypatch.setattr(agents, "get_prices", lambda *_args, **_kwargs: prices)
    monkeypatch.setattr(agents, "call_llm", lambda _prompt, model, **_kwargs: model(reasoning="固定解释"))
    monkeypatch.setattr(agents, "evaluate_ticker", lambda *_args, **_kwargs:
                        pytest.fail("nonpilot should remain on legacy"))
    state = {"messages": [], "data": {"tickers": ["600519"], "end_date": "2026-09-25",
                                      "analyst_signals": {}},
             "metadata": {"investor_mode": "new", "show_reasoning": False}}
    agents.investor_agent(state, profile_key="duan_yongping")
    assert state["data"]["analyst_signals"]["duan_yongping_agent"]["600519"]["signal"] == "bullish"
