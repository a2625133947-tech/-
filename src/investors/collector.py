"""Snapshot collector with content-based deduplication and retention policy.

This tool is strictly for accumulating prospective point-in-time snapshots.
It does NOT enter the investment graph or modify trading decisions.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
import logging
from pathlib import Path
import re
from typing import Any, Sequence

from pydantic import BaseModel, Field

from src.data.capabilities import Capability
from src.data.domain import DataStatus, Quality
from src.data.pipeline import DataService
from src.factors.engine import default_registry
from src.investors.profiles import PROXY_ID, SHADOW_PROFILES
from src.investors.shadow import (
    FrozenDataSnapshot, MatchedShadowResult, MatchedShadowRunner,
    save_frozen_snapshot, save_shadow_result,
)

logger = logging.getLogger(__name__)


def compute_content_hash(snapshot: FrozenDataSnapshot) -> str:
    """Compute a deterministic hash of the normalized market and financial payload.

    Excludes capture execution timestamps (as_of, retrieved_at) to detect whether
    the underlying corporate and market observations actually changed.
    """
    payload: dict[str, Any] = {"ticker": snapshot.ticker}

    # Financial statements payload
    stmt_data = {}
    for cap_name, env in sorted(snapshot.financial_statements.items()):
        if env.status is DataStatus.PRESENT and env.observation:
            rows = []
            for stmt in env.observation.value:
                fields = {f.name: str(f.value) for f in stmt.fields if f.value is not None}
                rows.append({"period_end": stmt.period_end.isoformat(), "period": stmt.period, "fields": fields})
            stmt_data[cap_name] = rows
    payload["statements"] = stmt_data

    # Price history payload
    if snapshot.price_history.status is DataStatus.PRESENT and snapshot.price_history.observation:
        bars = [
            {
                "date": b.trading_date.isoformat(),
                "open": str(b.open),
                "high": str(b.high),
                "low": str(b.low),
                "close": str(b.close),
                "volume": str(b.volume) if b.volume is not None else None,
                "factor": str(b.adjustment_factor) if b.adjustment_factor is not None else None,
            }
            for b in snapshot.price_history.observation.value
        ]
        payload["prices"] = bars
    else:
        payload["prices"] = []

    # Valuation history payload
    if snapshot.valuation_history.status is DataStatus.PRESENT and snapshot.valuation_history.observation:
        vals = [
            {
                "date": v.observed_date.isoformat(),
                "pe": str(v.pe) if v.pe is not None else None,
                "pb": str(v.pb) if v.pb is not None else None,
                "ps": str(v.ps) if v.ps is not None else None,
            }
            for v in snapshot.valuation_history.observation.value
        ]
        payload["valuations"] = vals
    else:
        payload["valuations"] = []

    # Share capital payload
    if snapshot.share_capital_history.status is DataStatus.PRESENT and snapshot.share_capital_history.observation:
        shares = [
            {"date": s.effective_date.isoformat(), "shares": str(s.total_shares)}
            for s in snapshot.share_capital_history.observation.value
        ]
        payload["shares"] = shares
    else:
        payload["shares"] = []

    # Dividends payload
    if snapshot.dividends.status is DataStatus.PRESENT and snapshot.dividends.observation:
        divs = [
            {"ex_date": d.ex_date.isoformat(), "cash": str(d.cash_per_share)}
            for d in snapshot.dividends.observation.value
        ]
        payload["dividends"] = divs
    else:
        payload["dividends"] = []

    # Industry payload
    if snapshot.industry.status is DataStatus.PRESENT and snapshot.industry.observation:
        payload["industry"] = snapshot.industry.observation.value.industry
    else:
        payload["industry"] = None

    payload["capability_statuses"] = snapshot.capability_statuses

    dumped = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return sha256(dumped.encode("utf-8")).hexdigest()


class SnapshotRetentionPolicy:
    """Retention classification preserving milestones and deduplicating unchanged observations."""

    @staticmethod
    def classify_milestones(
        current: FrozenDataSnapshot,
        previous: FrozenDataSnapshot | None,
    ) -> list[str]:
        tags: list[str] = []
        if previous is None:
            return ["INITIAL_BASELINE"]

        # Check for new financial statements
        curr_periods = {
            stmt.period_end
            for env in current.financial_statements.values()
            if env.status is DataStatus.PRESENT and env.observation
            for stmt in env.observation.value
        }
        prev_periods = {
            stmt.period_end
            for env in previous.financial_statements.values()
            if env.status is DataStatus.PRESENT and env.observation
            for stmt in env.observation.value
        }
        if curr_periods - prev_periods:
            tags.append("EARNINGS_RELEASE")

        # Check for corporate action events (share capital or dividend)
        curr_shares = (
            len(current.share_capital_history.observation.value)
            if current.share_capital_history.observation
            else 0
        )
        prev_shares = (
            len(previous.share_capital_history.observation.value)
            if previous.share_capital_history.observation
            else 0
        )
        if curr_shares != prev_shares:
            tags.append("CORPORATE_ACTION_SHARE_CHANGE")

        curr_divs = (
            len(current.dividends.observation.value)
            if current.dividends.observation
            else 0
        )
        prev_divs = (
            len(previous.dividends.observation.value)
            if previous.dividends.observation
            else 0
        )
        if curr_divs != prev_divs:
            tags.append("CORPORATE_ACTION_DIVIDEND")

        # Check for significant price movement (> 5% single-day close move)
        curr_bars = current.price_history.observation.value if current.price_history.observation else []
        prev_bars = previous.price_history.observation.value if previous.price_history.observation else []
        if curr_bars and prev_bars and curr_bars[-1].trading_date != prev_bars[-1].trading_date:
            last_close = curr_bars[-1].close
            prev_close = prev_bars[-1].close
            if prev_close > 0:
                change = abs((last_close - prev_close) / prev_close)
                if change >= Decimal("0.05"):
                    tags.append("SIGNIFICANT_PRICE_MOVE")

        # Check for schema or capability state changes
        if current.capability_statuses != previous.capability_statuses:
            tags.append("CAPABILITY_STATUS_CHANGE")

        return tags if tags else ["REGULAR_CAPTURE"]

    def should_retain(
        self,
        current: FrozenDataSnapshot,
        previous: FrozenDataSnapshot | None,
        is_duplicate_content: bool,
    ) -> tuple[bool, list[str]]:
        tags = self.classify_milestones(current, previous)
        if not is_duplicate_content:
            return True, tags

        # Content is identical to previous
        # If milestone event occurred (e.g. corporate action or schema change), retain
        milestones = {"EARNINGS_RELEASE", "CORPORATE_ACTION_SHARE_CHANGE", "CORPORATE_ACTION_DIVIDEND", "SIGNIFICANT_PRICE_MOVE"}
        if any(tag in milestones for tag in tags):
            return True, tags

        return False, ["DUPLICATE_CONTENT"]


class CaptureEvent(BaseModel):
    ticker: str
    captured_at: datetime
    as_of: datetime
    snapshot_id: str
    content_hash: str
    is_duplicate: bool
    retained: bool
    retention_tags: list[str]
    is_degraded: bool
    degraded_reasons: list[str] = Field(default_factory=list)


class ShadowEvaluationSummary(BaseModel):
    profile_id: str
    profile_version: str
    strategy_score: float | None = None
    signal: str
    confidence: float
    implemented_factor_coverage: float
    strategy_evidence_coverage: float
    known_missing_dimensions: list[str] = Field(default_factory=list)
    proxy_dependence: bool = False
    quality_status: str
    result_path: str | None = None
    confidence_components: dict[str, Any] | None = None


class TemporalCatalogEntry(BaseModel):
    ticker: str
    snapshot_id: str
    captured_at: str
    as_of: str
    market_data_date: str | None
    profile_versions: dict[str, str]
    factor_versions: dict[str, str]
    capability_coverage: dict[str, str]
    content_hash: str
    retention_tags: list[str]
    quality_status: str
    snapshot_path: str
    expected_profiles: list[str] = Field(default_factory=list)
    completed_profiles: list[str] = Field(default_factory=list)
    missing_profiles: list[str] = Field(default_factory=list)
    evaluation_complete: bool = True
    run_status: str = "COMPLETE"  # "COMPLETE", "PARTIAL_RUN", "DEGRADED"
    shadow_evaluations: dict[str, ShadowEvaluationSummary] = Field(default_factory=dict)


class TemporalCatalog(BaseModel):
    schema_version: int = 1
    description: str = "Point-in-time prospective snapshot replay catalog with content deduplication."
    entries: list[TemporalCatalogEntry] = Field(default_factory=list)

    @classmethod
    def load_or_create(cls, path: str | Path) -> "TemporalCatalog":
        path = Path(path)
        if path.exists():
            return cls.model_validate_json(path.read_text(encoding="utf-8"))
        return cls()

    def has_content_hash(self, ticker: str, content_hash: str) -> bool:
        return any(e.ticker == ticker and e.content_hash == content_hash for e in self.entries)

    def find_latest_entry(self, ticker: str) -> TemporalCatalogEntry | None:
        matches = [e for e in self.entries if e.ticker == ticker]
        return matches[-1] if matches else None

    def add_entry(self, entry: TemporalCatalogEntry) -> None:
        self.entries.append(entry)

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        temp_path.replace(path)
        return path


class CollectionResult(BaseModel):
    ticker: str
    status: str  # "SUCCESS", "DUPLICATE", "DEGRADED", "FAILED"
    snapshot_id: str | None = None
    content_hash: str | None = None
    retained: bool = False
    tags: list[str] = Field(default_factory=list)
    quality: str | None = None
    coverage_score: float = 0.0
    error: str | None = None
    snapshot_path: str | None = None


class CollectorRunReport(BaseModel):
    run_id: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float = 0.0
    requested_tickers: list[str] = Field(default_factory=list)
    successful: list[str] = Field(default_factory=list)
    snapshot_created: int = 0
    snapshot_deduplicated: int = 0
    snapshot_degraded: int = 0
    snapshot_failed: int = 0
    shadow_evaluations_success: int = 0
    shadow_evaluations_failed: int = 0
    failed: dict[str, str] = Field(default_factory=dict)
    degraded: list[str] = Field(default_factory=list)
    deduplicated: list[str] = Field(default_factory=list)
    provider_failures: dict[str, str] = Field(default_factory=dict)
    capability_degradations: dict[str, list[str]] = Field(default_factory=dict)
    coverage_summary: dict[str, float] = Field(default_factory=dict)
    events: list[CaptureEvent] = Field(default_factory=list)


BatchCollectionResult = CollectorRunReport


class SnapshotCollector:
    """Collects, validates, deduplicates, and retains point-in-time snapshots."""

    def __init__(
        self,
        *,
        service: DataService | None = None,
        snapshot_dir: str | Path = "docs/baselines/shadow/live/snapshots",
        results_dir: str | Path = "docs/baselines/shadow/live/results",
        catalog_path: str | Path = "docs/baselines/shadow/live/temporal_catalog.json",
        retention_policy: SnapshotRetentionPolicy | None = None,
        run_shadow: bool = True,
    ):
        self.service = service or DataService()
        self.snapshot_dir = Path(snapshot_dir)
        self.results_dir = Path(results_dir)
        self.catalog_path = Path(catalog_path)
        self.retention_policy = retention_policy or SnapshotRetentionPolicy()
        self.registry = default_registry()
        self.run_shadow = run_shadow

    def run_shadow_evaluations(
        self,
        snapshot: FrozenDataSnapshot,
        *,
        save_results: bool = True,
    ) -> dict[str, MatchedShadowResult]:
        """Run all 10 shadow-enabled investor evaluations over frozen snapshot."""
        runner = MatchedShadowRunner()
        results = {}
        for profile_id, profile in SHADOW_PROFILES.items():
            matched = runner.run(snapshot.ticker, profile, snapshot.as_of, snapshot)
            results[profile_id] = matched
            if save_results and self.results_dir:
                save_shadow_result(matched, self.results_dir)
        return results

    def collect_ticker(
        self,
        ticker: str,
        *,
        capture_mode: str = "current",
        catalog: TemporalCatalog | None = None,
    ) -> tuple[CollectionResult, CaptureEvent | None]:
        if catalog is None:
            catalog = TemporalCatalog.load_or_create(self.catalog_path)

        try:
            snapshot = FrozenDataSnapshot.capture_current(ticker, service=self.service)
        except Exception as exc:
            logger.warning("Failed to capture snapshot for %s: %s", ticker, exc)
            return (
                CollectionResult(ticker=ticker, status="FAILED", error=str(exc)),
                None,
            )

        content_hash = compute_content_hash(snapshot)
        is_dup = catalog.has_content_hash(ticker, content_hash)

        # Check degraded status
        degraded_reasons = []
        is_degraded = False
        if snapshot.price_history.observation and snapshot.price_history.observation.quality is Quality.DEGRADED:
            is_degraded = True
            degraded_reasons.append(snapshot.price_history.reason or "price quality degraded")

        # Calculate coverage
        present_count = sum(1 for s in snapshot.capability_statuses.values() if s is DataStatus.PRESENT)
        coverage_score = round(present_count / max(1, len(snapshot.capability_statuses)), 4)

        # Retention decision
        latest_entry = catalog.find_latest_entry(ticker)
        prev_snapshot = None
        if latest_entry:
            prev_file = self.snapshot_dir / Path(latest_entry.snapshot_path).name
            if prev_file.exists():
                try:
                    prev_snapshot = FrozenDataSnapshot.model_validate_json(prev_file.read_text(encoding="utf-8"))
                except Exception:
                    pass

        retained, tags = self.retention_policy.should_retain(snapshot, prev_snapshot, is_dup)

        saved_path = None
        if retained and capture_mode != "dry_run":
            saved_path = save_frozen_snapshot(snapshot, self.snapshot_dir)

            shadow_summaries = {}
            if self.run_shadow:
                shadow_runs = self.run_shadow_evaluations(snapshot, save_results=True)
                for pid, matched in shadow_runs.items():
                    res = matched.new
                    shadow_summaries[pid] = ShadowEvaluationSummary(
                        profile_id=pid,
                        profile_version=res.profile_version,
                        strategy_score=float(res.strategy_score) if res.strategy_score is not None else None,
                        signal=res.signal,
                        confidence=res.confidence,
                        implemented_factor_coverage=float(res.implemented_factor_coverage),
                        strategy_evidence_coverage=float(res.strategy_evidence_coverage),
                        known_missing_dimensions=list(res.known_missing_dimensions),
                        proxy_dependence=any(item.factor_type.value == "proxy" for item in res.used_factors),
                        quality_status="DEGRADED" if is_degraded else "VALIDATED",
                        confidence_components=res.confidence_components.model_dump(mode="json") if res.confidence_components else None,
                    )

            # Record in catalog
            market_date = None
            if snapshot.price_history.observation and snapshot.price_history.observation.value:
                market_date = snapshot.price_history.observation.value[-1].trading_date.isoformat()

            expected_pids = list(SHADOW_PROFILES.keys())
            completed_pids = list(shadow_summaries.keys())
            missing_pids = [p for p in expected_pids if p not in completed_pids]
            is_eval_complete = (len(missing_pids) == 0)
            run_status = "PARTIAL_RUN" if not is_eval_complete else ("DEGRADED" if is_degraded else "COMPLETE")

            entry = TemporalCatalogEntry(
                ticker=ticker,
                snapshot_id=snapshot.snapshot_id,
                captured_at=datetime.now(timezone.utc).isoformat(),
                as_of=snapshot.as_of.isoformat(),
                market_data_date=market_date,
                profile_versions={p.profile_id: p.version for p in SHADOW_PROFILES.values()},
                factor_versions={f.factor_id: f.version for f in self.registry.list()},
                capability_coverage={k: v.value for k, v in snapshot.capability_statuses.items()},
                content_hash=content_hash,
                retention_tags=tags,
                quality_status="DEGRADED" if is_degraded else "VALIDATED",
                snapshot_path=str(saved_path.relative_to(self.snapshot_dir.parent)) if saved_path.is_relative_to(self.snapshot_dir.parent) else str(saved_path),
                expected_profiles=expected_pids,
                completed_profiles=completed_pids,
                missing_profiles=missing_pids,
                evaluation_complete=is_eval_complete,
                run_status=run_status,
                shadow_evaluations=shadow_summaries,
            )
            catalog.add_entry(entry)
            catalog.save(self.catalog_path)

        event = CaptureEvent(
            ticker=ticker,
            captured_at=datetime.now(timezone.utc),
            as_of=snapshot.as_of,
            snapshot_id=snapshot.snapshot_id,
            content_hash=content_hash,
            is_duplicate=is_dup,
            retained=retained,
            retention_tags=tags,
            is_degraded=is_degraded,
            degraded_reasons=degraded_reasons,
        )

        status = "DEGRADED" if is_degraded else ("DUPLICATE" if is_dup and not retained else "SUCCESS")
        return (
            CollectionResult(
                ticker=ticker,
                status=status,
                snapshot_id=snapshot.snapshot_id,
                content_hash=content_hash,
                retained=retained,
                tags=tags,
                quality="DEGRADED" if is_degraded else "VALIDATED",
                coverage_score=coverage_score,
                snapshot_path=str(saved_path) if saved_path else None,
            ),
            event,
        )

    def resume_incomplete_evaluations(
        self,
        *,
        catalog: TemporalCatalog | None = None,
    ) -> int:
        """Find any incomplete snapshot evaluation in catalog and finish missing evaluations."""
        if catalog is None:
            catalog = TemporalCatalog.load_or_create(self.catalog_path)

        completed_count = 0
        expected = list(SHADOW_PROFILES.keys())
        runner = MatchedShadowRunner()

        for entry in catalog.entries:
            missing = [p for p in expected if p not in entry.shadow_evaluations]
            if missing or not entry.evaluation_complete:
                snap_path = self.snapshot_dir / Path(entry.snapshot_path).name
                if not snap_path.exists():
                    continue
                try:
                    snapshot = FrozenDataSnapshot.model_validate_json(snap_path.read_text(encoding="utf-8"))
                except Exception:
                    continue

                for pid in missing:
                    prof = SHADOW_PROFILES[pid]
                    try:
                        matched = runner.run(snapshot.ticker, prof, snapshot.as_of, snapshot)
                        if self.results_dir:
                            save_shadow_result(matched, self.results_dir)
                        res = matched.new
                        entry.shadow_evaluations[pid] = ShadowEvaluationSummary(
                            profile_id=pid,
                            profile_version=res.profile_version,
                            strategy_score=float(res.strategy_score) if res.strategy_score is not None else None,
                            signal=res.signal,
                            confidence=res.confidence,
                            implemented_factor_coverage=float(res.implemented_factor_coverage),
                            strategy_evidence_coverage=float(res.strategy_evidence_coverage),
                            known_missing_dimensions=list(res.known_missing_dimensions),
                            proxy_dependence=any(item.factor_type.value == "proxy" for item in res.used_factors),
                            quality_status=entry.quality_status,
                            confidence_components=res.confidence_components.model_dump(mode="json") if res.confidence_components else None,
                        )
                        completed_count += 1
                    except Exception as e:
                        logger.warning("Failed to evaluate %s for %s during resume: %s", pid, snapshot.ticker, e)

                entry.completed_profiles = sorted(entry.shadow_evaluations.keys())
                entry.missing_profiles = [p for p in expected if p not in entry.shadow_evaluations]
                entry.evaluation_complete = (len(entry.missing_profiles) == 0)
                entry.run_status = "COMPLETE" if entry.evaluation_complete else "PARTIAL_RUN"

        catalog.save(self.catalog_path)
        return completed_count

    def collect_many(
        self,
        tickers: Sequence[str],
        *,
        capture_mode: str = "current",
    ) -> CollectorRunReport:
        start_time = datetime.now(timezone.utc)
        run_id = f"run_{start_time.strftime('%Y%m%dT%H%M%SZ')}"
        catalog = TemporalCatalog.load_or_create(self.catalog_path)
        batch = CollectorRunReport(
            run_id=run_id,
            started_at=start_time,
            requested_tickers=list(tickers),
        )

        for ticker in tickers:
            result, event = self.collect_ticker(ticker, capture_mode=capture_mode, catalog=catalog)
            if event:
                batch.events.append(event)
            batch.coverage_summary[ticker] = result.coverage_score

            if result.status == "FAILED":
                batch.snapshot_failed += 1
                batch.failed[ticker] = result.error or "unknown failure"
            elif result.status == "DUPLICATE":
                batch.snapshot_deduplicated += 1
                batch.deduplicated.append(ticker)
                batch.successful.append(ticker)
            elif result.status == "DEGRADED":
                batch.snapshot_created += 1
                batch.snapshot_degraded += 1
                batch.degraded.append(ticker)
                batch.successful.append(ticker)
            else:
                batch.snapshot_created += 1
                batch.successful.append(ticker)

        if self.run_shadow:
            batch.shadow_evaluations_success = batch.snapshot_created * len(SHADOW_PROFILES)

        end_time = datetime.now(timezone.utc)
        batch.completed_at = end_time
        batch.duration_seconds = round((end_time - start_time).total_seconds(), 2)
        return batch


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for collect-shadow-snapshots."""
    parser = argparse.ArgumentParser(
        prog="collect-shadow-snapshots",
        description="Accumulate point-in-time frozen snapshots with content deduplication.",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        required=True,
        help="List of A-share tickers to capture (e.g. 600519 000858 600438)",
    )
    parser.add_argument(
        "--output-dir",
        default="docs/baselines/shadow/live/snapshots",
        help="Directory to save snapshot JSON files.",
    )
    parser.add_argument(
        "--catalog",
        default="docs/baselines/shadow/live/temporal_catalog.json",
        help="Path to catalog index JSON.",
    )
    parser.add_argument(
        "--mode",
        choices=["current", "dry_run"],
        default="current",
        help="Capture mode (current or dry_run).",
    )

    args = parser.parse_args(argv)

    print(f"Collecting snapshots for {len(args.tickers)} tickers (mode: {args.mode})...")
    collector = SnapshotCollector(
        snapshot_dir=args.output_dir,
        catalog_path=args.catalog,
    )

    batch = collector.collect_many(args.tickers, capture_mode=args.mode)

    print("\n--- Collection Summary ---")
    print(f"Successful:   {len(batch.successful)} / {len(args.tickers)}")
    print(f"Degraded:     {len(batch.degraded)} ({', '.join(batch.degraded) if batch.degraded else 'None'})")
    print(f"Deduplicated: {len(batch.deduplicated)} ({', '.join(batch.deduplicated) if batch.deduplicated else 'None'})")
    print(f"Failed:       {len(batch.failed)} ({', '.join(f'{t}: {e}' for t, e in batch.failed.items()) if batch.failed else 'None'})")

    print("\nCoverage by ticker:")
    for ticker, cov in batch.coverage_summary.items():
        print(f"  {ticker}: {cov:.1%}")

    return 0 if not batch.failed else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
