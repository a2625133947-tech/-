"""Deterministic tests for Phase B5 Shadow-Only Investor Expansion."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import pytest

from src.data.capabilities import Capability
from src.factors.contracts import FactorContext, FactorResult, FactorStatus, FactorType
from src.factors.engine import FactorEngine, default_registry
from src.investors.contracts import InvestorMode, InvestorProfile
from src.investors.engine import StrategyEvaluator
from src.investors.profiles import (
    EXPANDED_PROFILES, PILOT_PROFILES, PROXY_ID, SHADOW_PROFILES,
    get_profile,
)
from src.investors.shadow import (
    FrozenDataSnapshot, MatchedShadowRunner, load_frozen_snapshot,
)
from src.investors.collector import SnapshotCollector, TemporalCatalog

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_600519 = ROOT / "docs/baselines/shadow/live/snapshots/600519_20260927T141212Z_d37d7fdaef87.snapshot.json"
SNAPSHOT_300750 = ROOT / "docs/baselines/shadow/live/snapshots/300750_20260927T143013Z_79b0f3ff3c07.snapshot.json"


def _build_synthetic_factor_set(as_of: datetime, overrides: dict[str, Decimal]) -> dict[str, FactorResult]:
    """Helper to build a complete dictionary of FactorResults with specified score overrides."""
    registry = default_registry()
    results = {}
    for factor in registry.list():
        fid = factor.factor_id
        score = overrides.get(fid, Decimal("0.0"))
        results[fid] = FactorResult(
            factor_id=fid,
            version=factor.version,
            factor_type=FactorType.DIRECT,
            normalized_score=score,
            raw_value=score,
            status=FactorStatus.AVAILABLE,
            coverage=Decimal("1.0"),
            as_of=as_of,
            window=factor.time_horizon,
            inputs=(),
            provenance=(),
            limitations=(),
        )
    return results


# ==============================================================================
# 1. Profile Registration and Factor Validity
# ==============================================================================


def test_expanded_profiles_registration_and_factor_validity():
    """Verify all 7 expanded profiles are properly registered and reference valid factors."""
    registry = default_registry()
    valid_factor_ids = {f.factor_id for f in registry.list()} | {PROXY_ID}

    expected_expanded = {
        "duan_yongping", "deng_xiaofeng", "zhu_shaoxing",
        "liu_yanchun", "xie_zhiyu", "dong_chengfei", "chen_guangming",
    }
    assert set(EXPANDED_PROFILES.keys()) == expected_expanded
    assert len(SHADOW_PROFILES) == 10

    # Wang Yawei and Lin Yuan must NOT be in shadow profiles
    assert "wang_yawei" not in SHADOW_PROFILES
    assert "lin_yuan" not in SHADOW_PROFILES

    for pid, profile in EXPANDED_PROFILES.items():
        assert profile.version == "v1"
        assert len(profile.core_factors) >= 3
        assert len(profile.known_missing_dimensions) >= 2

        # Check every referenced factor exists in the actual Factor Engine
        for fid in profile.factor_ids:
            assert fid in valid_factor_ids, f"Profile {pid} references unknown factor {fid}"
            assert profile.factor_versions[fid] == "v1"

        # Explicitly verify no non-existent volatility_6m is referenced
        assert "volatility_6m" not in profile.factor_ids
        if pid == "dong_chengfei":
            assert "volatility_3m" in profile.factor_ids


def test_profile_semantic_differentiation():
    """Verify CORE factor sets, interpretations, and missing policies are genuinely distinct."""
    core_sets = [set(p.core_factors) for p in EXPANDED_PROFILES.values()]
    # No two expanded profiles should have the identical core factor set
    for i in range(len(core_sets)):
        for j in range(i + 1, len(core_sets)):
            assert core_sets[i] != core_sets[j], f"Profiles have duplicate core factor sets"

    # Interpretations for shared factors (e.g. valuation_percentile) must be investor-specific
    vp_interps = {pid: p.interpretation_rules.get("valuation_percentile")
                  for pid, p in EXPANDED_PROFILES.items() if "valuation_percentile" in p.interpretation_rules}
    assert len(set(str(v) for v in vp_interps.values())) == len(vp_interps), "Interpretations must be differentiated"


# ==============================================================================
# 2. Synthetic Strategy Semantics & Gate Tests
# ==============================================================================


def test_synthetic_semantics_duan_yongping_quality_dominates_short_term():
    """Duan Yongping: High quality business should not be dominated by short-term price drop."""
    evaluator = StrategyEvaluator()
    profile = get_profile("duan_yongping")
    as_of = datetime(2026, 9, 27, tzinfo=timezone.utc)

    # High business quality, strong balance sheet, solid cash, cheap valuation
    factors = _build_synthetic_factor_set(as_of, {
        "profitability_quality": Decimal("0.80"),
        "cash_conversion": Decimal("0.80"),
        "balance_sheet_safety": Decimal("0.80"),
        "margin_trend": Decimal("0.50"),
        "valuation_level": Decimal("0.50"),
        "valuation_percentile": Decimal("0.50"),
        "revenue_cagr_3y": Decimal("0.60"),
        # Severe short-term price decline
        "momentum_6m": Decimal("-0.90"),
        "drawdown_6m": Decimal("-0.90"),
    })

    res = evaluator.evaluate(profile, factors)
    assert res.signal == "bullish"
    assert res.strategy_score is not None and res.strategy_score >= Decimal("0.60")
    # Momentum does not dominate
    assert "momentum_6m" not in [f.factor_id for f in res.used_factors]


def test_synthetic_semantics_deng_xiaofeng_cheap_valuation_vs_operating_deterioration():
    """Deng Xiaofeng: Cheap valuation cannot be bullish when earnings and margins continue deteriorating."""
    evaluator = StrategyEvaluator()
    profile = get_profile("deng_xiaofeng")
    as_of = datetime(2026, 9, 27, tzinfo=timezone.utc)

    # Very cheap valuation, but operating turnaround fails (earnings and margins deteriorating)
    factors = _build_synthetic_factor_set(as_of, {
        "valuation_level": Decimal("0.90"),
        "valuation_percentile": Decimal("0.90"),
        "earnings_growth_yoy": Decimal("-0.60"),
        "margin_trend": Decimal("-0.50"),
        "profitability_quality": Decimal("0.10"),
        "balance_sheet_safety": Decimal("0.40"),
    })

    res = evaluator.evaluate(profile, factors)
    # Gate blocks bullish!
    assert res.signal != "bullish"
    assert res.signal_explanation.gate_passed is False
    assert res.signal_explanation.reason_code == "operating_deterioration_blocks_turnaround"
    assert "价值陷阱风险" in " ".join(res.risks)


def test_synthetic_semantics_zhu_shaoxing_growth_vs_weak_quality():
    """Zhu Shaoxing: High growth cannot get an unconditional bullish signal when quality is severely weak."""
    evaluator = StrategyEvaluator()
    profile = get_profile("zhu_shaoxing")
    as_of = datetime(2026, 9, 27, tzinfo=timezone.utc)

    # Blistering growth, but negative cash flow and deteriorating ROE
    factors = _build_synthetic_factor_set(as_of, {
        "revenue_growth_yoy": Decimal("0.95"),
        "growth_acceleration": Decimal("0.80"),
        "valuation_level": Decimal("0.30"),
        "profitability_quality": Decimal("-0.40"),
        "cash_conversion": Decimal("-0.50"),
        "balance_sheet_safety": Decimal("0.20"),
        "margin_trend": Decimal("0.10"),
    })

    res = evaluator.evaluate(profile, factors)
    assert res.signal != "bullish"
    assert res.signal_explanation.gate_passed is False
    assert res.signal_explanation.reason_code == "weak_quality_blocks_growth"


def test_synthetic_semantics_liu_yanchun_high_margins_vs_growth_contraction():
    """Liu Yanchun: High past margins cannot be bullish when consumer revenue and profit are contracting."""
    evaluator = StrategyEvaluator()
    profile = get_profile("liu_yanchun")
    as_of = datetime(2026, 9, 27, tzinfo=timezone.utc)

    factors = _build_synthetic_factor_set(as_of, {
        "profitability_quality": Decimal("0.85"),
        "margin_trend": Decimal("0.40"),
        "cash_conversion": Decimal("0.60"),
        "revenue_cagr_3y": Decimal("0.50"),
        "valuation_level": Decimal("0.20"),
        # Demand sharply contracting
        "revenue_growth_yoy": Decimal("-0.45"),
        "earnings_growth_yoy": Decimal("-0.50"),
    })

    res = evaluator.evaluate(profile, factors)
    assert res.signal != "bullish"
    assert res.signal_explanation.gate_passed is False
    assert res.signal_explanation.reason_code == "revenue_contraction_blocks_bullish"


def test_synthetic_semantics_xie_zhiyu_growth_deceleration_drag():
    """Xie Zhiyu: Growth deceleration drags down the strategy and blocks bullish signal."""
    evaluator = StrategyEvaluator()
    profile = get_profile("xie_zhiyu")
    as_of = datetime(2026, 9, 27, tzinfo=timezone.utc)

    # Growth slowing sharply with stagnant earnings
    factors = _build_synthetic_factor_set(as_of, {
        "growth_acceleration": Decimal("-0.60"),
        "earnings_growth_yoy": Decimal("-0.10"),
        "revenue_growth_yoy": Decimal("0.10"),
        "valuation_level": Decimal("0.40"),
        "profitability_quality": Decimal("0.30"),
        "valuation_percentile": Decimal("0.30"),
        "balance_sheet_safety": Decimal("0.30"),
    })

    res = evaluator.evaluate(profile, factors)
    assert res.signal != "bullish"
    assert res.signal_explanation.gate_passed is False
    assert res.signal_explanation.reason_code == "growth_deceleration_blocks_bullish"


def test_synthetic_semantics_dong_chengfei_balance_sheet_risk_blocks_bullish():
    """Dong Chengfei: Financial fragility and debt risk block bullish even if valuation is low."""
    evaluator = StrategyEvaluator()
    profile = get_profile("dong_chengfei")
    as_of = datetime(2026, 9, 27, tzinfo=timezone.utc)

    # Cheap valuation, but excessive leverage and debt risk
    factors = _build_synthetic_factor_set(as_of, {
        "valuation_level": Decimal("0.80"),
        "valuation_percentile": Decimal("0.80"),
        "cash_conversion": Decimal("0.40"),
        "profitability_quality": Decimal("0.20"),
        "drawdown_6m": Decimal("0.20"),
        "balance_sheet_safety": Decimal("-0.50"),
    })

    res = evaluator.evaluate(profile, factors)
    assert res.signal != "bullish"
    assert res.signal_explanation.gate_passed is False
    assert res.signal_explanation.reason_code == "balance_sheet_risk_blocks_bullish"


def test_synthetic_semantics_chen_guangming_cash_conversion_conflict():
    """Chen Guangming: High accounting ROE without cash backing cannot generate a bullish signal."""
    evaluator = StrategyEvaluator()
    profile = get_profile("chen_guangming")
    as_of = datetime(2026, 9, 27, tzinfo=timezone.utc)

    # High ROE but poor cash flow
    factors = _build_synthetic_factor_set(as_of, {
        "profitability_quality": Decimal("0.85"),
        "valuation_level": Decimal("0.60"),
        "balance_sheet_safety": Decimal("0.50"),
        "valuation_percentile": Decimal("0.50"),
        "cash_conversion": Decimal("-0.50"),
    })

    res = evaluator.evaluate(profile, factors)
    assert res.signal != "bullish"
    assert res.signal_explanation.gate_passed is False
    assert res.signal_explanation.reason_code == "weak_cash_conversion_blocks_bullish"


# ==============================================================================
# 3. Offline Replay Across All 18 Snapshots
# ==============================================================================


def test_offline_replay_all_18_snapshots_for_7_expanded_profiles():
    """Verify all 18 frozen snapshots replay all 7 expanded profiles without provider calls."""
    catalog = TemporalCatalog.load_or_create(ROOT / "docs/baselines/shadow/live/temporal_catalog.json")
    runner = MatchedShadowRunner()

    assert len(catalog.entries) == 18

    for entry in catalog.entries:
        snap_file = ROOT / "docs/baselines/shadow/live" / entry.snapshot_path
        snapshot = load_frozen_snapshot(snap_file)

        for pid, profile in EXPANDED_PROFILES.items():
            matched = runner.run(snapshot.ticker, profile, snapshot.as_of, snapshot)

            assert matched.ticker == snapshot.ticker
            assert matched.profile_version == "v1"
            assert matched.legacy.signal in ("bullish", "neutral", "bearish")
            assert matched.new.signal in ("bullish", "neutral", "bearish")
            assert 0.0 <= matched.new.confidence <= 100.0

            # Verify coverage semantics: strategy_evidence_coverage < implemented_factor_coverage
            assert matched.new.implemented_factor_coverage >= matched.new.strategy_evidence_coverage
            assert len(matched.new.known_missing_dimensions) >= 2


# ==============================================================================
# 4. Shadow Mode Safety and Agent Isolation
# ==============================================================================


def test_shadow_mode_preserves_legacy_production_output(monkeypatch):
    """Verify that in SHADOW mode, production analyst_signals strictly retains Legacy output."""
    from src.agents import a_share_investors as agents
    from src.data.models import FinancialMetrics, Price

    source = json.loads((ROOT / "docs/baselines/stage1_600519_before.json").read_text())
    metrics = [FinancialMetrics(**item) for item in source["financial_metrics"]["data"]]
    prices = [Price(**item) for item in source["prices"]["data"]]
    monkeypatch.setattr(agents, "get_financial_metrics", lambda *_args, **_kwargs: metrics)
    monkeypatch.setattr(agents, "get_prices", lambda *_args, **_kwargs: prices)
    monkeypatch.setattr(agents, "call_llm", lambda _prompt, model, **_kwargs: model(reasoning="测试分析理由"))

    mock_state = {
        "messages": [],
        "data": {
            "tickers": ["600519"],
            "end_date": "2026-09-27",
            "analyst_signals": {},
        },
        "metadata": {
            "investor_mode": "shadow",
            "show_reasoning": False,
        },
    }

    # Test with one of the expanded profiles (e.g. duan_yongping)
    res = agents.investor_agent(mock_state, profile_key="duan_yongping")

    # Production output must be present
    assert "duan_yongping_agent" in res["data"]["analyst_signals"]
    prod_signal = res["data"]["analyst_signals"]["duan_yongping_agent"]["600519"]
    assert "signal" in prod_signal
    assert "confidence" in prod_signal

    # investor_shadow must be populated with both legacy and new
    assert "investor_shadow" in res["data"]
    shadow_data = res["data"]["investor_shadow"]["duan_yongping_agent"]["600519"]
    assert "legacy" in shadow_data
    assert "new" in shadow_data
    assert shadow_data["new"]["profile_version"] == "v1"


def test_not_ready_investors_remain_strictly_legacy(monkeypatch):
    """Verify Wang Yawei and Lin Yuan never run New shadow evaluations."""
    from src.agents import a_share_investors as agents
    from src.data.models import FinancialMetrics, Price

    source = json.loads((ROOT / "docs/baselines/stage1_600519_before.json").read_text())
    metrics = [FinancialMetrics(**item) for item in source["financial_metrics"]["data"]]
    prices = [Price(**item) for item in source["prices"]["data"]]
    monkeypatch.setattr(agents, "get_financial_metrics", lambda *_args, **_kwargs: metrics)
    monkeypatch.setattr(agents, "get_prices", lambda *_args, **_kwargs: prices)
    monkeypatch.setattr(agents, "call_llm", lambda _prompt, model, **_kwargs: model(reasoning="测试分析理由"))

    mock_state = {
        "messages": [],
        "data": {
            "tickers": ["600519"],
            "end_date": "2026-09-27",
            "analyst_signals": {},
        },
        "metadata": {
            "investor_mode": "shadow",
            "show_reasoning": False,
        },
    }

    for key in ("wang_yawei", "lin_yuan"):
        res = agents.investor_agent(mock_state, profile_key=key)
        # Production output is Legacy
        assert f"{key}_agent" in res["data"]["analyst_signals"]
        # No shadow evaluation record should exist for NOT_READY investors
        assert f"{key}_agent" not in res["data"].get("investor_shadow", {})


# ==============================================================================
# 5. Snapshot Collector Integration
# ==============================================================================


def test_snapshot_collector_evaluates_all_10_shadow_profiles():
    """Verify collector runs shadow evaluation across all 10 profiles upon snapshot capture."""
    snapshot = load_frozen_snapshot(SNAPSHOT_600519)
    collector = SnapshotCollector()

    results = collector.run_shadow_evaluations(snapshot, save_results=False)
    assert len(results) == 10
    assert set(results.keys()) == set(SHADOW_PROFILES.keys())

    for pid, matched in results.items():
        assert matched.new.strategy_score is not None
        assert matched.new.signal in ("bullish", "neutral", "bearish")
