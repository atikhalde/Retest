"""
Rule-testing sweep: for every historical BOS1 breakout (genuine new N-week
high) found across a universe, tag which of the ORIGINAL 9 TradingView-style
conditions were true in that breakout's week, then measure two real outcome
metrics per rule:

  1. Pattern win rate  - did the resulting retest/re-accumulation chain go
     on to a CONFIRMED BOS2 breakout (a "win"), or INVALIDATE/TIMEOUT
     (a "loss")? STILL_OPEN chains are excluded (outcome not yet known).
  2. Forward return  - buying the BOS1 breakout itself (next day's open),
     what's the win rate / avg return at fixed forward horizons (5, 10, 20
     trading days)?

For each of the 9 rules we report: N (how many historical breakouts had
that rule TRUE), pattern win rate, and forward-return win rate/avg return
at each horizon - split by rule=True vs rule=False, so you can see whether
requiring that rule actually helps or just throws away sample size.

Usage:
    python scripts/analyze_bos1_rules.py --symbols-file data/backtest_universe_sample.txt --years 5
    python scripts/analyze_bos1_rules.py --symbols PGIL,AUBANK,ALKEM
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from smc_scanner.config import Config
from smc_scanner.indicators import add_indicators, ema, rsi, macd_hist
from smc_scanner.weekly import resample_weekly, find_daily_bos1_candidates
from smc_scanner.backtest import enumerate_chains, _forward_trade
from smc_scanner.data_sources.yfinance_source import YFinanceDataSource

RULE_NAMES = [
    "1_new_26w_high", "2_freshly_broken", "3_ema20_gt_ema50", "4_ema50_rising",
    "5_rsi_gt_60", "6_rsi_rising", "7_macd_hist_pos", "8_vol_gt_sma10", "9_green_candle",
]

HORIZONS = (5, 10, 20)


def weekly_rule_table(df: pd.DataFrame, cfg) -> pd.DataFrame:
    """One row per week, with all 9 original boolean conditions."""
    w = resample_weekly(df)
    n_weeks = cfg.bos1_lookback_weeks
    close, open_, high, vol = w["Close"], w["Open"], w["High"], w["Volume"]

    roll_high = high.rolling(n_weeks).max()
    high_1wk_ago = roll_high.shift(1)
    high_2wk_ago = roll_high.shift(2)
    ema20 = ema(close, 20)
    ema50 = ema(close, 50)
    rsi14 = rsi(close, 14)
    macdh = macd_hist(close)
    vol_sma10 = vol.rolling(10).mean()

    rules = pd.DataFrame({
        "1_new_26w_high": close > high_1wk_ago,
        "2_freshly_broken": close.shift(1) <= high_2wk_ago,
        "3_ema20_gt_ema50": ema20 > ema50,
        "4_ema50_rising": ema50 > ema50.shift(2),
        "5_rsi_gt_60": rsi14 > cfg.rsi_min,
        "6_rsi_rising": rsi14 > rsi14.shift(1),
        "7_macd_hist_pos": macdh > 0,
        "8_vol_gt_sma10": vol > vol_sma10,
        "9_green_candle": close > open_,
    })
    return rules


def analyze(symbols, cfg, days) -> pd.DataFrame:
    ds = YFinanceDataSource(cfg)
    rows = []

    for i, symbol in enumerate(symbols):
        try:
            df = ds.fetch_ohlc(symbol, days=days)
        except Exception as e:
            print(f"  [!] {symbol}: {e}")
            continue
        if df is None or df.empty or len(df) < 200:
            continue
        df = add_indicators(df, cfg)
        rules = weekly_rule_table(df, cfg)
        chains = enumerate_chains(df, cfg, symbol)
        bos1_candidates = find_daily_bos1_candidates(df, cfg)
        # map bos1_idx -> outcome via the chain that starts there
        outcome_by_bos1 = {c.bos1_idx: c.outcome for c in chains}
        n = len(df)
        close = df["Close"].values

        for bos1_idx, p0_price, p0_date in bos1_candidates:
            bos1_date = df.index[bos1_idx]
            # resample_weekly labels each week by its ending Friday - find
            # the first weekly-row date >= bos1_date (robust to pandas
            # DateOffset quirks around exact-Friday dates, which an earlier
            # version of this script got wrong, silently mis-mapping ~15-25%
            # of candidates to the wrong week and corrupting rules 1/2).
            candidates_idx = rules.index[rules.index >= bos1_date]
            if len(candidates_idx) == 0:
                continue
            week_end = candidates_idx[0]
            if week_end not in rules.index or rules.loc[week_end].isna().any():
                continue

            row = {"symbol": symbol, "bos1_date": bos1_date}
            for rn in RULE_NAMES:
                row[rn] = bool(rules.loc[week_end, rn])

            outcome = outcome_by_bos1.get(bos1_idx)
            row["outcome"] = outcome
            row["is_win"] = (outcome == "BOS2_CONFIRMED") if outcome in ("BOS2_CONFIRMED", "INVALIDATED", "TIMEOUT") else None

            trade = _forward_trade(df, bos1_idx, p0_price * (1 - cfg.max_undercut_pct), HORIZONS)
            if trade:
                for h in HORIZONS:
                    row[f"ret_{h}d"] = trade.get(f"ret_{h}d_pct")
            rows.append(row)

        if (i + 1) % 20 == 0:
            print(f"[analyze] processed {i+1}/{len(symbols)} symbols, {len(rows)} BOS1 candidates so far")

    return pd.DataFrame(rows)


def summarize(df: pd.DataFrame):
    print(f"\nTotal BOS1 candidates analyzed: {len(df)}")
    resolved = df[df["is_win"].notna()]
    print(f"Resolved (BOS2_CONFIRMED/INVALIDATED/TIMEOUT): {len(resolved)} "
          f"(baseline win rate: {resolved['is_win'].mean()*100:.1f}%)")
    for h in HORIZONS:
        col = f"ret_{h}d"
        if col in df.columns:
            vals = df[col].dropna()
            print(f"Baseline {h}d forward return: win rate {(vals>0).mean()*100:.1f}%, "
                  f"avg {vals.mean():.2f}%, n={len(vals)}")

    print("\n" + "=" * 110)
    print(f"{'Rule':<22}{'N(True)':>9}{'PatternWin%':>13}{'N(False)':>10}{'PatternWin%':>13}   |  "
          f"{'5d win%/avg':>14}{'10d win%/avg':>15}{'20d win%/avg':>15}")
    print("=" * 110)
    for rn in RULE_NAMES:
        true_df = df[df[rn] == True]
        false_df = df[df[rn] == False]

        def pattern_win(sub):
            r = sub[sub["is_win"].notna()]
            return (r["is_win"].mean() * 100, len(r)) if len(r) else (float("nan"), 0)

        t_pw, t_n = pattern_win(true_df)
        f_pw, f_n = pattern_win(false_df)

        horizon_strs = []
        for h in HORIZONS:
            col = f"ret_{h}d"
            tv = true_df[col].dropna() if col in true_df.columns else pd.Series(dtype=float)
            wr = (tv > 0).mean() * 100 if len(tv) else float("nan")
            av = tv.mean() if len(tv) else float("nan")
            horizon_strs.append(f"{wr:5.1f}%/{av:+5.2f}%")

        print(f"{rn:<22}{len(true_df):>9}{t_pw:>12.1f}%{len(false_df):>10}{f_pw:>12.1f}%   |  " +
              "".join(f"{s:>15}" for s in horizon_strs))
    print("=" * 110)
    print("(PatternWin% = % of resolved chains starting from this BOS1 that reached BOS2_CONFIRMED)")
    print("(Xd win%/avg = win rate and average return X trading days after buying the BOS1 breakout itself, rule=True subset only)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", type=str, default=None)
    ap.add_argument("--symbols-file", type=str, default=None)
    ap.add_argument("--years", type=float, default=5.0)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    cfg = Config()
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    elif args.symbols_file:
        with open(args.symbols_file) as f:
            symbols = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    else:
        symbols = ["PGIL.NS", "AUBANK.NS", "ALKEM.NS", "CUMMINSIND.NS"]
    if args.limit:
        symbols = symbols[: args.limit]

    days = int(args.years * 365.25)
    print(f"[analyze] {len(symbols)} symbols, {args.years}y history (~{days}d)")
    df = analyze(symbols, cfg, days)
    os.makedirs("results", exist_ok=True)
    df.to_csv("results/bos1_rule_analysis.csv", index=False)
    print(f"\nWrote results/bos1_rule_analysis.csv ({len(df)} rows)")
    summarize(df)
