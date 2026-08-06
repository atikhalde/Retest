"""
Command-line entrypoints.

    python -m smc_scanner.cli build-universe
    python -m smc_scanner.cli scan --mode eod
    python -m smc_scanner.cli scan --mode intraday
    python -m smc_scanner.cli backtest --years 3
"""
import argparse
import sys

import pandas as pd

from .config import Config
from .universe import build_universe, get_universe
from .data_sources import get_data_source
from .scanner import run_scan
from .backtest import run_backtest, render_markdown_report


def cmd_build_universe(args):
    cfg = Config.from_env()
    build_universe(cfg, max_workers=args.workers)


def cmd_scan(args):
    cfg = Config.from_env()
    cfg.scan_mode = args.mode
    if args.data_source:
        cfg.data_source = args.data_source

    universe_df = get_universe(cfg)
    if args.limit:
        universe_df = universe_df.head(args.limit)
    print(f"[scan] universe size after market-cap filter (>= {cfg.min_market_cap_cr} cr): {len(universe_df)}")

    data_source = get_data_source(cfg)
    results = run_scan(cfg, universe_df, data_source, max_workers=args.workers,
                        send_alerts=not args.no_alerts)

    if results.empty:
        print("No pattern matches found.")
        return

    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 30)
    key_stages = results[results["stage"].isin(["FRESH_BOS2", "PRE_BOS2_READY"])]
    print("\n=== ACTIONABLE (FRESH_BOS2 / PRE_BOS2_READY) ===")
    print(key_stages.to_string(index=False) if not key_stages.empty else "(none this run)")
    print(f"\nFull results -> {cfg.results_dir}/latest_scan.csv  ({len(results)} rows)")


def cmd_backtest(args):
    cfg = Config.from_env()
    cfg.data_source = args.data_source
    data_source = get_data_source(cfg)

    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    elif args.symbols_file:
        with open(args.symbols_file) as f:
            symbols = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    else:
        universe_df = get_universe(cfg)
        symbols = universe_df["symbol"].tolist()
        if args.data_source == "yfinance":
            symbols = [f"{s}.NS" for s in symbols]
        if args.limit:
            symbols = symbols[: args.limit]

    print(f"[backtest] running on {len(symbols)} symbols")
    result = run_backtest(symbols, cfg, data_source)

    import os
    os.makedirs(cfg.results_dir, exist_ok=True)
    result["bos2_trades"].to_csv(f"{cfg.results_dir}/backtest_bos2_trades.csv", index=False)
    result["pre_bos2_trades"].to_csv(f"{cfg.results_dir}/backtest_pre_bos2_trades.csv", index=False)
    result["summary"].to_csv(f"{cfg.results_dir}/backtest_summary.csv", index=False)

    report = render_markdown_report(result, cfg)
    with open(f"{cfg.results_dir}/backtest_report.md", "w") as f:
        f.write(report)

    print(report)


def main():
    ap = argparse.ArgumentParser(prog="smc_scanner")
    sub = ap.add_subparsers(dest="command", required=True)

    p1 = sub.add_parser("build-universe", help="Rebuild data/universe.csv from Dhan scrip master + market caps")
    p1.add_argument("--workers", type=int, default=16)
    p1.set_defaults(func=cmd_build_universe)

    p2 = sub.add_parser("scan", help="Run a scan")
    p2.add_argument("--mode", choices=["eod", "intraday"], default="eod")
    p2.add_argument("--data-source", choices=["dhan", "yfinance"], default=None)
    p2.add_argument("--workers", type=int, default=4)
    p2.add_argument("--limit", type=int, default=None, help="Only scan first N symbols (debug)")
    p2.add_argument("--no-alerts", action="store_true")
    p2.set_defaults(func=cmd_scan)

    p3 = sub.add_parser("backtest", help="Run historical backtest")
    p3.add_argument("--data-source", choices=["dhan", "yfinance"], default="yfinance")
    p3.add_argument("--symbols", type=str, default=None)
    p3.add_argument("--symbols-file", type=str, default=None)
    p3.add_argument("--limit", type=int, default=100)
    p3.set_defaults(func=cmd_backtest)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
