#!/usr/bin/env python3
"""Capture current provider data once and run all requested profiles offline."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import warnings
import traceback

import pandas as pd

from src.investors.profiles import PILOT_PROFILES
from src.investors.shadow import (
    FrozenDataSnapshot, MatchedShadowRunner, save_frozen_snapshot,
    save_shadow_result,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tickers", nargs="+", help="A-share ticker codes to capture once")
    parser.add_argument("--output-dir", default="docs/baselines/shadow/live",
                        help="directory for frozen snapshots and JSON results")
    parser.add_argument("--profiles", nargs="*", choices=sorted(PILOT_PROFILES),
                        help="profile ids; defaults to all three B4 pilots")
    parser.add_argument("--debug", action="store_true",
                        help="show third-party fetch output and warnings")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    snapshot_dir = output_dir / "snapshots"
    result_dir = output_dir / "results"
    profiles = [PILOT_PROFILES[key] for key in (args.profiles or sorted(PILOT_PROFILES))]
    runner = MatchedShadowRunner()
    failures = 0

    for ticker in args.tickers:
        try:
            if args.debug:
                frozen = FrozenDataSnapshot.capture_current(ticker)
            else:
                # BaoStock prints its login/logout banners directly to stdout;
                # AkShare's SettingWithCopyWarning is non-fatal here. Keep the
                # default capture output focused on the saved data/result.
                with redirect_stdout(StringIO()), warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)
                    frozen = FrozenDataSnapshot.capture_current(ticker)
            snapshot_path = save_frozen_snapshot(frozen, snapshot_dir)
            print(f"SNAPSHOT {ticker} as_of={frozen.as_of.isoformat()} "
                  f"id={frozen.snapshot_id[:12]} file={snapshot_path}")
            _print_coverage(frozen)
        except Exception as exc:
            failures += 1
            print(f"FAILED {ticker}: {type(exc).__name__}" +
                  (f": {exc}" if args.debug else " (use --debug for details)"))
            if args.debug:
                traceback.print_exc()
            continue

        for profile in profiles:
            result = runner.run(ticker, profile, frozen.as_of, frozen)
            result_path = save_shadow_result(result, result_dir)
            print(f"MATCHED {ticker} {profile.profile_id} {profile.version}: "
                  f"legacy={result.legacy.signal}/{result.legacy.confidence:.1f} "
                  f"new={result.new.signal}/{result.new.confidence:.1f} "
                  f"score={result.new.strategy_score} "
                  f"core={result.new.core_coverage} total={result.new.overall_coverage} "
                  f"file={result_path}")
    return 1 if failures else 0


def _print_coverage(snapshot: FrozenDataSnapshot) -> None:
    envelope_rows = [
        ("prices", snapshot.price_history,
         lambda rows: f"{len(rows)} bars through {rows[-1].trading_date}"),
        *[(key, envelope,
           lambda rows: f"{len(rows)} periods through {max(row.period_end for row in rows)}")
          for key, envelope in sorted(snapshot.financial_statements.items())],
        ("valuation", snapshot.valuation_history,
         lambda rows: f"{len(rows)} rows through {rows[-1].observed_date}"),
        ("share_capital", snapshot.share_capital_history,
         lambda rows: f"{len(rows)} events through {rows[-1].effective_date}"),
        ("industry", snapshot.industry, lambda value: value.industry or value.name),
        ("dividends", snapshot.dividends,
         lambda rows: f"{len(rows)} events through {rows[-1].ex_date}"),
    ]
    for label, envelope, describe in envelope_rows:
        if envelope.observation is None:
            print(f"  {label}: {envelope.provider} {envelope.status.value}")
            continue
        value = envelope.observation.value
        rows = value if isinstance(value, list) else value
        detail = describe(rows) if rows else "0 rows"
        print(f"  {label}: {envelope.provider} {envelope.status.value}; {detail}")


if __name__ == "__main__":
    raise SystemExit(main())
