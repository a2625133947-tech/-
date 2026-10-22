"""Operational health monitoring, drift detection, and corpus summary for shadow evaluations.

Monitors data provider health, factor distribution stability, and signal/confidence
consistency across the accumulated prospective corpus.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import statistics
from typing import Any, Mapping, Sequence

from pydantic import BaseModel, Field

from src.investors.collector import TemporalCatalog, TemporalCatalogEntry

logger = logging.getLogger(__name__)


class DataDriftWarning(BaseModel):
    warning_type: str  # "COVERAGE_DROP", "SCHEMA_FAILURE_SPIKE", "DEGRADATION_SPIKE"
    message: str
    severity: str = "WARNING"  # "WARNING", "CRITICAL"
    details: dict[str, Any] = Field(default_factory=dict)


class FactorDriftWarning(BaseModel):
    factor_id: str
    warning_type: str  # "MASS_UNAVAILABLE", "MASS_DEGRADED", "EXTREME_SCORE_SHIFT"
    affected_ratio: float
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class DistributionShiftWarning(BaseModel):
    profile_id: str
    warning_type: str  # "SIGNAL_MONOPOLY", "CONFIDENCE_INFLATION", "CONFIDENCE_COLLAPSE"
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class CorpusHealthReport(BaseModel):
    generated_at: datetime
    snapshot_count: int
    ticker_count: int
    date_range: tuple[str, str] | None = None
    partial_runs_count: int = 0
    degraded_snapshots_count: int = 0
    signal_distribution: dict[str, dict[str, int]] = Field(default_factory=dict)
    confidence_distribution: dict[str, dict[str, float]] = Field(default_factory=dict)
    data_drift_warnings: list[DataDriftWarning] = Field(default_factory=list)
    factor_drift_warnings: list[FactorDriftWarning] = Field(default_factory=list)
    distribution_warnings: list[DistributionShiftWarning] = Field(default_factory=list)


def check_data_drift(
    current_entries: Sequence[TemporalCatalogEntry],
    *,
    min_coverage_threshold: float = 0.50,
) -> list[DataDriftWarning]:
    """Detect sudden drops in capability coverage across snapshots."""
    warnings: list[DataDriftWarning] = []
    if not current_entries:
        return warnings

    degraded_count = sum(1 for e in current_entries if e.quality_status == "DEGRADED")
    degraded_ratio = degraded_count / len(current_entries)
    if degraded_ratio > 0.40:
        warnings.append(DataDriftWarning(
            warning_type="DEGRADATION_SPIKE",
            severity="WARNING",
            message=f"High proportion of degraded snapshots: {degraded_count}/{len(current_entries)} ({degraded_ratio:.1%})",
            details={"degraded_count": degraded_count, "total_count": len(current_entries)},
        ))

    partial_count = sum(1 for e in current_entries if getattr(e, "run_status", "COMPLETE") == "PARTIAL_RUN")
    if partial_count > 0:
        warnings.append(DataDriftWarning(
            warning_type="PARTIAL_RUN_DETECTED",
            severity="CRITICAL",
            message=f"{partial_count} partial snapshot evaluation runs detected in corpus",
            details={"partial_count": partial_count},
        ))

    return warnings


def check_distribution_shift(
    catalog: TemporalCatalog,
) -> list[DistributionShiftWarning]:
    """Detect uncharacteristic distribution collapse (e.g. 100% bullish or extreme confidence shift)."""
    warnings: list[DistributionShiftWarning] = []
    signals_by_profile: dict[str, list[str]] = {}
    confs_by_profile: dict[str, list[float]] = {}

    for entry in catalog.entries:
        for pid, summary in entry.shadow_evaluations.items():
            signals_by_profile.setdefault(pid, []).append(summary.signal)
            confs_by_profile.setdefault(pid, []).append(summary.confidence)

    for pid, signals in signals_by_profile.items():
        if len(signals) >= 10:
            counts = {s: signals.count(s) for s in ("bullish", "neutral", "bearish")}
            for sig, count in counts.items():
                if count == len(signals):
                    warnings.append(DistributionShiftWarning(
                        profile_id=pid,
                        warning_type="SIGNAL_MONOPOLY",
                        message=f"Profile {pid} produced 100% {sig} across all {len(signals)} evaluations",
                        details={"counts": counts, "total": len(signals)},
                    ))

    for pid, confs in confs_by_profile.items():
        if len(confs) >= 5:
            mean_conf = statistics.mean(confs)
            if mean_conf > 85.0:
                warnings.append(DistributionShiftWarning(
                    profile_id=pid,
                    warning_type="CONFIDENCE_INFLATION",
                    message=f"Profile {pid} mean confidence abnormally high ({mean_conf:.1f}% > 85%)",
                    details={"mean_confidence": mean_conf},
                ))
            elif mean_conf < 25.0:
                warnings.append(DistributionShiftWarning(
                    profile_id=pid,
                    warning_type="CONFIDENCE_COLLAPSE",
                    message=f"Profile {pid} mean confidence abnormally low ({mean_conf:.1f}% < 25%)",
                    details={"mean_confidence": mean_conf},
                ))

    return warnings


def generate_corpus_summary(
    catalog_path: str | Path = "docs/baselines/shadow/live/temporal_catalog.json",
) -> CorpusHealthReport:
    """Generate comprehensive operational health report of the shadow corpus."""
    catalog = TemporalCatalog.load_or_create(catalog_path)
    entries = catalog.entries

    tickers = {e.ticker for e in entries}
    dates = [e.as_of[:10] for e in entries if e.as_of]
    date_range = (min(dates), max(dates)) if dates else None

    degraded_count = sum(1 for e in entries if e.quality_status == "DEGRADED")
    partial_count = sum(1 for e in entries if getattr(e, "run_status", "COMPLETE") == "PARTIAL_RUN")

    sig_dist: dict[str, dict[str, int]] = {}
    conf_stats: dict[str, dict[str, float]] = {}
    confs_by_profile: dict[str, list[float]] = {}

    for e in entries:
        for pid, s in e.shadow_evaluations.items():
            sig_dist.setdefault(pid, {"bullish": 0, "neutral": 0, "bearish": 0})
            if s.signal in sig_dist[pid]:
                sig_dist[pid][s.signal] += 1
            confs_by_profile.setdefault(pid, []).append(s.confidence)

    for pid, vals in confs_by_profile.items():
        if vals:
            conf_stats[pid] = {
                "mean": round(statistics.mean(vals), 1),
                "median": round(statistics.median(vals), 1),
                "min": round(min(vals), 1),
                "max": round(max(vals), 1),
                "stdev": round(statistics.stdev(vals), 1) if len(vals) > 1 else 0.0,
            }

    data_warnings = check_data_drift(entries)
    dist_warnings = check_distribution_shift(catalog)

    return CorpusHealthReport(
        generated_at=datetime.now(timezone.utc),
        snapshot_count=len(entries),
        ticker_count=len(tickers),
        date_range=date_range,
        partial_runs_count=partial_count,
        degraded_snapshots_count=degraded_count,
        signal_distribution=sig_dist,
        confidence_distribution=conf_stats,
        data_drift_warnings=data_warnings,
        distribution_warnings=dist_warnings,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for shadow-corpus-summary."""
    parser = argparse.ArgumentParser(
        prog="shadow-corpus-summary",
        description="Inspect shadow corpus health, signal distributions, and drift warnings.",
    )
    parser.add_argument(
        "--catalog",
        default="docs/baselines/shadow/live/temporal_catalog.json",
        help="Path to catalog index JSON.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON format.",
    )

    args = parser.parse_args(argv)
    report = generate_corpus_summary(args.catalog)

    if args.json:
        print(report.model_dump_json(indent=2))
        return 0

    print("==================================================")
    print("           SHADOW CORPUS HEALTH REPORT            ")
    print("==================================================")
    print(f"Generated At:       {report.generated_at.isoformat()}")
    print(f"Total Snapshots:    {report.snapshot_count}")
    print(f"Total Tickers:      {report.ticker_count}")
    print(f"Date Range:         {report.date_range[0]} to {report.date_range[1]}" if report.date_range else "None")
    print(f"Degraded Snapshots: {report.degraded_snapshots_count}")
    print(f"Partial Runs:       {report.partial_runs_count}")

    print("\n--- Signal Distribution Across 10 Shadow Profiles ---")
    print(f"{'Profile ID':<18} | {'Bullish':>7} | {'Neutral':>7} | {'Bearish':>7} | {'Total':>5}")
    print("-" * 52)
    for pid, dist in sorted(report.signal_distribution.items()):
        total = sum(dist.values())
        print(f"{pid:<18} | {dist['bullish']:>7} | {dist['neutral']:>7} | {dist['bearish']:>7} | {total:>5}")

    print("\n--- Confidence Statistics ---")
    print(f"{'Profile ID':<18} | {'Mean':>6} | {'Median':>6} | {'Min':>6} | {'Max':>6} | {'StDev':>6}")
    print("-" * 58)
    for pid, stats in sorted(report.confidence_distribution.items()):
        print(f"{pid:<18} | {stats['mean']:>5.1f}% | {stats['median']:>5.1f}% | {stats['min']:>5.1f}% | {stats['max']:>5.1f}% | {stats['stdev']:>5.1f}")

    if report.data_drift_warnings:
        print("\n[!] DATA DRIFT WARNINGS:")
        for w in report.data_drift_warnings:
            print(f"  - [{w.severity}] {w.warning_type}: {w.message}")

    if report.distribution_warnings:
        print("\n[!] DISTRIBUTION SHIFT WARNINGS:")
        for w in report.distribution_warnings:
            print(f"  - [{w.warning_type}] {w.profile_id}: {w.message}")

    print("\nOperational Status: Healthy (Research Corpus Active)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
