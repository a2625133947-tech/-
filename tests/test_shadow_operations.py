"""Deterministic tests for Phase B5.5 Shadow Operations and Confidence Semantics Audit."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import pytest

from src.factors.contracts import FactorResult, FactorStatus, FactorType
from src.factors.engine import FactorEngine, default_registry
from src.investors.contracts import ConfidenceComponents
from src.investors.engine import StrategyEvaluator
from src.investors.profiles import (
    EXPANDED_PROFILES, PILOT_PROFILES, SHADOW_PROFILES, get_profile,
)
from src.investors.shadow import (
    FrozenDataSnapshot, MatchedShadowRunner, load_frozen_snapshot,
)
from src.investors.collector import (
    CollectorRunReport, SnapshotCollector, TemporalCatalog, TemporalCatalogEntry,
)
from src.investors.longitudinal import (
    LongitudinalShadowRecord, OutcomeRecord, build_longitudinal_record,
)
from src.investors.monitoring import (
    CorpusHealthReport, check_data_drift, check_distribution_shift,
    generate_corpus_summary,
)

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_600519 = ROOT / "docs/baselines/shadow/live/snapshots/600519_20260927T141212Z_d37d7fdaef87.snapshot.json"
CATALOG_PATH = ROOT / "docs/baselines/shadow/live/temporal_catalog.json"


# ==============================================================================
# 1. Confidence Semantics and Breakdown Reconciliation Tests
# ==============================================================================


def test_confidence_components_populated_and_reconciled():
    """Verify that confidence_components exactly reconciles the final confidence."""
    snapshot = load_frozen_snapshot(SNAPSHOT_600519)
    runner = MatchedShadowRunner()
    profile = get_profile("duan_yongping")

    matched = runner.run("600519", profile, snapshot.as_of, snapshot)
    res = matched.new
    comp = res.confidence_components

    assert comp is not None
    assert comp.maximum_possible == 90.0
    assert 0.0 <= comp.core_coverage <= 1.0
    assert 0.0 <= comp.evidence_quality <= 1.0

    # Base confidence formula: maximum * coverage_score * quality
    expected_base = round(comp.maximum_possible * comp.coverage_score * comp.evidence_quality, 1)
    assert abs(comp.unconstrained_confidence - expected_base) < 0.2

    # Final confidence must equal the active cap if a cap bound the calculation
    if comp.active_cap_value is not None:
        assert comp.final_confidence <= comp.active_cap_value
    assert comp.final_confidence == res.confidence
    assert len(comp.audit_trail) >= 2


def test_strategy_evidence_cap_prevents_inflated_confidence():
    """Profiles with multiple known missing dimensions must have confidence bounded by strategy_evidence_cap."""
    evaluator = StrategyEvaluator()
    profile = get_profile("xie_zhiyu")
    as_of = datetime(2026, 9, 27, tzinfo=timezone.utc)

    # Construct synthetic complete factor set (100% available with validated quality)
    registry = default_registry()
    factors = {}
    for factor in registry.list():
        factors[factor.factor_id] = FactorResult(
            factor_id=factor.factor_id,
            version=factor.version,
            factor_type=FactorType.DIRECT,
            normalized_score=Decimal("0.50"),
            raw_value=Decimal("0.50"),
            status=FactorStatus.AVAILABLE,
            coverage=Decimal("1.0"),
            as_of=as_of,
            window=factor.time_horizon,
        )

    res = evaluator.evaluate(profile, factors)
    comp = res.confidence_components

    assert comp is not None
    # Xie Zhiyu has 4 known missing dimensions (PEG, relative valuation, etc.)
    assert len(profile.known_missing_dimensions) == 4
    assert comp.strategy_evidence_cap is not None
    # 40 + 50 * (8/12) = 73.3
    assert comp.strategy_evidence_cap <= 75.0
    # Even with 100% factor data, confidence cannot exceed 75.0%
    assert res.confidence <= comp.strategy_evidence_cap


def test_proxy_penalty_without_double_penalty():
    """Feng Liu: proxy_cap and strategy_evidence_cap must apply as ceilings (min), not multiplicative compounding."""
    evaluator = StrategyEvaluator()
    profile = get_profile("feng_liu")
    as_of = datetime(2026, 9, 27, tzinfo=timezone.utc)

    registry = default_registry()
    factors = {}
    for factor in registry.list():
        factors[factor.factor_id] = FactorResult(
            factor_id=factor.factor_id,
            version=factor.version,
            factor_type=FactorType.DIRECT,
            normalized_score=Decimal("0.50"),
            raw_value=Decimal("0.50"),
            status=FactorStatus.AVAILABLE,
            coverage=Decimal("1.0"),
            as_of=as_of,
            window=factor.time_horizon,
        )

    res = evaluator.evaluate(profile, factors)
    comp = res.confidence_components

    assert comp.proxy_cap == 60.0
    assert comp.strategy_evidence_cap is not None
    # The active cap should be the stricter proxy_cap (60.0) without double discounting
    assert comp.active_cap_name == "proxy_cap"
    assert comp.final_confidence == 60.0


# ==============================================================================
# 2. Collector Health and Run Report
# ==============================================================================


def test_collector_run_report_structure(tmp_path):
    """Verify collect_many returns a complete, structured CollectorRunReport."""
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = tmp_path / "catalog.json"

    snapshot = load_frozen_snapshot(SNAPSHOT_600519)

    class FakeService:
        pass

    collector = SnapshotCollector(
        service=FakeService(),
        snapshot_dir=snapshot_dir,
        catalog_path=catalog_path,
        run_shadow=False,
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(FrozenDataSnapshot, "capture_current", lambda ticker, service=None: snapshot)
        report: CollectorRunReport = collector.collect_many(["600519"])

    assert report.run_id.startswith("run_")
    assert report.duration_seconds >= 0.0
    assert report.requested_tickers == ["600519"]
    assert report.snapshot_created == 1
    assert report.snapshot_failed == 0
    assert report.successful == ["600519"]


# ==============================================================================
# 3. Partial-Run Detection and Resumability
# ==============================================================================


def test_partial_run_detection_and_resume(tmp_path):
    """Verify that incomplete shadow runs are detected as PARTIAL_RUN and can be resumed."""
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = tmp_path / "catalog.json"
    results_dir = tmp_path / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    snapshot = load_frozen_snapshot(SNAPSHOT_600519)
    from src.investors.shadow import save_frozen_snapshot
    saved_snapshot_path = save_frozen_snapshot(snapshot, snapshot_dir)

    # Create an artificially incomplete catalog entry (only 3 of 10 profiles completed)
    from src.investors.collector import ShadowEvaluationSummary
    dummy_evals = {
        pid: ShadowEvaluationSummary(
            profile_id=pid,
            profile_version="v1",
            strategy_score=0.5,
            signal="bullish",
            confidence=50.0,
            implemented_factor_coverage=1.0,
            strategy_evidence_coverage=0.8,
            quality_status="VALIDATED",
        )
        for pid in ("zhang_kun", "feng_liu", "fu_pengbo")
    }

    catalog = TemporalCatalog()
    entry = TemporalCatalogEntry(
        ticker="600519",
        snapshot_id=snapshot.snapshot_id,
        captured_at=snapshot.as_of.isoformat(),
        as_of=snapshot.as_of.isoformat(),
        market_data_date="2026-09-24",
        profile_versions={},
        factor_versions={},
        capability_coverage={},
        content_hash="dummy_hash",
        retention_tags=["TEST"],
        quality_status="VALIDATED",
        snapshot_path=saved_snapshot_path.name,
        expected_profiles=list(SHADOW_PROFILES.keys()),
        completed_profiles=["zhang_kun", "feng_liu", "fu_pengbo"],
        missing_profiles=[p for p in SHADOW_PROFILES if p not in ("zhang_kun", "feng_liu", "fu_pengbo")],
        evaluation_complete=False,
        run_status="PARTIAL_RUN",
        shadow_evaluations=dummy_evals,
    )
    catalog.add_entry(entry)
    catalog.save(catalog_path)

    # Monitoring should detect the partial run
    warnings = check_data_drift(catalog.entries)
    assert any(w.warning_type == "PARTIAL_RUN_DETECTED" for w in warnings)

    # Resume incomplete evaluations
    collector = SnapshotCollector(
        snapshot_dir=snapshot_dir,
        results_dir=results_dir,
        catalog_path=catalog_path,
    )
    resumed_count = collector.resume_incomplete_evaluations(catalog=catalog)
    assert resumed_count == 7

    # Reload catalog and verify entry is now complete
    reloaded = TemporalCatalog.load_or_create(catalog_path)
    assert reloaded.entries[0].evaluation_complete is True
    assert reloaded.entries[0].run_status == "COMPLETE"
    assert len(reloaded.entries[0].completed_profiles) == 10
    assert len(reloaded.entries[0].missing_profiles) == 0


# ==============================================================================
# 4. Longitudinal Dataset and Outcome Separation
# ==============================================================================


def test_longitudinal_shadow_record_and_outcome_separation():
    """Verify LongitudinalShadowRecord captures model state and OutcomeRecord remains decoupled."""
    snapshot = load_frozen_snapshot(SNAPSHOT_600519)
    runner = MatchedShadowRunner()
    matched = runner.run("600519", get_profile("duan_yongping"), snapshot.as_of, snapshot)

    record = build_longitudinal_record(snapshot, matched)

    assert isinstance(record, LongitudinalShadowRecord)
    assert record.ticker == "600519"
    assert record.profile_id == "duan_yongping"
    assert record.profile_version == "v1"
    assert record.signal == "bullish"
    assert record.confidence_components is not None
    assert len(record.known_missing_dimensions) >= 2

    # Forward returns belong in a strictly separate OutcomeRecord
    outcome = OutcomeRecord(
        snapshot_id=snapshot.snapshot_id,
        ticker="600519",
        as_of=snapshot.as_of,
        measured_at=snapshot.as_of,
        forward_window="1M",
        forward_return=Decimal("0.045"),
        benchmark_return=Decimal("0.021"),
        excess_return=Decimal("0.024"),
    )

    assert outcome.snapshot_id == record.snapshot_id
    assert outcome.forward_return == Decimal("0.045")
    # Verify StrategyEvaluationResult has no outcome attributes
    assert not hasattr(matched.new, "forward_return")


# ==============================================================================
# 5. Drift Detection & Monitoring Tests
# ==============================================================================


def test_data_drift_warning_on_degradation_spike():
    """Verify check_data_drift generates warning when degraded snapshots spike above 40%."""
    entries = [
        TemporalCatalogEntry(
            ticker=f"60000{i}",
            snapshot_id=f"id_{i}",
            captured_at="2026-09-27T00:00:00Z",
            as_of="2026-09-27T00:00:00Z",
            market_data_date="2026-09-24",
            profile_versions={},
            factor_versions={},
            capability_coverage={},
            content_hash=f"hash_{i}",
            retention_tags=[],
            quality_status="DEGRADED" if i < 6 else "VALIDATED",
            snapshot_path="test.json",
        )
        for i in range(10)
    ]

    warnings = check_data_drift(entries)
    assert any(w.warning_type == "DEGRADATION_SPIKE" for w in warnings)


def test_distribution_shift_warning_on_confidence_inflation():
    """Verify check_distribution_shift detects uncharacteristic confidence inflation."""
    from src.investors.collector import ShadowEvaluationSummary
    catalog = TemporalCatalog()

    for i in range(10):
        entry = TemporalCatalogEntry(
            ticker=f"60000{i}",
            snapshot_id=f"id_{i}",
            captured_at="2026-09-27T00:00:00Z",
            as_of="2026-09-27T00:00:00Z",
            market_data_date="2026-09-24",
            profile_versions={},
            factor_versions={},
            capability_coverage={},
            content_hash=f"hash_{i}",
            retention_tags=[],
            quality_status="VALIDATED",
            snapshot_path="test.json",
            shadow_evaluations={
                "test_prof": ShadowEvaluationSummary(
                    profile_id="test_prof",
                    profile_version="v1",
                    strategy_score=0.5,
                    signal="bullish",
                    confidence=95.0,  # Abnormal inflation
                    implemented_factor_coverage=1.0,
                    strategy_evidence_coverage=1.0,
                    quality_status="VALIDATED",
                )
            },
        )
        catalog.add_entry(entry)

    warnings = check_distribution_shift(catalog)
    assert any(w.warning_type == "CONFIDENCE_INFLATION" for w in warnings)


def test_corpus_summary_report_generation():
    """Verify generate_corpus_summary reads live catalog and produces full health report."""
    report = generate_corpus_summary(CATALOG_PATH)
    assert isinstance(report, CorpusHealthReport)
    assert report.snapshot_count == 18
    assert report.ticker_count == 18
    assert len(report.signal_distribution) == 10
    assert len(report.confidence_distribution) == 10
    assert report.partial_runs_count == 0
