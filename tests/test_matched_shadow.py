"""Deterministic, offline validation of frozen matched Investor evaluations."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sys
import warnings

import pandas as pd
import pytest
from pydantic import ValidationError

from src.data.domain import (
    Adjustment, CompanyProfile, DataEnvelope, DataStatus, FinancialField,
    FinancialStatement, ObservedValue, Quality,
    StatementType, Unit, ValuationSnapshot,
)
from src.factors.contracts import FactorContext, FactorStatus
from src.factors.engine import FactorEngine
from src.investors import PILOT_PROFILES, StrategyEvaluator
from src.investors.profiles import PROXY_ID
from src.investors.shadow import (
    FrozenDataSnapshot, MatchedShadowRunner, _freeze_context, _legacy_inputs,
    load_frozen_snapshot, save_frozen_snapshot, save_shadow_result,
)


ROOT = Path(__file__).resolve().parents[1]
GOLDEN = json.loads((ROOT / "tests/fixtures/factors/golden_v1.json").read_text())
CORPUS = json.loads((ROOT / "tests/fixtures/shadow/strategy_semantics_v1.json").read_text())


def factors(ticker="600519"):
    context = FactorContext.model_validate(GOLDEN["contexts"][ticker])
    return context, FactorEngine().evaluate(context)


def changed(results, factor_id, score, *, status=FactorStatus.AVAILABLE,
            coverage=Decimal(1), quality=None):
    result = dict(results)
    original = result[factor_id]
    update = {
        "normalized_score": Decimal(str(score)) if score is not None else None,
        "raw_value": Decimal(str(score)) if score is not None else None,
        "status": status,
        "coverage": coverage,
    }
    if quality is not None:
        update["quality"] = quality
    result[factor_id] = original.model_copy(update=update)
    return result


def _list_envelope(rows, provider, *, unit=Unit.NONE):
    if not rows:
        return DataEnvelope(status=DataStatus.EMPTY_SUCCESS, provider=provider,
                            reason="no fixture rows")
    avail = max(row.available_at for row in rows)
    retrieved = max(row.retrieved_at if hasattr(row, "retrieved_at") else avail for row in rows)
    dates = [getattr(row, "period_end", None) or getattr(row, "trading_date", None)
             or getattr(row, "observed_date", None) or getattr(row, "effective_date", None)
             or getattr(row, "ex_date", None) for row in rows]
    observed = max(day for day in dates if day is not None)
    return DataEnvelope(status=DataStatus.PRESENT, provider=provider,
        observation=ObservedValue(value=rows, provider=provider,
            observed_date=observed, period="fixture", available_at=avail,
            retrieved_at=max(retrieved, avail), unit=unit, quality=Quality.VALIDATED))


def snapshot_from_context(context):
    """Build provider-shaped frozen envelopes from the normalized golden fixture."""
    context = _freeze_context(context, context.as_of)
    bars = list(context.prices.bars)
    instrument = bars[0].instrument
    provider = context.prices.provenance.provider

    financial_statements = {}
    statement_specs = {
        "income_statement": (StatementType.INCOME,
            {"revenue", "net_income", "operating_income", "cost_of_revenue"}),
        "balance_sheet": (StatementType.BALANCE_SHEET,
            {"shareholders_equity", "short_term_debt", "current_portion_long_term_debt",
             "long_term_debt", "bonds_payable", "current_assets", "current_liabilities",
             "cash_and_equivalents"}),
        "cash_flow_statement": (StatementType.CASH_FLOW,
            {"operating_cash_flow", "capital_expenditure"}),
    }
    for key, (statement_type, names) in statement_specs.items():
        grouped = {}
        for name in names:
            series = context.metrics.get(name)
            for point in series.points if series else ():
                grouped.setdefault((point.observed_date, point.period), []).append(point)
        statements = []
        for (period_end, period), points in sorted(grouped.items()):
            statements.append(FinancialStatement(
                instrument=instrument, statement_type=statement_type,
                period_end=period_end, period=period,
                fields=tuple(FinancialField(name=point.metric_id, value=point.value,
                                            unit=point.provenance.unit) for point in points),
                available_at=max(point.provenance.available_at for point in points),
                revision=next((point.provenance.revision for point in points
                               if point.provenance.revision), None),
            ))
        financial_statements[key] = _list_envelope(statements, provider, unit=Unit.CNY)

    by_date = {}
    for name in ("pe", "pb", "ps"):
        series = context.metrics.get(name)
        for point in series.points if series else ():
            by_date.setdefault(point.observed_date, {})[name] = point
    closes = {bar.trading_date: bar.close for bar in bars}
    valuations = []
    for day, values in sorted(by_date.items()):
        points = list(values.values())
        valuations.append(ValuationSnapshot(
            instrument=instrument, observed_date=day,
            pe=values["pe"].value if "pe" in values else None,
            pb=values["pb"].value if "pb" in values else None,
            ps=values["ps"].value if "ps" in values else None,
            close=closes.get(day), provider=provider,
            available_at=max(item.provenance.available_at for item in points),
            retrieved_at=max(item.provenance.retrieved_at for item in points),
            quality=Quality.VALIDATED,
        ))
    valuation_history = _list_envelope(valuations, provider, unit=Unit.MULTIPLE)
    price_history = DataEnvelope(status=DataStatus.PRESENT, provider=provider,
        observation=ObservedValue(value=bars, provider=provider,
            observed_date=bars[-1].trading_date, period="daily",
            available_at=context.prices.provenance.available_at,
            retrieved_at=context.prices.provenance.retrieved_at,
            unit=context.prices.provenance.unit,
            quality=context.prices.provenance.quality))
    empty_shares = DataEnvelope(status=DataStatus.EMPTY_SUCCESS, provider="synthetic_fixture",
                                reason="fixture does not include dated share-capital events")
    no_industry = DataEnvelope(status=DataStatus.MISSING, provider="synthetic_fixture",
                               reason="fixture does not include industry metadata")
    no_dividends = DataEnvelope(status=DataStatus.EMPTY_SUCCESS, provider="synthetic_fixture",
                                reason="fixture does not include dividend events")
    return FrozenDataSnapshot(
        ticker=context.ticker, as_of=context.as_of,
        adjustment_mode=bars[0].adjustment,
        financial_statements=financial_statements,
        price_history=price_history, valuation_history=valuation_history,
        share_capital_history=empty_shares, industry=no_industry,
        dividends=no_dividends, factor_context=context,
        capability_statuses={"fixture": DataStatus.PRESENT},
    )


def test_snapshot_roundtrip_is_stable_and_binds_the_matched_input_hash(tmp_path):
    context, _ = factors()
    frozen = snapshot_from_context(context)
    restored = FrozenDataSnapshot.model_validate_json(frozen.model_dump_json())
    assert restored == frozen
    assert restored.snapshot_id == frozen.snapshot_id

    path = tmp_path / "frozen.json"
    path.write_text(frozen.model_dump_json(indent=2), encoding="utf-8")
    loaded = load_frozen_snapshot(path)
    assert loaded == frozen and loaded.snapshot_id == frozen.snapshot_id
    saved = save_frozen_snapshot(frozen, tmp_path / "snapshots")
    assert load_frozen_snapshot(saved) == frozen


def test_snapshot_rejects_future_publication_and_wrong_adjustment_or_ticker():
    context, _ = factors()
    frozen = snapshot_from_context(context)
    future_context = context.model_copy(deep=True)
    metric = future_context.metrics["revenue"]
    future_context.metrics["revenue"] = metric.model_copy(update={
        "points": (metric.points[0].model_copy(update={"provenance":
            metric.points[0].provenance.model_copy(update={
                "available_at": datetime(2027, 1, 1, tzinfo=timezone.utc)})}), *metric.points[1:])})
    payload = frozen.model_dump(mode="python")
    payload["factor_context"] = future_context
    with pytest.raises(ValidationError, match="published after snapshot as_of"):
        FrozenDataSnapshot.model_validate(payload)

    with pytest.raises(ValidationError, match="price bars do not match"):
        FrozenDataSnapshot.model_validate({**frozen.model_dump(mode="python"),
                                           "adjustment_mode": Adjustment.FORWARD})
    with pytest.raises(ValueError, match="ticker/as_of"):
        MatchedShadowRunner().run("000001", PILOT_PROFILES["zhang_kun"],
                                  frozen.as_of, frozen)


def test_runner_uses_one_frozen_ticker_time_price_series_and_never_calls_provider(monkeypatch):
    context, _ = factors()
    frozen = snapshot_from_context(context)

    def fail(*_args, **_kwargs):
        pytest.fail("MatchedShadowRunner must not make provider requests")

    monkeypatch.setattr("src.data.pipeline.DataService.fetch", fail)
    monkeypatch.setattr("src.data.pipeline.DataService.get_financial_statements", fail)
    factor_results = FactorEngine().evaluate(context)
    legacy_raw, _, legacy_bars = _legacy_inputs(frozen, factor_results)
    assert legacy_raw["return_on_equity"] is not None
    assert [date.fromisoformat(item.time) for item in legacy_bars] == [
        point.observed_date for point in factor_results["momentum_6m"].inputs]
    assert [item.close for item in legacy_bars] == [
        float(point.value) for point in factor_results["momentum_6m"].inputs]
    assert all(item.adjustment is frozen.adjustment_mode for item in context.prices.bars)

    matched = MatchedShadowRunner().run(frozen.ticker, PILOT_PROFILES["zhang_kun"],
                                         frozen.as_of, frozen)
    assert matched.ticker == frozen.ticker and matched.as_of == frozen.as_of
    assert matched.snapshot_id == frozen.snapshot_id
    assert matched.difference.ticker == matched.ticker
    assert matched.difference.as_of == matched.as_of
    assert matched.difference.legacy_factor_scores == matched.legacy.factor_scores
    assert matched.difference.new_factor_scores == {
        item.factor_id: item.score for item in matched.new.used_factors}
    assert matched.difference.new_factor_versions == {
        item.factor_id: item.version for item in matched.new.used_factors}
    assert set(matched.difference.threshold_effect.model_dump()) >= {
        "legacy_bullish_at", "legacy_bearish_at", "new_bullish_at",
        "new_bearish_at", "new_policy_style", "new_reason_code",
    }


def test_factor_contributions_reconcile_strategy_score_and_explain_signal_path():
    _, evaluated = factors()
    result = StrategyEvaluator().evaluate(PILOT_PROFILES["zhang_kun"], evaluated)
    contributions = [item.weighted_contribution for item in result.contributions
                     if item.weighted_contribution is not None]
    assert sum(contributions, Decimal(0)) == result.strategy_score
    assert len(result.contributions) == len(result.used_factors)
    for contribution in result.contributions:
        assert contribution.factor_id in {item.factor_id for item in result.used_factors}
        if contribution.score is not None:
            assert contribution.inputs and contribution.provenance
            assert contribution.provenance == tuple(
                source for point in contribution.inputs
                for source in (point.provenance, *point.source_inputs))
    path = result.signal_explanation
    assert path is not None and path.signal == result.signal
    assert path.strategy_score == result.strategy_score
    assert path.policy_style == PILOT_PROFILES["zhang_kun"].signal_policy.style
    assert path.reason_code


def test_missing_capability_explanations_have_deterministic_order():
    _, baseline = factors()
    profile = PILOT_PROFILES["zhang_kun"]
    unavailable = dict(baseline)
    for factor_id in profile.core_factors:
        unavailable = changed(unavailable, factor_id, None,
                              status=FactorStatus.UNAVAILABLE, coverage=Decimal(0))

    result = StrategyEvaluator().evaluate(profile, unavailable)
    explanation = next(item for item in result.limitations
                       if item.startswith("关键能力证据不可用："))
    capabilities = explanation.split("：", maxsplit=1)[1].split("、")
    assert capabilities == sorted(capabilities)


def test_difference_report_contains_legacy_new_and_effect_fields():
    context, _ = factors("000001")
    frozen = snapshot_from_context(context)
    result = MatchedShadowRunner().run(frozen.ticker, PILOT_PROFILES["feng_liu"],
                                        frozen.as_of, frozen)
    diff = result.difference
    assert diff.legacy_factor_values == result.legacy.factor_values
    assert diff.legacy_factor_scores == result.legacy.factor_scores
    assert diff.legacy_signal == result.legacy.signal
    assert diff.legacy_confidence == result.legacy.confidence
    assert diff.new_used_factors == result.new.used_factors
    assert diff.new_strategy_score == result.new.strategy_score
    assert diff.new_signal == result.new.signal
    assert diff.new_confidence == result.new.confidence
    assert diff.new_core_coverage == result.new.core_coverage
    assert diff.new_supporting_coverage == result.new.supporting_coverage
    assert diff.new_overall_coverage == result.new.overall_coverage
    assert diff.new_limitations == result.new.limitations
    assert diff.matched_inputs.adjustment_mode == frozen.adjustment_mode
    assert diff.matched_inputs.price_rows == len(frozen.price_history.observation.value)
    assert diff.matched_inputs.provider_ids["price_adjusted"] == "synthetic_fixture"
    assert isinstance(diff.factors_added, list) and isinstance(diff.factors_removed, list)
    assert isinstance(diff.factor_formula_changes, dict)
    assert isinstance(diff.missing_data_effect, list)
    assert diff.threshold_effect.new_reason_code
    assert isinstance(diff.signal_changed, bool)
    assert isinstance(diff.confidence_delta, float)


def test_legacy_price_input_uses_exact_new_momentum_window_and_adjusted_values():
    context, _ = factors()
    template = context.prices.bars[0]
    days = [context.as_of.date() - timedelta(days=250 - 2 * index)
            for index in range(126)]
    prices = []
    for index, day in enumerate(days):
        close = Decimal("100") + Decimal(index) / Decimal(10)
        prices.append(template.model_copy(update={
            "trading_date": day, "open": close, "high": close,
            "low": close, "close": close, "adjustment": Adjustment.BACKWARD,
        }))
    context.prices.bars = tuple(prices)
    context.prices.provenance = context.prices.provenance.model_copy(update={
        "observed_date": days[-1], "available_at": context.as_of,
        "retrieved_at": context.as_of,
    })
    frozen = snapshot_from_context(context)
    factor_results = FactorEngine().evaluate(context)
    new_momentum_dates = [point.observed_date
                          for point in factor_results["momentum_6m"].inputs]
    _, _, legacy_prices = _legacy_inputs(frozen, factor_results)
    assert len(new_momentum_dates) == len(legacy_prices) == 126
    assert new_momentum_dates == [date.fromisoformat(item.time) for item in legacy_prices]
    assert [float(item.close) for item in context.prices.bars] == [
        item.close for item in legacy_prices]


@pytest.mark.parametrize("status", [DataStatus.MISSING, DataStatus.PROVIDER_FAILURE,
                                    DataStatus.UNSUPPORTED, DataStatus.NOT_PUBLISHED,
                                    DataStatus.INVALID_QUALITY])
def test_non_present_data_states_remain_distinguishable(status):
    from src.investors.shadow import _freeze_envelope
    envelope = DataEnvelope(status=status, provider="fixture", reason="fixture state")
    assert _freeze_envelope(envelope, datetime(2026, 9, 27, tzinfo=timezone.utc),
                            lambda _item: None, lambda _item: None).status is status


def test_zhang_kun_long_term_quality_behaviors():
    _, base = factors()
    profile = PILOT_PROFILES["zhang_kun"]
    strong = base
    for key, value in (("profitability_quality", 0.9), ("cash_conversion", 0.9),
                       ("balance_sheet_safety", 0.8), ("margin_trend", 0.7),
                       ("momentum_6m", -0.95)):
        strong = changed(strong, key, value)
    result = StrategyEvaluator().evaluate(profile, strong)
    assert result.signal != "bearish"
    assert result.strategy_score > 0
    assert "价格走弱不单独推翻" in result.interpretations["momentum_6m"]

    weak_cash = base
    for key, value in (("profitability_quality", 0.95), ("cash_conversion", -0.95),
                       ("balance_sheet_safety", -0.35), ("margin_trend", -0.8)):
        weak_cash = changed(weak_cash, key, value)
    weak = StrategyEvaluator().evaluate(profile, weak_cash)
    assert weak.signal != "bullish"
    assert any("现金转化不足" in item or "利润率持续承压" in item for item in weak.risks)

    expensive_quality = base
    for key, value in (("profitability_quality", 0.9), ("cash_conversion", 0.8),
                       ("balance_sheet_safety", 0.8), ("margin_trend", 0.7),
                       ("valuation_level", -0.95)):
        expensive_quality = changed(expensive_quality, key, value)
    expensive = StrategyEvaluator().evaluate(profile, expensive_quality)
    assert any("估值" in risk for risk in expensive.risks)
    assert any("盈利质量" in strength or "现金流" in strength for strength in expensive.strengths)


def _feng_case(base, *, business, price, cheap=0.8):
    result = base
    for key, value in (("valuation_level", cheap), ("valuation_percentile", cheap),
                       ("drawdown_6m", price), ("momentum_1m", price),
                       ("growth_acceleration", business), ("margin_trend", business),
                       ("earnings_growth_yoy", business)):
        result = changed(result, key, value)
    return result


def test_feng_liu_requires_price_proxy_and_operating_improvement():
    _, base = factors()
    profile = PILOT_PROFILES["feng_liu"]
    deteriorating = StrategyEvaluator().evaluate(profile,
        _feng_case(base, business=-0.9, price=-0.9))
    improving = StrategyEvaluator().evaluate(profile,
        _feng_case(base, business=0.9, price=-0.9))
    rank = {"bearish": -1, "neutral": 0, "bullish": 1}
    assert deteriorating.signal != "bullish"
    assert rank[improving.signal] > rank[deteriorating.signal]
    assert improving.strategy_score > deteriorating.strategy_score
    assert any("LOW_EXPECTATION_PROXY" in item for item in improving.limitations)
    proxy = next(item for item in improving.used_factors if item.factor_id == PROXY_ID)
    assert any("不代表真实市场预期" in item for item in proxy.limitations)

    no_confirmation = _feng_case(base, business=0.0, price=0.7, cheap=0.85)
    only_cheap = StrategyEvaluator().evaluate(profile, no_confirmation)
    assert only_cheap.signal != "bullish"
    assert only_cheap.signal_explanation.reason_code in {
        "improvement_below_gate", "proxy_not_established"}
    assert only_cheap.confidence <= 60


def test_fu_pengbo_growth_quality_behaviors():
    _, base = factors()
    profile = PILOT_PROFILES["fu_pengbo"]
    high_quality_slow = base
    improved_growth = base
    for key, value in (("revenue_growth_yoy", 0.5), ("earnings_growth_yoy", 0.45),
                       ("growth_acceleration", -0.95), ("profitability_quality", 0.9),
                       ("cash_conversion", 0.75)):
        high_quality_slow = changed(high_quality_slow, key, value)
    for key, value in (("revenue_growth_yoy", 0.5), ("earnings_growth_yoy", 0.45),
                       ("growth_acceleration", 0.95), ("profitability_quality", 0.9),
                       ("cash_conversion", 0.75)):
        improved_growth = changed(improved_growth, key, value)
    slow = StrategyEvaluator().evaluate(profile, high_quality_slow)
    accelerated = StrategyEvaluator().evaluate(profile, improved_growth)
    assert accelerated.strategy_score - slow.strategy_score >= Decimal("0.25")
    assert any("成长明显减速" in risk or "成长质量冲突" in risk for risk in slow.risks)

    poor_quality_high_growth = base
    for key, value in (("revenue_growth_yoy", 0.95), ("earnings_growth_yoy", 0.9),
                       ("growth_acceleration", 0.9), ("profitability_quality", -0.95),
                       ("cash_conversion", -0.95), ("balance_sheet_safety", -0.9)):
        poor_quality_high_growth = changed(poor_quality_high_growth, key, value)
    poor = StrategyEvaluator().evaluate(profile, poor_quality_high_growth)
    assert poor.confidence < 80
    assert "profitability_quality" not in poor.strengths
    assert "cash_conversion" not in poor.key_metrics or poor.key_metrics["cash_conversion"]["value"] < 0

    balanced_growth = base
    for key, value in (("revenue_growth_yoy", 0.8), ("earnings_growth_yoy", 0.8),
                       ("growth_acceleration", 0.7), ("profitability_quality", 0.8),
                       ("cash_conversion", 0.7), ("valuation_level", 0.25)):
        balanced_growth = changed(balanced_growth, key, value)
    balanced = StrategyEvaluator().evaluate(profile, balanced_growth)
    assert balanced.signal == "bullish"
    assert balanced.strengths


def test_confidence_is_monotonic_in_core_coverage_and_data_quality():
    _, baseline = factors()
    profile = PILOT_PROFILES["zhang_kun"]
    evaluator = StrategyEvaluator()
    full = evaluator.evaluate(profile, baseline)

    partial = baseline
    for factor_id in profile.core_factors:
        partial = changed(partial, factor_id,
            baseline[factor_id].normalized_score, status=FactorStatus.PARTIAL,
            coverage=Decimal("0.75"))
    reduced = evaluator.evaluate(profile, partial)
    assert reduced.strategy_score == full.strategy_score
    assert reduced.core_coverage == Decimal("0.75")
    assert full.confidence >= reduced.confidence

    degraded = baseline
    for factor_id in profile.factor_ids:
        factor = baseline[factor_id]
        if factor.normalized_score is not None:
            degraded = changed(degraded, factor_id, factor.normalized_score,
                status=FactorStatus.DEGRADED, coverage=factor.coverage,
                quality=Quality.DEGRADED)
    poor_quality = evaluator.evaluate(profile, degraded)
    assert full.confidence >= poor_quality.confidence

    insufficient = changed(baseline, "cash_conversion", None,
                           status=FactorStatus.INSUFFICIENT_HISTORY, coverage=Decimal(0))
    short_history = evaluator.evaluate(profile, insufficient)
    assert full.confidence >= short_history.confidence
    assert "历史长度不足" in " ".join(short_history.limitations)

    feng = PILOT_PROFILES["feng_liu"]
    feng_full = evaluator.evaluate(feng, baseline)
    no_proxy_inputs = dict(baseline)
    for factor_id in ("valuation_level", "valuation_percentile", "drawdown_6m", "momentum_1m"):
        no_proxy_inputs = changed(no_proxy_inputs, factor_id, None,
                                  status=FactorStatus.UNAVAILABLE, coverage=Decimal(0))
    proxy_missing = evaluator.evaluate(feng, no_proxy_inputs)
    assert feng_full.confidence <= 60
    assert proxy_missing.confidence < feng_full.confidence


def test_signal_monotonicity_for_each_profile_and_profile_gate():
    _, baseline = factors()
    evaluator = StrategyEvaluator()
    rank = {"bearish": -1, "neutral": 0, "bullish": 1}
    for profile_id in PILOT_PROFILES:
        profile = PILOT_PROFILES[profile_id]
        signals = []
        for step in range(-4, 5):
            x = Decimal(step) / Decimal(4)
            candidate = baseline
            for factor_id in profile.core_factors:
                if factor_id == PROXY_ID:
                    continue
                candidate = changed(candidate, factor_id, x)
            if profile_id == "feng_liu":
                for factor_id in ("valuation_level", "valuation_percentile"):
                    candidate = changed(candidate, factor_id, x)
                for factor_id in ("drawdown_6m", "momentum_1m"):
                    candidate = changed(candidate, factor_id, -x)
            result = evaluator.evaluate(profile, candidate)
            signals.append(rank[result.signal])
        assert signals == sorted(signals), (profile_id, signals)

    _, current = factors()
    no_proxy = dict(current)
    for factor_id in ("valuation_level", "valuation_percentile", "drawdown_6m", "momentum_1m"):
        original = no_proxy[factor_id]
        no_proxy[factor_id] = original.model_copy(update={
            "normalized_score": None, "raw_value": None,
            "status": FactorStatus.UNAVAILABLE, "coverage": Decimal(0)})
    gated = evaluator.evaluate(PILOT_PROFILES["feng_liu"], no_proxy)
    assert gated.signal != "bullish"
    assert gated.signal_explanation.gate_id == "low_expectation_proxy_and_operating_improvement"
    assert gated.signal_explanation.gate_passed is False


def test_key_metrics_only_include_used_profile_factors_and_profiles_differ():
    _, results = factors()
    outputs = {profile_id: StrategyEvaluator().evaluate(profile, results)
               for profile_id, profile in PILOT_PROFILES.items()}
    for profile_id, output in outputs.items():
        profile = PILOT_PROFILES[profile_id]
        contribution_by_id = {item.factor_id: item for item in output.contributions}
        expected = [factor_id for factor_id in profile.key_metric_priority
                    if contribution_by_id[factor_id].score is not None
                    and contribution_by_id[factor_id].raw_value is not None]
        assert list(output.key_metrics) == expected
        assert set(output.key_metrics) <= set(profile.factor_ids)
    assert len({tuple(output.key_metrics) for output in outputs.values()}) == 3
    assert len({(output.strengths, output.risks) for output in outputs.values()}) > 1


def test_corpus_has_twelve_label_free_semantic_scenarios():
    scenarios = CORPUS["scenarios"]
    assert len(scenarios) >= 12
    assert len({item["id"] for item in scenarios}) == len(scenarios)
    assert all("expected_signal" not in item and "ticker" not in item for item in scenarios)
    _, base = factors()
    for scenario in scenarios:
        candidate = dict(base)
        for factor_id, value in scenario.get("overrides", {}).items():
            candidate = changed(candidate, factor_id, value)
        for factor_id in scenario.get("missing_factors", []):
            candidate = changed(candidate, factor_id, None,
                status=FactorStatus.UNAVAILABLE, coverage=Decimal(0))
        profile = PILOT_PROFILES[scenario["profile_id"]]
        output = StrategyEvaluator().evaluate(profile, candidate)
        assert output.profile_id == profile.profile_id
        assert output.signal_explanation.signal == output.signal
        assert output.contributions
        assert set(output.key_metrics) <= set(profile.factor_ids)


def test_shadow_result_persists_as_atomic_json_record_without_credentials(tmp_path):
    context, _ = factors()
    frozen = snapshot_from_context(context)
    result = MatchedShadowRunner().run(frozen.ticker, PILOT_PROFILES["zhang_kun"],
                                        frozen.as_of, frozen)
    path = save_shadow_result(result, tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["snapshot_id"] == frozen.snapshot_id
    assert payload["difference"]["ticker"] == frozen.ticker
    assert not path.with_suffix(path.suffix + ".tmp").exists()
    assert "api_key" not in path.read_text(encoding="utf-8").lower()


def test_capture_cli_hides_provider_banners_and_akshare_warning_by_default(
        monkeypatch, capsys, tmp_path):
    from scripts import run_matched_shadow_validation as cli

    context, _ = factors()
    frozen = snapshot_from_context(context)

    def noisy_capture(*_args, **_kwargs):
        print("login success!")
        warnings.warn("third-party dataframe warning",
                      category=pd.errors.SettingWithCopyWarning)
        return frozen

    monkeypatch.setattr(FrozenDataSnapshot, "capture_current", noisy_capture)
    monkeypatch.setattr(sys, "argv", ["run_matched_shadow_validation.py", "600519",
                                      "--output-dir", str(tmp_path)])
    assert cli.main() == 0
    output = capsys.readouterr().out
    assert "login success" not in output
    assert "third-party dataframe warning" not in output
    assert "MATCHED 600519" in output


def test_live_catalog_replays_all_matched_results_without_provider_access(monkeypatch):
    """Live captures are replayable fixtures, not hand-assigned signal labels."""
    root = ROOT / "docs/baselines/shadow/live"
    catalog = json.loads((root / "catalog.json").read_text(encoding="utf-8"))
    entries = catalog["entries"]
    assert catalog["schema_version"] == 1
    assert len(entries) >= 18
    assert len({item["ticker"] for item in entries}) == len(entries)
    assert all("expected_signal" not in item for item in entries)

    def provider_access_is_a_test_failure(*_args, **_kwargs):
        pytest.fail("catalog replay must not access a live Provider")

    monkeypatch.setattr("src.data.pipeline.DataService.fetch", provider_access_is_a_test_failure)
    monkeypatch.setattr("src.data.pipeline.DataService.get_financial_statements",
                        provider_access_is_a_test_failure)
    runner = MatchedShadowRunner()
    replayed = 0
    for entry in entries:
        frozen = load_frozen_snapshot(root / entry["snapshot"])
        assert frozen.ticker == entry["ticker"]
        assert frozen.as_of.isoformat().replace("+00:00", "Z") == entry["as_of"]
        assert frozen.snapshot_id == entry["snapshot_id"]
        assert set(entry["matched_results"]) == set(PILOT_PROFILES)

        for profile_id, reference in entry["matched_results"].items():
            profile = PILOT_PROFILES[profile_id]
            assert profile.version == reference["profile_version"]
            expected = json.loads((root / reference["path"]).read_text(encoding="utf-8"))
            actual = runner.run(frozen.ticker, profile, frozen.as_of, frozen)
            assert actual.model_dump(mode="json") == expected
            replayed += 1

    assert replayed == len(entries) * len(PILOT_PROFILES)
