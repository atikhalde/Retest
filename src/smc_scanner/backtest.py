"""
Historical backtest of the pattern's forward-return edge.

For every symbol we walk the *entire* available history once and enumerate
every retest -> re-accumulation chain (not just the most recent one, unlike
the live scanner). Each chain resolves to exactly one outcome:

    BOS2_CONFIRMED  - price broke back above P1 with a volume kick
                      (the "FRESH_BOS2" trigger)
    INVALIDATED     - price closed below P0 by more than `max_undercut_pct`
                      before ever breaking out (structure failed)
    TIMEOUT         - re-accumulation dragged on past `max_reaccum_bars`
                      without resolving either way
    STILL_OPEN      - hit the end of available data before resolving
                      (excluded from stats - outcome unknown)

For every chain we also record whether/when it first satisfied the
PRE_BOS2_READY condition (coiled + re-accumulation minimum met), so we can
directly compare two entry strategies:

    1) Enter on BOS2 confirmation (the conservative, confirmed breakout)
    2) Enter on first PRE_BOS2_READY flag (the anticipatory / better-price
       entry the live scanner also raises as its own alert stage)

Both are evaluated with the same realistic mechanics: entry at next bar's
Open, a hard stop at the chain's retest low, and returns measured at fixed
forward horizons.

Every exported row (whether in "All Chains", "BOS2 Trades" or
"PreBOS2 Trades") carries the FULL stage history of that pattern instance -
symbol, P0/base date & price, BOS1 date & price, P1 date & price, retest
date & price, how many bars it re-accumulated, the PRE_BOS2_READY date (if
any), the BOS2 date & price (if confirmed), and the final outcome - so you
can trace exactly which real dates the algorithm used for every trade.

This is research tooling, not investment advice - use it to sanity check
(and re-tune) the scanner's parameters before trusting its live alerts.
"""
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd

from .pivots import find_pivots

HORIZONS = (5, 10, 20, 40, 60)


@dataclass
class Chain:
    symbol: str
    p0_idx: int
    p0_price: float
    bos1_idx: int
    bos1_price: float
    p1_idx: int
    p1_price: float
    retest_idx: int
    retest_price: float
    outcome: str
    end_idx: Optional[int]
    pre_bos2_ready_idx: Optional[int] = None


def enumerate_chains(df: pd.DataFrame, cfg, symbol: str) -> List[Chain]:
    ph, _ = find_pivots(df, cfg.pivot_left, cfg.pivot_right)
    piv_high_idx = [i for i, v in enumerate(ph) if v]
    n = len(df)

    close = df["Close"].values
    high = df["High"].values
    low = df["Low"].values
    vol = df["Volume"].values
    vol_sma20 = df["VOL_SMA20"].values if "VOL_SMA20" in df.columns else np.full(n, np.nan)

    seen_keys = set()
    chains: List[Chain] = []

    for i0 in piv_high_idx:
        p0_price = high[i0]

        bos1_idx = None
        for j in range(i0 + cfg.pivot_right + 1, n):
            vsma = vol_sma20[j] if not np.isnan(vol_sma20[j]) else np.inf
            if close[j] > p0_price * (1 + cfg.breakout_buffer) and vol[j] >= cfg.vol_mult_impulse * vsma:
                bos1_idx = j
                break
        if bos1_idx is None:
            continue

        run_max_idx, run_max, p1_idx = bos1_idx, high[bos1_idx], None
        k = bos1_idx + 1
        while k < n:
            if high[k] > run_max:
                run_max, run_max_idx = high[k], k
            if close[k] < run_max * 0.97:
                p1_idx = run_max_idx
                break
            k += 1
        if p1_idx is None:
            continue
        p1_price = high[p1_idx]

        retest_idx, invalidated = None, False
        m, running_min, running_min_idx = p1_idx + 1, np.inf, None
        while m < n:
            if low[m] < running_min:
                running_min, running_min_idx = low[m], m
            if close[m] < p0_price * (1 - cfg.max_undercut_pct):
                invalidated = True
                break
            zone_lo, zone_hi = p0_price * (1 - cfg.retest_zone_pct), p0_price * (1 + cfg.retest_zone_pct)
            if running_min_idx is not None and zone_lo <= running_min <= zone_hi:
                if close[m] > running_min * 1.02:
                    retest_idx = running_min_idx
                    break
            m += 1
        if invalidated or retest_idx is None:
            continue

        key = (bos1_idx, retest_idx)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        retest_price = low[retest_idx]

        earliest_bos2 = retest_idx + cfg.min_reaccum_bars
        latest_bos2 = retest_idx + cfg.max_reaccum_bars
        outcome, end_idx, pre_ready_idx = "STILL_OPEN", None, None

        for r in range(retest_idx + 1, min(latest_bos2, n)):
            if close[r] < p0_price * (1 - cfg.max_undercut_pct):
                outcome, end_idx = "INVALIDATED", r
                break
            if r >= earliest_bos2:
                dist = (p1_price - close[r]) / p1_price
                if pre_ready_idx is None and dist <= cfg.pre_bos2_proximity_pct and close[r] < p1_price * (1 + cfg.breakout_buffer):
                    pre_ready_idx = r
                vsma = vol_sma20[r] if not np.isnan(vol_sma20[r]) else np.inf
                if close[r] > p1_price * (1 + cfg.breakout_buffer) and vol[r] >= cfg.vol_mult_bos2 * vsma:
                    outcome, end_idx = "BOS2_CONFIRMED", r
                    break
        else:
            if min(latest_bos2, n) <= n - 1 and latest_bos2 <= n:
                outcome, end_idx = "TIMEOUT", min(latest_bos2, n) - 1

        chains.append(Chain(
            symbol=symbol, p0_idx=i0, p0_price=p0_price, bos1_idx=bos1_idx, bos1_price=close[bos1_idx],
            p1_idx=p1_idx, p1_price=p1_price, retest_idx=retest_idx, retest_price=retest_price,
            outcome=outcome, end_idx=end_idx, pre_bos2_ready_idx=pre_ready_idx,
        ))

    return chains


def _d(df, idx):
    return df.index[idx] if idx is not None else None


def chain_base_info(chain: Chain, df: pd.DataFrame) -> dict:
    """Every stage date/price for a chain, human-readable, regardless of outcome."""
    reaccum_end_idx = chain.end_idx if chain.outcome != "STILL_OPEN" else None
    info = {
        "symbol": chain.symbol,
        "outcome": chain.outcome,
        "p0_date": _d(df, chain.p0_idx),
        "p0_price": round(float(chain.p0_price), 2),
        "bos1_date": _d(df, chain.bos1_idx),
        "bos1_price": round(float(chain.bos1_price), 2),
        "p1_date": _d(df, chain.p1_idx),
        "p1_price": round(float(chain.p1_price), 2),
        "retest_date": _d(df, chain.retest_idx),
        "retest_price": round(float(chain.retest_price), 2),
        "reaccumulation_start_date": _d(df, chain.retest_idx + 1) if chain.retest_idx + 1 < len(df) else None,
        "pre_bos2_ready_date": _d(df, chain.pre_bos2_ready_idx),
        "reaccum_bars": (reaccum_end_idx - chain.retest_idx) if reaccum_end_idx is not None else None,
        "bos2_date": _d(df, chain.end_idx) if chain.outcome == "BOS2_CONFIRMED" else None,
        "bos2_price": round(float(df["Close"].values[chain.end_idx]), 2) if chain.outcome == "BOS2_CONFIRMED" else None,
        "invalidated_date": _d(df, chain.end_idx) if chain.outcome == "INVALIDATED" else None,
        "timeout_date": _d(df, chain.end_idx) if chain.outcome == "TIMEOUT" else None,
    }
    return info


def _forward_trade(df: pd.DataFrame, entry_idx: int, stop_price: float, horizons=HORIZONS) -> Optional[dict]:
    """
    Simulates one trade: enter at the next bar's Open after `entry_idx`, hard
    stop at `stop_price`, measure returns at each horizon in `horizons`.

    Three possible outcomes per row, captured in `trade_status`:
      PENDING_ENTRY - the signal fired on the most recent available bar, so
                      there's no "next session" data yet to actually enter on
                      (this is what a signal generated *today* looks like -
                      it's still included in the export, just with entry/
                      returns left blank until the next session's data exists)
      STOPPED_OUT   - the stop was hit at some point; every horizon from
                      then on reports that same locked-in exit return, even
                      if we don't yet have that many days of trailing data
                      (once stopped, the trade is closed - no more data needed)
      OPEN/COMPLETE - never stopped; a horizon shows the mark-to-close return
                      if we have that much trailing data yet, else blank
    """
    n = len(df)
    if entry_idx >= n - 1:
        return {
            "entry_date": None, "entry_price": None, "stop_price": round(float(stop_price), 2),
            **{f"ret_{h}d_pct": None for h in horizons},
            "stopped_out": None, "stopped_out_within_days": None,
            "trade_status": "PENDING_ENTRY (signal is on the most recent bar - no next-session open yet)",
        }

    entry_price = df["Open"].values[entry_idx + 1]
    if entry_price <= 0 or np.isnan(entry_price):
        return None

    close = df["Close"].values
    low = df["Low"].values
    result = {"entry_date": df.index[entry_idx + 1], "entry_price": round(float(entry_price), 2),
              "stop_price": round(float(stop_price), 2)}

    stopped_at = None
    for h in horizons:
        if stopped_at is not None:
            # trade already closed at the stop earlier - that return is final
            # regardless of whether `h` days of trailing data exist yet
            result[f"ret_{h}d_pct"] = round(float((stop_price - entry_price) / entry_price * 100), 2)
            continue
        end_i = entry_idx + 1 + h
        if end_i >= n:
            result[f"ret_{h}d_pct"] = None
            continue
        window_low = low[entry_idx + 1: end_i + 1].min()
        if window_low <= stop_price:
            stopped_at = h
            ret = (stop_price - entry_price) / entry_price * 100
        else:
            ret = (close[end_i] - entry_price) / entry_price * 100
        result[f"ret_{h}d_pct"] = round(float(ret), 2)

    result["stopped_out"] = stopped_at is not None
    result["stopped_out_within_days"] = stopped_at
    last_horizon_available = entry_idx + 1 + horizons[-1] < n
    result["trade_status"] = "STOPPED_OUT" if stopped_at is not None else (
        "COMPLETE" if last_horizon_available else "OPEN (still within holding period, more horizons pending)")
    return result


# canonical column order for the trade-level exports
TRADE_COLUMN_ORDER = [
    "symbol", "outcome", "trade_status",
    "p0_date", "p0_price", "bos1_date", "bos1_price", "p1_date", "p1_price",
    "retest_date", "retest_price", "reaccumulation_start_date", "reaccum_bars",
    "pre_bos2_ready_date", "bos2_date", "bos2_price",
    "signal_date", "signal_price", "entry_date", "entry_price", "stop_price",
    "ret_5d_pct", "ret_10d_pct", "ret_20d_pct", "ret_40d_pct", "ret_60d_pct",

    "stopped_out", "stopped_out_within_days", "eventually_confirmed",
]


def _reorder(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    cols = [c for c in TRADE_COLUMN_ORDER if c in df.columns] + [c for c in df.columns if c not in TRADE_COLUMN_ORDER]
    return df[cols]


def run_backtest(symbols: List[str], cfg, data_source, horizons=HORIZONS) -> dict:
    from .indicators import add_indicators, confluence_score
    from .pattern import detect_pattern

    all_chain_rows = []
    all_trades_bos2 = []
    all_trades_pre = []
    live_signals = []
    outcome_counts = {"BOS2_CONFIRMED": 0, "INVALIDATED": 0, "TIMEOUT": 0, "STILL_OPEN": 0}

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

        # Same-day cross-check with the live scanner's detector: is this
        # symbol showing a PRE_BOS2_READY / FRESH_BOS2 setup as of the very
        # last bar in the data we just fetched? This is what surfaces
        # "PGIL-right-now"-type setups distinctly from the historical stats.
        try:
            live_match = detect_pattern(df, cfg, symbol)
            if live_match is not None and live_match.stage in ("FRESH_BOS2", "PRE_BOS2_READY"):
                conf = confluence_score(df, cfg)
                live_signals.append({
                    "symbol": symbol, "stage": live_match.stage,
                    "last_date": live_match.last_date, "last_close": round(float(live_match.last_close), 2),
                    "p0_price": round(float(live_match.p0_price), 2) if live_match.p0_price else None,
                    "bos1_date": live_match.bos1_date, "bos1_price": round(float(live_match.bos1_price), 2) if live_match.bos1_price else None,
                    "p1_resistance": round(float(live_match.p1_price), 2) if live_match.p1_price else None,
                    "retest_date": live_match.retest_date, "retest_price": round(float(live_match.retest_price), 2) if live_match.retest_price else None,
                    "reaccum_bars": live_match.reaccum_bars,
                    "bos2_date": live_match.bos2_date, "bos2_price": round(float(live_match.bos2_price), 2) if live_match.bos2_price else None,
                    "confluence_score": f"{conf['score']}/{conf['max_score']}",
                    "notes": live_match.notes,
                })
        except Exception as e:
            print(f"  [!] {symbol}: live-signal check failed: {e}")

        for c in chains:
            outcome_counts[c.outcome] = outcome_counts.get(c.outcome, 0) + 1
            base_info = chain_base_info(c, df)
            all_chain_rows.append(base_info)

            if c.outcome == "BOS2_CONFIRMED":
                trade = _forward_trade(df, c.end_idx, c.retest_price, horizons)
                if trade:
                    row = dict(base_info)
                    row.update({"signal_date": base_info["bos2_date"], "signal_price": base_info["bos2_price"]})
                    row.update(trade)
                    all_trades_bos2.append(row)

            if c.pre_bos2_ready_idx is not None:
                trade = _forward_trade(df, c.pre_bos2_ready_idx, c.retest_price, horizons)
                if trade:
                    row = dict(base_info)
                    row.update({
                        "signal_date": base_info["pre_bos2_ready_date"],
                        "signal_price": round(float(df["Close"].values[c.pre_bos2_ready_idx]), 2),
                        "eventually_confirmed": c.outcome == "BOS2_CONFIRMED",
                    })

                    row.update(trade)
                    all_trades_pre.append(row)

    all_chains_df = pd.DataFrame(all_chain_rows)
    bos2_df = _reorder(pd.DataFrame(all_trades_bos2))
    pre_df = _reorder(pd.DataFrame(all_trades_pre))
    live_signals_df = pd.DataFrame(live_signals)
    if not live_signals_df.empty:
        stage_prio = {"FRESH_BOS2": 0, "PRE_BOS2_READY": 1}
        live_signals_df["_p"] = live_signals_df["stage"].map(stage_prio).fillna(9)
        live_signals_df = live_signals_df.sort_values("_p").drop(columns="_p").reset_index(drop=True)

    summary = _summarize(bos2_df, pre_df, outcome_counts, horizons)
    return {
        "all_chains": all_chains_df,
        "bos2_trades": bos2_df,
        "pre_bos2_trades": pre_df,
        "live_signals": live_signals_df,
        "outcome_counts": outcome_counts,
        "summary": summary,
    }



def _summarize(bos2_df, pre_df, outcome_counts, horizons) -> pd.DataFrame:
    rows = []
    total_resolved = sum(v for k, v in outcome_counts.items() if k != "STILL_OPEN")
    confirm_rate = outcome_counts.get("BOS2_CONFIRMED", 0) / total_resolved * 100 if total_resolved else float("nan")

    for label, tdf in (("BOS2_CONFIRMED entry", bos2_df), ("PRE_BOS2_READY entry", pre_df)):
        if tdf is None or tdf.empty:
            continue
        for h in horizons:
            col = f"ret_{h}d_pct"
            if col not in tdf.columns:
                continue
            vals = tdf[col].dropna()
            if vals.empty:
                continue
            win_rate = (vals > 0).mean() * 100
            rows.append({
                "entry_type": label, "horizon_days": h, "n_trades": len(vals),
                "win_rate_pct": round(win_rate, 1), "avg_return_pct": round(vals.mean(), 2),
                "median_return_pct": round(vals.median(), 2), "best_pct": round(vals.max(), 2),
                "worst_pct": round(vals.min(), 2),
            })
    summary = pd.DataFrame(rows)
    summary.attrs["pattern_completion_rate_pct"] = round(confirm_rate, 1)
    summary.attrs["outcome_counts"] = outcome_counts
    return summary


def render_markdown_report(result: dict, cfg) -> str:
    summary = result["summary"]
    counts = result["outcome_counts"]
    total_resolved = sum(v for k, v in counts.items() if k != "STILL_OPEN")
    completion_rate = counts.get("BOS2_CONFIRMED", 0) / total_resolved * 100 if total_resolved else float("nan")

    lines = ["# SMC Structure Scanner - Backtest Report", ""]
    lines.append(f"Generated: {pd.Timestamp.now().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append("## Pattern completion rate")
    lines.append("")
    lines.append(f"- Total resolved retest/re-accumulation chains: **{total_resolved}**")
    for k, v in counts.items():
        lines.append(f"  - {k}: {v}")
    lines.append(f"- **{completion_rate:.1f}%** of chains that reached re-accumulation went on to a confirmed BOS2 breakout.")
    lines.append("")
    lines.append("## Forward returns by entry type & horizon")
    lines.append("")
    if not summary.empty:
        lines.append(summary.to_markdown(index=False))
    else:
        lines.append("_No trades generated - widen the symbol universe or date range._")
    lines.append("")
    lines.append("## Notes / caveats")
    lines.append("- Entries assume next-bar Open after the signal; stop = the chain's retest low.")
    lines.append("- No slippage, brokerage, or position sizing modeled.")
    lines.append("- `PRE_BOS2_READY` entries include chains that *never* confirmed BOS2 (see "
                  "`eventually_confirmed` column in `backtest_pre_bos2_trades.csv`) - that's the real "
                  "cost of entering early, weigh it against the better average price.")
    lines.append("- `results/backtest_all_chains.csv` / the 'All Chains' Excel sheet lists EVERY pattern "
                  "instance found (including INVALIDATED/TIMEOUT/STILL_OPEN ones that never became a "
                  "trade) with its full P0/BOS1/P1/Retest/BOS2 date-and-price trail.")
    return "\n".join(lines)
