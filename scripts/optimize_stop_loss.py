"""
Stop-loss optimizer for the Reaccum-Reversal entry style, focused on the
4-7 trading day holding window already identified as the best short-term
horizon (see README "Best holding period found so far").

Tests two families of stop-loss placement against every historical reversal
signal in the universe:

    1) Fixed % below entry price: 1, 1.5, 2, 2.5, 3, 4, 5, 7, 10%
    2) The structural stop already used elsewhere (the chain's retest low)
    3) ATR-multiple stops: 1x, 1.5x, 2x, 2.5x ATR(14) below entry

For each stop-loss method x each holding period in {3,4,5,6,7,10} days, it
reports win rate, average return, average risk actually taken (the stop
distance in %), and a reward:risk ratio, so you can see which stop is most
capital-efficient for a short hold - not just which has the highest win
rate (a very tight stop can "win" more per trade but get stopped out so
often that expectancy is worse).
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from smc_scanner.config import Config
from smc_scanner.data_sources.yfinance_source import YFinanceDataSource
from smc_scanner.indicators import add_indicators
from smc_scanner.backtest import enumerate_chains, chain_base_info

HOLD_DAYS = (3, 4, 5, 6, 7, 10)
FIXED_SL_PCTS = (0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05, 0.07, 0.10)
ATR_MULTS = (1.0, 1.5, 2.0, 2.5)

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")


def simulate(df, entry_idx, stop_price, hold_days):
    """One trade: enter at entry_idx+1's Open, exit at min(stop hit, hold_days close)."""
    n = len(df)
    if entry_idx + 1 >= n:
        return None
    entry_price = df["Open"].values[entry_idx + 1]
    if entry_price <= 0 or np.isnan(entry_price):
        return None
    end_i = entry_idx + 1 + hold_days
    if end_i >= n:
        return None
    low = df["Low"].values
    close = df["Close"].values

    window_low = low[entry_idx + 1: end_i + 1].min()
    stopped = window_low <= stop_price
    if stopped:
        ret = (stop_price - entry_price) / entry_price * 100
    else:
        ret = (close[end_i] - entry_price) / entry_price * 100
    risk_pct = (entry_price - stop_price) / entry_price * 100
    return {"return_pct": ret, "stopped": stopped, "risk_pct": risk_pct, "entry_price": entry_price}


def run(symbols, cfg):
    data_source = YFinanceDataSource(cfg)
    rows = []

    for symbol in symbols:
        try:
            df = data_source.fetch_ohlc(symbol)
        except Exception as e:
            print(f"  [!] {symbol}: {e}")
            continue
        if df is None or df.empty or len(df) < 80:
            continue
        df = add_indicators(df, cfg)
        chains = enumerate_chains(df, cfg, symbol)

        close = df["Close"].values
        low = df["Low"].values
        atr = df["ATR"].values

        for c in chains:
            info = chain_base_info(c, df, cfg)
            rev_date = info["reaccum_reversal_date"]
            if rev_date is None:
                continue
            rev_idx = df.index.get_loc(rev_date)
            entry_open_idx = rev_idx + 1
            if entry_open_idx >= len(df):
                continue
            entry_price_ref = df["Open"].values[entry_open_idx]
            retest_price = c.retest_price
            atr_at_entry = atr[rev_idx] if not np.isnan(atr[rev_idx]) else None

            for hold in HOLD_DAYS:
                # 1) fixed % stops
                for pct in FIXED_SL_PCTS:
                    stop_price = entry_price_ref * (1 - pct)
                    res = simulate(df, rev_idx, stop_price, hold)
                    if res:
                        rows.append({"method": f"Fixed {pct*100:.1f}%", "hold_days": hold, **res, "symbol": symbol})

                # 2) structural stop (chain retest low)
                res = simulate(df, rev_idx, retest_price, hold)
                if res:
                    rows.append({"method": "Structural (retest low)", "hold_days": hold, **res, "symbol": symbol})

                # 3) ATR multiple stops
                if atr_at_entry:
                    for mult in ATR_MULTS:
                        stop_price = entry_price_ref - mult * atr_at_entry
                        res = simulate(df, rev_idx, stop_price, hold)
                        if res:
                            rows.append({"method": f"{mult}x ATR", "hold_days": hold, **res, "symbol": symbol})

    return pd.DataFrame(rows)


def summarize(trades: pd.DataFrame) -> pd.DataFrame:
    g = trades.groupby(["method", "hold_days"])
    out = g.agg(
        n_trades=("return_pct", "count"),
        win_rate_pct=("return_pct", lambda s: round((s > 0).mean() * 100, 1)),
        avg_return_pct=("return_pct", lambda s: round(s.mean(), 2)),
        median_return_pct=("return_pct", lambda s: round(s.median(), 2)),
        stopped_out_pct=("stopped", lambda s: round(s.mean() * 100, 1)),
        avg_risk_pct=("risk_pct", lambda s: round(s.mean(), 2)),
    ).reset_index()
    out["reward_risk"] = (out["avg_return_pct"] / out["avg_risk_pct"]).round(2)
    return out.sort_values(["hold_days", "avg_return_pct"], ascending=[True, False])


if __name__ == "__main__":
    cfg = Config()
    with open(os.path.join(os.path.dirname(__file__), "..", "data", "backtest_universe_sample.txt")) as f:
        symbols = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    print(f"Running stop-loss sweep on {len(symbols)} symbols...")
    trades = run(symbols, cfg)
    trades.to_csv(os.path.join(RESULTS_DIR, "sl_optimization_trades.csv"), index=False)

    summary = summarize(trades)
    summary.to_csv(os.path.join(RESULTS_DIR, "sl_optimization_summary.csv"), index=False)

    pd.set_option("display.width", 160)
    pd.set_option("display.max_rows", 200)
    print(summary.to_string(index=False))

    print("\n=== BEST METHOD PER HOLDING PERIOD (by avg return) ===")
    best = summary.loc[summary.groupby("hold_days")["avg_return_pct"].idxmax()]
    print(best.to_string(index=False))

    print("\n=== BEST METHOD PER HOLDING PERIOD (by reward:risk) ===")
    best_rr = summary.loc[summary.groupby("hold_days")["reward_risk"].idxmax()]
    print(best_rr.to_string(index=False))
