"""Deterministic, offline temporal and point-in-time shadow validation tests."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import pytest

from src.data.capabilities import Capability
from src.data.domain import DataEnvelope, DataStatus, Quality, Unit
from src.data.temporal import (
    PitSafetyLevel, TemporalCapabilityPolicy, TemporalClassification,
    filter_context_for_retrospective,
)
from src.factors.contracts import FactorStatus
from src.factors.engine import FactorEngine
from src.investors.contracts import InvestorProfile
from src.investors.profiles import PILOT_PROFILES, ZHANG_KUN_V1, get_pilot_profile
from src.investors.shadow import (
    FrozenDataSnapshot, load_frozen_snapshot,
)
from src.investors.collector import (
    SnapshotCollector, SnapshotRetentionPolicy, TemporalCatalog,
    compute_content_hash,
)
from src.investors.temporal import (
    TemporalDataPolicy, TemporalShadowRunner, TemporalValidationMode,
    build_pit_constrained_snapshot, build_strategy_trace,
)

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_600519 = ROOT / "docs/baselines/shadow/live/snapshots/600519_20260927T141212Z_d37d7fdaef87.snapshot.json"
SNAPSHOT_000333 = ROOT / "docs/baselines/shadow/live/snapshots/000333_20260927T143043Z_bc40030bfbab.snapshot.json"
SNAPSHOT_300750 = ROOT / "docs/baselines/shadow/live/snapshots/300750_20260927T143013Z_79b0f3ff3c07.snapshot.json"


# ==============================================================================
# 1. Temporal Capability Policy Tests
# ==============================================================================


def test_temporal_capability_policy_coverage_and_classifications():
    """Verify all capabilities have an explicit, grounded temporal policy."""
    policies = TemporalCapabilityPolicy.all_policies()
    assert len(policies) == len(Capability)

    # Statements must be historically reconstructible and PIT-safe
    for cap in (Capability.INCOME_STATEMENT, Capability.BALANCE_SHEET, Capability.CASH_FLOW_STATEMENT):
        pol = TemporalCapabilityPolicy.get_policy(cap)
        assert pol.classification is TemporalClassification.HISTORICALLY_RECONSTRUCTIBLE
        assert pol.pit_safety is PitSafetyLevel.PIT_SAFE
        assert pol.retrospective_eligible is True

    # Price adjusted must be archived-only and pit-partial
    price_pol = TemporalCapabilityPolicy.get_policy(Capability.PRICE_ADJUSTED)
    assert price_pol.classification is TemporalClassification.ARCHIVED_ONLY
    assert price_pol.pit_safety is PitSafetyLevel.PIT_PARTIAL
    assert price_pol.retrospective_eligible is False

    # Industry must be current-only
    ind_pol = TemporalCapabilityPolicy.get_policy(Capability.INDUSTRY)
    assert ind_pol.classification is TemporalClassification.CURRENT_ONLY
    assert ind_pol.pit_safety is PitSafetyLevel.CURRENT_ONLY
    assert ind_pol.retrospective_eligible is False


def test_retrospective_context_filtering_prevents_lookahead_and_current_backfill():
    snapshot = load_frozen_snapshot(SNAPSHOT_600519)
    # Target date: 2026-03-01 (before 2025 annual report publication)
    as_of = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
    filtered = filter_context_for_retrospective(snapshot.factor_context, as_of)

    assert filtered.as_of == as_of

    # In retrospective mode, price bars are NOT backfilled
    assert filtered.prices.status is DataStatus.NOT_AVAILABLE_FOR_DATE
    assert len(filtered.prices.bars) == 0

    # Valuation multiples from BaoStock are marked NOT_AVAILABLE_FOR_DATE
    assert filtered.metrics["pe"].source_status is DataStatus.NOT_AVAILABLE_FOR_DATE
    assert len(filtered.metrics["pe"].points) == 0

    # Statement metrics cannot contain points after 2026-03-01
    for name in ("net_income", "revenue", "operating_cash_flow"):
        series = filtered.metrics[name]
        for pt in series.points:
            assert pt.provenance.available_at <= as_of
            assert pt.observed_date <= as_of.date()


# ==============================================================================
# 2. Historical Financial Statement Point-in-Time Validation
# ==============================================================================


def test_historical_financial_validation_announcement_timeline():
    """Verify financial statements are invisible before announcement date and visible after."""
    snapshot = load_frozen_snapshot(SNAPSHOT_600519)
    runner = TemporalShadowRunner()
    profile = PILOT_PROFILES["zhang_kun"]

    # 600519 announcement dates in snapshot:
    # 2025 Annual: announced 2026-04-16 16:00:00 UTC
    # 2026 Q1: announced 2026-04-24 16:00:00 UTC
    # 2026 Q2: announced 2026-08-14 16:00:00 UTC
    t_before_annual = datetime(2026, 4, 15, 12, 0, tzinfo=timezone.utc)
    t_after_annual = datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc)
    t_after_q1 = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    t_after_q2 = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)

    res_before = runner.run("600519", profile, t_before_annual, snapshot)
    res_after = runner.run("600519", profile, t_after_annual, snapshot)
    res_q1 = runner.run("600519", profile, t_after_q1, snapshot)
    res_q2 = runner.run("600519", profile, t_after_q2, snapshot)

    # Before annual announcement: latest visible period must be 2025 Q3 (2025-09-30)
    assert res_before.latest_financial_period == "2025-09-30"

    # After annual announcement: latest period is 2025-12-31
    assert res_after.latest_financial_period == "2025-12-31"

    # After Q1 announcement: latest period is 2026-03-31
    assert res_q1.latest_financial_period == "2026-03-31"

    # After Q2 announcement: latest period is 2026-06-30
    assert res_q2.latest_financial_period == "2026-06-30"

    # Price factors in retrospective mode must remain NOT_AVAILABLE_AS_OF
    for res in (res_before, res_after, res_q1, res_q2):
        used_momentum = next(f for f in res.new.used_factors if f.factor_id == "momentum_6m")
        assert used_momentum.status is FactorStatus.NOT_AVAILABLE_AS_OF


# ==============================================================================
# 3. Snapshot Collector, Content Hash Deduplication & Retention Tests
# ==============================================================================


def test_content_hash_invariance_under_timestamp_shift():
    snapshot1 = load_frozen_snapshot(SNAPSHOT_600519)
    hash1 = compute_content_hash(snapshot1)

    # Shift as_of timestamp by 2 days, keeping data rows identical
    snapshot2 = snapshot1.model_copy(update={"as_of": snapshot1.as_of + timedelta(days=2)}, deep=True)
    hash2 = compute_content_hash(snapshot2)

    assert hash1 == hash2, "Content hash must be invariant when data payload is identical"


def test_snapshot_collector_deduplication_and_retention(tmp_path):
    catalog_path = tmp_path / "test_catalog.json"
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    snapshot = load_frozen_snapshot(SNAPSHOT_600519)

    # Mock DataService to return the loaded snapshot
    class FakeService:
        pass

    collector = SnapshotCollector(
        service=FakeService(),
        snapshot_dir=snapshot_dir,
        catalog_path=catalog_path,
    )

    # Monkeypatch FrozenDataSnapshot.capture_current to return snapshot
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(FrozenDataSnapshot, "capture_current", lambda ticker, service=None: snapshot)

        # First collection: initial baseline
        res1, event1 = collector.collect_ticker("600519")
        assert res1.status in ("SUCCESS", "VALIDATED")
        assert res1.retained is True
        assert "INITIAL_BASELINE" in res1.tags
        assert event1.is_duplicate is False

        # Second collection with identical data: detected as duplicate and NOT retained
        res2, event2 = collector.collect_ticker("600519")
        assert res2.status == "DUPLICATE"
        assert res2.retained is False
        assert "DUPLICATE_CONTENT" in res2.tags
        assert event2.is_duplicate is True


def test_retention_policy_preserves_earnings_and_corporate_milestones():
    policy = SnapshotRetentionPolicy()
    snapshot = load_frozen_snapshot(SNAPSHOT_600519)

    # Compare snapshot against itself -> regular or initial
    tags_initial = policy.classify_milestones(snapshot, None)
    assert "INITIAL_BASELINE" in tags_initial

    # Simulate earnings release by adding a dummy statement period to current
    snap_copy = snapshot.model_copy(deep=True)
    income_env = snap_copy.financial_statements["income_statement"]
    old_stmts = list(income_env.observation.value)
    new_stmt = old_stmts[-1].model_copy(update={"period_end": date(2027, 3, 31)}, deep=True)
    income_env.observation.value = old_stmts + [new_stmt]

    tags_earnings = policy.classify_milestones(snap_copy, snapshot)
    assert "EARNINGS_RELEASE" in tags_earnings


# ==============================================================================
# 4. Temporal Validation Matrix (Pilot Investor x Ticker x AsOf)
# ==============================================================================


@pytest.mark.parametrize("ticker, snap_file", [
    ("600519", SNAPSHOT_600519),
    ("000333", SNAPSHOT_000333),
    ("300750", SNAPSHOT_300750),
])
@pytest.mark.parametrize("pilot_key", ["zhang_kun", "feng_liu", "fu_pengbo"])
def test_temporal_validation_matrix_offline_reconstruction(ticker, snap_file, pilot_key):
    """Verify all pilot investors evaluate deterministically across tickers and historical dates."""
    snapshot = load_frozen_snapshot(snap_file)
    runner = TemporalShadowRunner()
    profile = PILOT_PROFILES[pilot_key]

    dates = [
        datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
        datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
    ]

    for as_of in dates:
        comp = runner.run(ticker, profile, as_of, snapshot)
        new_res = comp.new

        # Strict deterministic outputs
        assert new_res.signal in ("bullish", "neutral", "bearish")
        assert 0.0 <= new_res.confidence <= 100.0
        assert new_res.core_coverage >= 0.0
        assert new_res.strategy_score is None or (-1.0 <= float(new_res.strategy_score) <= 1.0)

        # Matched shadow comparison has difference report
        assert comp.difference.profile_version == profile.version
        assert comp.difference.investor == profile.display_name


# ==============================================================================
# 5. Temporal Strategy Trace & Transition Audits
# ==============================================================================


def test_strategy_trace_and_transitions_auditable():
    snapshot = load_frozen_snapshot(SNAPSHOT_600519)
    profile = PILOT_PROFILES["zhang_kun"]

    dates = [
        datetime(2026, 1, 15, tzinfo=timezone.utc),
        datetime(2026, 4, 15, tzinfo=timezone.utc),
        datetime(2026, 8, 15, tzinfo=timezone.utc),
    ]

    trace = build_strategy_trace("600519", profile, dates, snapshot)
    assert len(trace.points) == 3
    assert trace.ticker == "600519"
    assert trace.profile_version == "v2"

    # Check point continuity
    for pt in trace.points:
        assert pt.core_coverage > Decimal("0.8")
        assert "profitability_quality" in pt.key_factor_contributions

    # Confidence transitions must be cleanly recorded
    conf_transitions = trace.confidence_transitions()
    assert len(conf_transitions) == 2
    for t in conf_transitions:
        assert isinstance(t["delta"], float)


def test_signal_and_confidence_strict_determinism():
    """Identical inputs must yield exact identical signal, score, and confidence."""
    snapshot = load_frozen_snapshot(SNAPSHOT_600519)
    runner = TemporalShadowRunner()
    profile = PILOT_PROFILES["fu_pengbo"]
    as_of = datetime(2026, 5, 1, tzinfo=timezone.utc)

    res1 = runner.run("600519", profile, as_of, snapshot)
    res2 = runner.run("600519", profile, as_of, snapshot)

    assert res1.new.strategy_score == res2.new.strategy_score
    assert res1.new.signal == res2.new.signal
    assert res1.new.confidence == res2.new.confidence
    assert res1.new.signal_explanation == res2.new.signal_explanation


# ==============================================================================
# 6. Temporal Metamorphic Tests
# ==============================================================================


def test_metamorphic_zhang_kun_cash_conversion_monotonicity():
    """For Zhang Kun: improving cash conversion must not decrease strategy score."""
    from src.investors.engine import StrategyEvaluator
    profile = PILOT_PROFILES["zhang_kun"]
    evaluator = StrategyEvaluator()

    snapshot = load_frozen_snapshot(SNAPSHOT_600519)
    pit_snap = build_pit_constrained_snapshot(snapshot, datetime(2026, 5, 1, tzinfo=timezone.utc))
    engine = FactorEngine()
    factors_base = engine.evaluate(pit_snap.factor_context)

    # Base evaluation
    base_res = evaluator.evaluate(profile, factors_base)

    # Perturb cash_conversion score upwards
    factors_improved = dict(factors_base)
    cc_orig = factors_base["cash_conversion"]
    improved_score = min(Decimal("1.0"), (cc_orig.normalized_score or Decimal("0")) + Decimal("0.30"))
    factors_improved["cash_conversion"] = cc_orig.model_copy(update={
        "normalized_score": improved_score,
        "raw_value": improved_score,
    })

    improved_res = evaluator.evaluate(profile, factors_improved)
    assert improved_res.strategy_score >= base_res.strategy_score, "Score must not decrease when cash conversion improves"

    # Perturb cash_conversion downwards
    factors_worsened = dict(factors_base)
    worsened_score = max(Decimal("-1.0"), (cc_orig.normalized_score or Decimal("0")) - Decimal("0.30"))
    factors_worsened["cash_conversion"] = cc_orig.model_copy(update={
        "normalized_score": worsened_score,
        "raw_value": worsened_score,
    })

    worsened_res = evaluator.evaluate(profile, factors_worsened)
    assert worsened_res.strategy_score <= base_res.strategy_score, "Score must not increase when cash conversion worsens"


def test_metamorphic_feng_liu_operating_improvement_monotonicity():
    """For Feng Liu: when proxy is established, improving operating metrics must not decrease strategy score."""
    from src.investors.engine import StrategyEvaluator
    from src.factors.contracts import FactorResult, FactorType
    profile = PILOT_PROFILES["feng_liu"]
    evaluator = StrategyEvaluator()

    snapshot = load_frozen_snapshot(SNAPSHOT_000333)
    pit_snap = build_pit_constrained_snapshot(snapshot, datetime(2026, 5, 1, tzinfo=timezone.utc))
    engine = FactorEngine()
    factors_base = engine.evaluate(pit_snap.factor_context)

    # Inject established proxy
    factors_base["low_expectation_proxy"] = FactorResult(
        factor_id="low_expectation_proxy",
        version="v1",
        factor_type=FactorType.PROXY,
        normalized_score=Decimal("0.50"),
        raw_value=Decimal("0.50"),
        status=FactorStatus.AVAILABLE,
        coverage=Decimal("1.0"),
        as_of=pit_snap.as_of,
        window="test",
        limitations=("test",),
    )

    base_res = evaluator.evaluate(profile, factors_base)

    # Improve growth_acceleration
    factors_improved = dict(factors_base)
    ga = factors_base["growth_acceleration"]
    factors_improved["growth_acceleration"] = ga.model_copy(update={
        "normalized_score": Decimal("0.80"),
        "raw_value": Decimal("0.80"),
        "status": FactorStatus.AVAILABLE,
    })
    improved_res = evaluator.evaluate(profile, factors_improved)
    assert improved_res.strategy_score >= base_res.strategy_score


def test_metamorphic_fu_pengbo_growth_acceleration_monotonicity():
    """For Fu Pengbo: improving growth acceleration must not decrease strategy score."""
    from src.investors.engine import StrategyEvaluator
    profile = PILOT_PROFILES["fu_pengbo"]
    evaluator = StrategyEvaluator()

    snapshot = load_frozen_snapshot(SNAPSHOT_300750)
    pit_snap = build_pit_constrained_snapshot(snapshot, datetime(2026, 5, 1, tzinfo=timezone.utc))
    engine = FactorEngine()
    factors_base = engine.evaluate(pit_snap.factor_context)
    ga = factors_base["growth_acceleration"]

    # Low growth acceleration
    f_low = dict(factors_base)
    f_low["growth_acceleration"] = ga.model_copy(update={
        "normalized_score": Decimal("0.20"),
        "raw_value": Decimal("0.20"),
    })
    res_low = evaluator.evaluate(profile, f_low)

    # Medium growth acceleration
    f_mid = dict(factors_base)
    f_mid["growth_acceleration"] = ga.model_copy(update={
        "normalized_score": Decimal("0.50"),
        "raw_value": Decimal("0.50"),
    })
    res_mid = evaluator.evaluate(profile, f_mid)

    # High growth acceleration
    f_high = dict(factors_base)
    f_high["growth_acceleration"] = ga.model_copy(update={
        "normalized_score": Decimal("0.80"),
        "raw_value": Decimal("0.80"),
    })
    res_high = evaluator.evaluate(profile, f_high)

    assert res_high.strategy_score >= res_mid.strategy_score >= res_low.strategy_score, (
        f"Monotonicity violated: {res_high.strategy_score} >= {res_mid.strategy_score} >= {res_low.strategy_score}"
    )


# ==============================================================================
# 7. Data Missing Transition & Profile Missing Policy
# ==============================================================================


def test_data_missing_transition_conforms_to_confidence_caps():
    """T1: Key factor missing -> confidence capped; T2: Key factor available -> confidence improves."""
    from src.investors.engine import StrategyEvaluator
    profile = PILOT_PROFILES["zhang_kun"]
    evaluator = StrategyEvaluator()

    snapshot = load_frozen_snapshot(SNAPSHOT_600519)
    pit_snap = build_pit_constrained_snapshot(snapshot, datetime(2026, 5, 1, tzinfo=timezone.utc))
    factors = FactorEngine().evaluate(pit_snap.factor_context)

    # T1: Core factor profitability_quality is unavailable
    factors_t1 = dict(factors)
    orig_pq = factors["profitability_quality"]
    factors_t1["profitability_quality"] = orig_pq.model_copy(update={
        "status": FactorStatus.UNAVAILABLE,
        "normalized_score": None,
        "raw_value": None,
        "coverage": Decimal("0"),
    })

    res_t1 = evaluator.evaluate(profile, factors_t1)
    # Under Zhang Kun missing policy: core_missing_cap is 55
    assert res_t1.confidence <= 55.0
    assert any("核心因子不完整" in lim for lim in res_t1.limitations)

    # T2: Key factor becomes fully available
    res_t2 = evaluator.evaluate(profile, factors)
    assert res_t2.core_coverage > res_t1.core_coverage
    assert res_t2.confidence >= res_t1.confidence


# ==============================================================================
# 8. Profile Version Boundary & Independent Replay
# ==============================================================================


def test_zhang_kun_v1_and_v2_replayable_independently():
    """Zhang Kun v1 and v2 run on identical snapshot: v2 outputs valuation risk rule, v1 does not."""
    snapshot = load_frozen_snapshot(SNAPSHOT_600519)
    runner = TemporalShadowRunner()
    as_of = datetime(2026, 5, 1, tzinfo=timezone.utc)

    profile_v1 = get_pilot_profile("zhang_kun", "v1")
    profile_v2 = get_pilot_profile("zhang_kun", "v2")

    assert profile_v1.version == "v1"
    assert profile_v2.version == "v2"

    comp_v1 = runner.run("600519", profile_v1, as_of, snapshot)
    comp_v2 = runner.run("600519", profile_v2, as_of, snapshot)

    assert comp_v1.new.profile_version == "v1"
    assert comp_v2.new.profile_version == "v2"

    # Both produce identical strategy scores since weights/formulas are identical
    assert comp_v1.new.strategy_score == comp_v2.new.strategy_score
    assert comp_v1.new.signal == comp_v2.new.signal
    assert comp_v1.new.confidence == comp_v2.new.confidence

    # Risk message verification
    assert "valuation_level" not in profile_v1.risk_rules
    assert "valuation_level" in profile_v2.risk_rules
    assert profile_v2.risk_rules["valuation_level"] == "核心经营质量良好，但估值偏高压缩预期回报"
