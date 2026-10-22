"""Read-only live check for the BaoStock and AKShare A-share adapters.

Run from the repository root: python scripts/check_a_share_sources.py 600519
"""

import argparse
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import akshare as ak

from src.tools import a_share


def check(ticker: str) -> int:
    _, sina_code, index = a_share.normalize_ticker(ticker)
    if index:
        raise ValueError("Use an individual A-share stock, not an index")
    end_date = date.today().isoformat()
    failures = []
    quote = {}
    shares = None

    try:
        quote = a_share._latest_quote(ticker, end_date)
        if not quote:
            raise RuntimeError("no BaoStock trading row in the past 45 days")
        print(f"BaoStock: {quote['date']} close={quote.get('close')} PE={quote.get('peTTM')} PB={quote.get('pbMRQ')} PS={quote.get('psTTM')}")
    except Exception as exc:
        failures.append(f"BaoStock: {type(exc).__name__}")

    try:
        frames = a_share._statements(sina_code)
        for name, frame in frames.items():
            visible = a_share._visible(frame, end_date)
            if not visible:
                raise RuntimeError(f"{name} has no announced report")
            print(f"AKShare/Sina {name}: {len(frame)} rows, latest announced period {max(visible)}")
    except Exception as exc:
        failures.append(f"AKShare/Sina statements: {type(exc).__name__}")

    try:
        history = a_share._share_history(sina_code)
        shares = a_share._shares_as_of(history, quote.get("date"))
        if shares is None:
            raise RuntimeError("no dated total shares at the BaoStock trading date")
        print(f"AKShare/Eastmoney share capital: {len(history)} change records, {shares:,.0f} shares as of {quote['date']}")
        estimated_cap = a_share._market_cap(quote, shares)
        print(f"Calculated market cap: CNY {estimated_cap:,.2f}")
    except Exception as exc:
        failures.append(f"AKShare/Eastmoney share capital: {type(exc).__name__}")

    snapshot_checked = False
    if shares is not None and quote:
        try:
            snapshot = ak.stock_individual_info_em(symbol=sina_code[-6:], timeout=10)
            items = dict(zip(snapshot["item"], snapshot["value"]))
            snapshot_shares = a_share._number(items.get("总股本"))
            snapshot_cap = a_share._number(items.get("总市值"))
            if not snapshot_shares or not snapshot_cap:
                raise ValueError("current total shares or market cap unavailable")
        except Exception as exc:
            print(f"WARNING optional current snapshot unavailable: {type(exc).__name__}; market-cap cross-check incomplete", file=sys.stderr)
        else:
            snapshot_checked = True
            share_gap = abs(shares / snapshot_shares - 1)
            cap_gap = abs(a_share._market_cap(quote, shares) / snapshot_cap - 1)
            print(f"AKShare/Eastmoney current snapshot: {snapshot_shares:,.0f} shares, CNY {snapshot_cap:,.2f} market cap")
            print(f"Cross-check gaps: shares {share_gap:.2%}, market cap {cap_gap:.2%}")
            if share_gap > 0.01 or cap_gap > 0.10:
                failures.append("Current market-cap cross-check: gap exceeds 1% shares or 10% market cap")

    for failure in failures:
        print(f"FAILED {failure}", file=sys.stderr)
    if not failures:
        print("PASS: core source connectivity, fields, and dated shares" + ("; current snapshot cross-check passed" if snapshot_checked else "; current snapshot not checked"))
    return int(bool(failures))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticker", help="Shanghai/Shenzhen six-digit stock code, e.g. 600519")
    args = parser.parse_args()
    raise SystemExit(check(args.ticker))
