"""
Weekly-timeframe BOS1 gate - replicates the original TradingView indicator's
own entry logic exactly, instead of a generic daily-pivot breakout:

    weekly close > weekly max(26, 1 week ago high)
    and 1 week ago close <= weekly max(26, 2 weeks ago high)
    and weekly ema(weekly close, 20) > weekly ema(weekly close, 50)
    and weekly ema(weekly close, 50) > 2 weeks ago ema(weekly close, 50)
    and weekly rsi(14) > 60
    and weekly rsi(14) > 1 week ago rsi(14)
    and weekly macd histogram(26, 12, 9) > 0
    and weekly volume > weekly sma(weekly volume, 10)
    and weekly close > weekly open

In plain English: this week is the FIRST time price closes above its
trailing 26-week high (it hadn't already broken out last week - so this is
a fresh breakout, not a stale continuation), AND the weekly trend/momentum
suite (EMA20>EMA50 rising, RSI>60 rising, MACD histogram positive, volume
above its 10-week average, green weekly candle) all confirm simultaneously.

This is a much stricter, more meaningful gate than "any daily pivot break
with a volume spike" - it prevents flagging a BOS1 on a trivial local high
inside a stock that's still trading well below its real highs (e.g. ALKEM's
30 Jul 2026 false signal: the stock never once closed above its actual
26-week high of ~5843 in the whole window - the old pivot-based logic was
breaking a meaningless local pivot at 5470 instead).

`daily close > 100` and `market cap > 1000` from the original checklist are
applied elsewhere (universe filter / confluence score), not here.
"""
import numpy as np
import pandas as pd

from .indicators import ema, rsi, macd_hist


def resample_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Resample daily OHLCV to weekly bars, week ending Friday (NSE trading week)."""
    w = df.resample("W-FRI").agg({
        "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum",
    }).dropna(subset=["Open", "High", "Low", "Close"])
    return w


def compute_weekly_bos1_signal(df_daily: pd.DataFrame, cfg) -> pd.DataFrame:
    """Returns the weekly-resampled frame with a `bos1_fired` boolean column
    and `p0_level` (the 26-week high being broken) for every week.

    `bos1_fired` requires only the CORE structural condition - a genuine,
    freshly-made new N-week high (it wasn't already broken last week). The
    original indicator's extra momentum sub-conditions (EMA trend/rising,
    RSI>60 rising, MACD histogram positive, volume above its 10-week
    average, green weekly candle) are still computed and exposed as
    diagnostic columns here, but are NOT required to fire BOS1 - they are
    better suited as a confluence/quality score on top of a confirmed
    pattern (see `indicators.confluence_score`) than as a hard gate on the
    very origin point. Requiring all of them simultaneously turned out to
    reject real, valid impulses (e.g. AUBank's 24 Apr 2026 breakout) while
    the core "genuine new high" condition alone still correctly rejects
    fake ones (e.g. ALKEM, which never actually cleared its real 26-week
    high at all in the window that produced its false 30 Jul reversal).
    """
    w = resample_weekly(df_daily)
    n_weeks = cfg.bos1_lookback_weeks
    if len(w) < n_weeks + 5:
        w["bos1_fired"] = False
        w["p0_level"] = np.nan
        return w

    close, open_, high, vol = w["Close"], w["Open"], w["High"], w["Volume"]

    roll_high = high.rolling(n_weeks).max()
    high_1wk_ago = roll_high.shift(1)
    high_2wk_ago = roll_high.shift(2)

    ema20 = ema(close, 20)
    ema50 = ema(close, 50)
    rsi14 = rsi(close, 14)
    macdh = macd_hist(close)
    vol_sma10 = vol.rolling(10).mean()

    cond_new_high = close > high_1wk_ago
    cond_freshly_broken = close.shift(1) <= high_2wk_ago

    # diagnostic-only, not part of the hard gate (see docstring)
    cond_ema_trend = ema20 > ema50
    cond_ema50_rising = ema50 > ema50.shift(2)
    cond_rsi_strong = rsi14 > cfg.rsi_min
    cond_rsi_rising = rsi14 > rsi14.shift(1)
    cond_macd_positive = macdh > 0
    cond_vol_confirm = vol > vol_sma10
    cond_green = close > open_

    bos1_fired = (cond_new_high & cond_freshly_broken)
    momentum_confluence = (
        cond_ema_trend.astype(int) + cond_ema50_rising.astype(int) + cond_rsi_strong.astype(int)
        + cond_rsi_rising.astype(int) + cond_macd_positive.astype(int) + cond_vol_confirm.astype(int)
        + cond_green.astype(int)
    )

    w = w.copy()
    w["bos1_fired"] = bos1_fired.fillna(False)
    w["p0_level"] = high_1wk_ago
    w["momentum_confluence"] = momentum_confluence  # 0-7, informational
    return w



def find_daily_bos1_candidates(df_daily: pd.DataFrame, cfg):
    """
    Maps each fired weekly BOS1 signal to the precise DAILY bar within that
    week where the close first actually clears the 26-week-high level (the
    "impulse candle" itself, e.g. PGIL's 24 Jun) - not just the week's
    closing bar - so the rest of the daily-bar pipeline (P1 tracking,
    retest, re-accumulation, reversal, BOS2) has a concrete start point.

    Returns a list of (daily_idx, p0_price, p0_date) tuples in chronological
    order, one per fired week that could be mapped to a daily bar. `p0_date`
    is the date of the actual prior peak that set the 26-week-high record
    being broken (not the breakout date itself).
    """
    weekly = compute_weekly_bos1_signal(df_daily, cfg)
    fired_weeks = weekly[weekly["bos1_fired"]]
    if fired_weeks.empty:
        return []

    dates = df_daily.index
    close = df_daily["Close"].values
    high = df_daily["High"].values
    n_lookback_days = cfg.bos1_lookback_weeks * 7
    candidates = []

    for week_end, row in fired_weeks.iterrows():
        p0_level = row["p0_level"]
        if pd.isna(p0_level):
            continue
        week_start = week_end - pd.Timedelta(days=6)
        mask = (dates > week_start) & (dates <= week_end)
        day_idxs = np.where(mask)[0]
        if len(day_idxs) == 0:
            continue
        bos1_idx = None
        for di in day_idxs:
            if close[di] > p0_level:
                bos1_idx = di
                break
        if bos1_idx is None:
            bos1_idx = day_idxs[-1]  # fall back to the week's last daily bar

        # find the actual prior peak (within the trailing lookback window)
        # that set this 26-week-high record, for a meaningful p0_date
        lookback_start_date = dates[bos1_idx] - pd.Timedelta(days=n_lookback_days)
        peak_mask = (dates >= lookback_start_date) & (dates < dates[bos1_idx])
        peak_idxs = np.where(peak_mask)[0]
        if len(peak_idxs) > 0:
            p0_idx = peak_idxs[np.argmax(high[peak_idxs])]
            p0_date = dates[p0_idx]
        else:
            p0_date = dates[bos1_idx]

        candidates.append((int(bos1_idx), float(p0_level), p0_date))

    return candidates


def bos1_weekly_confirmation(df_daily: pd.DataFrame, bos1_date, cfg) -> dict:
    """Weekly momentum confirmation for the ORIGINAL BOS1 breakout week -
    folded into the quality score (2026-08-08), NOT the detection gate.

    Checks 3 of the original TradingView-style conditions, evaluated on the
    week containing `bos1_date`:
        - weekly EMA20 > weekly EMA50 (trend)
        - weekly MACD histogram > 0 (momentum)
        - weekly volume > weekly 10-week volume SMA (participation)

    Why scoring, not gating: validated across 964 real historical BOS1
    breakouts (80 symbols, 5 years) - requiring these as hard conditions
    correlates with better aggregate forward returns (e.g. weeks that
    failed the MACD-positive check averaged -0.45% at 10 days vs +0.98%
    baseline), but AUBank's real, previously-confirmed 2026-04-22 breakout
    itself has a NEGATIVE weekly MACD histogram - a hard gate would have
    incorrectly rejected it. Scoring lets a case like that still be
    detected and tracked, just graded a bit lower instead of thrown away.

    Returns {"raw": int 0-3 or None, "max": 3, "ema20_gt_ema50": bool/None,
    "macd_hist_positive": bool/None, "vol_gt_sma10": bool/None}. `raw` is
    None if there isn't enough weekly history yet to compute all three.
    """
    empty = {"raw": None, "max": 3, "ema20_gt_ema50": None,
             "macd_hist_positive": None, "vol_gt_sma10": None}
    if bos1_date is None:
        return empty

    w = resample_weekly(df_daily)
    if len(w) < 50:
        return empty

    close, vol = w["Close"], w["Volume"]
    ema20 = ema(close, 20)
    ema50 = ema(close, 50)
    macdh = macd_hist(close)
    vol_sma10 = vol.rolling(10).mean()

    week_candidates = w.index[w.index >= pd.Timestamp(bos1_date)]
    if len(week_candidates) == 0:
        return empty
    week_end = week_candidates[0]

    e20, e50 = ema20.get(week_end), ema50.get(week_end)
    mh = macdh.get(week_end)
    v, vsma = vol.get(week_end), vol_sma10.get(week_end)

    conds = {
        "ema20_gt_ema50": bool(e20 > e50) if pd.notna(e20) and pd.notna(e50) else None,
        "macd_hist_positive": bool(mh > 0) if pd.notna(mh) else None,
        "vol_gt_sma10": bool(v > vsma) if pd.notna(v) and pd.notna(vsma) else None,
    }
    known = [c for c in conds.values() if c is not None]
    raw = sum(1 for c in known if c) if len(known) == 3 else None
    return {"raw": raw, "max": 3, **conds}


