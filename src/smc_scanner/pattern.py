"""
Core structural pattern detector.

    Base(P0) -> Impulse/BOS1 -> Retest -> Re-accumulation -> BOS2(P1) -> Markup

Produces a PatternMatch with a `stage` field that a scanner/alerting layer
can act on:

    IN_RETEST        - just bounced off the retest zone, too early to call basing
    BASING           - re-accumulating, but not yet close to the breakout trigger
    FRESH_REVERSAL   - a higher-low reversal just confirmed (green candle closing
                       above the last confirmed swing-low candle's high) within
                       `recency_bars` - the tactical, earlier entry style (e.g.
                       PGIL on 27 Jul, AUBANK on 24 Jul) rather than waiting for
                       the full P1 breakout.
    PRE_BOS2_READY   - re-accumulation minimum satisfied AND price is coiled
                       within `pre_bos2_proximity_pct` of P1 (the level BOS2 must
                       clear). This is the "catch it before it breaks" stage.
    FRESH_BOS2       - BOS2 fired within `recency_bars` -> actionable now
    STALE_BOS2       - BOS2 fired too long ago to be a fresh trade idea
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from .pivots import find_reaccum_reversals
from .weekly import find_daily_bos1_candidates, bos1_weekly_confirmation




@dataclass
class PatternMatch:
    symbol: str
    stage: str
    p0_date: Optional[pd.Timestamp] = None
    p0_price: float = np.nan
    bos1_date: Optional[pd.Timestamp] = None
    bos1_price: float = np.nan
    p1_date: Optional[pd.Timestamp] = None
    p1_price: float = np.nan
    retest_date: Optional[pd.Timestamp] = None
    retest_price: float = np.nan
    reaccum_bars: int = 0
    reversal_date: Optional[pd.Timestamp] = None
    reversal_price: float = np.nan
    num_reversals: int = 0
    volatility_contracted: bool = False
    atr_contraction_ratio: float = np.nan
    distance_to_p1_pct: float = np.nan
    bos2_date: Optional[pd.Timestamp] = None
    bos2_price: float = np.nan
    bars_since_bos2: Optional[int] = None
    last_close: float = np.nan
    last_date: Optional[pd.Timestamp] = None
    notes: str = ""
    # Weekly confirmation of the ORIGINAL BOS1 breakout (weekly EMA20>EMA50,
    # MACD histogram>0, volume>10w SMA) - scoring input only, see
    # weekly.bos1_weekly_confirmation for why this isn't a detection gate.
    bos1_weekly_raw: Optional[int] = None
    bos1_weekly_max: int = 3


def detect_pattern(df: pd.DataFrame, cfg, symbol: str) -> Optional[PatternMatch]:
    full_df = df  # keep full history available for the weekly BOS1 gate
    bos1_candidates_full = find_daily_bos1_candidates(full_df, cfg)

    df = df.tail(cfg.lookback_bars + cfg.pivot_right + 5).copy()
    if len(df) < 40:
        return None

    offset = len(full_df) - len(df)
    bos1_candidates = [
        (idx - offset, p0_price, p0_date)
        for idx, p0_price, p0_date in bos1_candidates_full
        if 0 <= idx - offset < len(df)
    ]
    n = len(df)

    close = df["Close"].values
    high = df["High"].values
    low = df["Low"].values
    vol = df["Volume"].values
    vol_sma20 = df["VOL_SMA20"].values if "VOL_SMA20" in df.columns else np.full(n, np.nan)
    atr_arr = df["ATR"].values if "ATR" in df.columns else np.full(n, np.nan)
    dates = df.index

    best_match = None

    for bos1_idx, p0_price, p0_date in bos1_candidates:
        # ---- P1 = running high after BOS1 until a real pullback starts ----
        run_max_idx = bos1_idx
        run_max = high[bos1_idx]

        p1_idx = None
        k = bos1_idx + 1
        while k < n:
            if high[k] > run_max:
                run_max = high[k]
                run_max_idx = k
            if close[k] < run_max * 0.97:
                p1_idx = run_max_idx
                break
            k += 1
        if p1_idx is None:
            continue
        p1_price = high[p1_idx]
        p1_date = dates[p1_idx]

        # impulse-leg ATR (volatility during the initial thrust) - baseline for contraction check
        impulse_atr = np.nanmean(atr_arr[bos1_idx:p1_idx + 1]) if p1_idx > bos1_idx else atr_arr[bos1_idx]

        # ---- retest: local minimum after p1_idx that lands near P0 ----
        retest_idx = None
        invalidated = False
        m = p1_idx + 1
        running_min = np.inf
        running_min_idx = None
        while m < n:
            if low[m] < running_min:
                running_min = low[m]
                running_min_idx = m
            if close[m] < p0_price * (1 - cfg.max_undercut_pct):
                invalidated = True
                break
            zone_lo = p0_price * (1 - cfg.retest_zone_pct)
            zone_hi = p0_price * (1 + cfg.retest_zone_pct)
            if running_min_idx is not None and zone_lo <= running_min <= zone_hi:
                if close[m] > running_min * 1.02:
                    retest_idx = running_min_idx
                    break
            m += 1
        if invalidated or retest_idx is None:
            continue
        retest_price = low[retest_idx]
        retest_date = dates[retest_idx]

        # ---- re-accumulation -> BOS2 (or PRE_BOS2_READY / BASING if not fired yet) ----
        bos2_idx = None
        earliest_bos2 = retest_idx + cfg.min_reaccum_bars
        latest_bos2 = retest_idx + cfg.max_reaccum_bars
        reaccum_broken = False
        for r in range(retest_idx + 1, min(latest_bos2, n)):
            if close[r] < p0_price * (1 - cfg.max_undercut_pct):
                reaccum_broken = True
                break
            if r >= earliest_bos2:
                vsma = vol_sma20[r] if not np.isnan(vol_sma20[r]) else np.inf
                if close[r] > p1_price * (1 + cfg.breakout_buffer) and vol[r] >= cfg.vol_mult_bos2 * vsma:
                    bos2_idx = r
                    break
        if reaccum_broken:
            continue

        last_idx = n - 1
        reaccum_atr = np.nanmean(atr_arr[retest_idx:min(last_idx, latest_bos2) + 1])
        atr_ratio = (reaccum_atr / impulse_atr) if impulse_atr and not np.isnan(impulse_atr) and impulse_atr > 0 else np.nan
        vol_contracted = bool(atr_ratio <= cfg.pre_bos2_max_atr_ratio) if not np.isnan(atr_ratio) else False

        reaccum_end_for_reversal = bos2_idx if bos2_idx is not None else last_idx
        reversals = find_reaccum_reversals(df, retest_idx, reaccum_end_for_reversal, cfg.pivot_left, cfg.pivot_right)
        last_reversal = reversals[-1] if reversals else (None, None, None)
        num_reversals = len(reversals)

        if bos2_idx is not None:
            bars_since = last_idx - bos2_idx
            stage = "FRESH_BOS2" if bars_since <= cfg.recency_bars else "STALE_BOS2"
            match = PatternMatch(
                symbol=symbol, stage=stage,
                p0_date=p0_date, p0_price=p0_price,
                bos1_date=dates[bos1_idx], bos1_price=close[bos1_idx],
                p1_date=p1_date, p1_price=p1_price,
                retest_date=retest_date, retest_price=retest_price,
                reaccum_bars=bos2_idx - retest_idx,
                volatility_contracted=vol_contracted, atr_contraction_ratio=atr_ratio,
                distance_to_p1_pct=0.0,
                bos2_date=dates[bos2_idx], bos2_price=close[bos2_idx],
                bars_since_bos2=bars_since,
                reversal_date=last_reversal[1], reversal_price=last_reversal[2], num_reversals=num_reversals,
                last_close=close[last_idx], last_date=dates[last_idx],
                notes="Continuation breakout confirmed" if stage == "FRESH_BOS2"
                      else "Breakout already played out (beyond recency window)",
            )
        else:
            bars_in_reaccum = last_idx - retest_idx
            dist_to_p1 = (p1_price - close[last_idx]) / p1_price
            bars_since_reversal = (last_idx - last_reversal[0]) if last_reversal[0] is not None else None
            if bars_in_reaccum < cfg.min_reaccum_bars:
                stage = "IN_RETEST"
                notes = "Just bounced off the retest zone; too early to call re-accumulation"
            elif bars_since_reversal is not None and bars_since_reversal <= cfg.recency_bars:
                stage = "FRESH_REVERSAL"
                notes = (f"Higher-low reversal confirmed {bars_since_reversal}d ago at {last_reversal[2]:.2f} "
                         f"(green close above the last confirmed swing-low candle's high). "
                         f"Tactical early entry, {dist_to_p1*100:.1f}% below P1={p1_price:.2f}.")
            elif dist_to_p1 <= cfg.pre_bos2_proximity_pct and close[last_idx] < p1_price * (1 + cfg.breakout_buffer):
                stage = "PRE_BOS2_READY"
                squeeze_txt = "volatility contracted (coiled)" if vol_contracted else "range not yet contracted"
                notes = (f"Re-accumulation complete ({bars_in_reaccum}d), price {dist_to_p1*100:.1f}% "
                         f"under P1={p1_price:.2f}; {squeeze_txt}. Watch for breakout w/ volume.")
            else:
                stage = "BASING"
                notes = f"Re-accumulating {bars_in_reaccum}d, still {dist_to_p1*100:.1f}% below P1={p1_price:.2f}"


            match = PatternMatch(
                symbol=symbol, stage=stage,
                p0_date=p0_date, p0_price=p0_price,
                bos1_date=dates[bos1_idx], bos1_price=close[bos1_idx],
                p1_date=p1_date, p1_price=p1_price,
                retest_date=retest_date, retest_price=retest_price,
                reaccum_bars=bars_in_reaccum,
                reversal_date=last_reversal[1], reversal_price=last_reversal[2], num_reversals=num_reversals,
                volatility_contracted=vol_contracted, atr_contraction_ratio=atr_ratio,
                distance_to_p1_pct=dist_to_p1,
                last_close=close[last_idx], last_date=dates[last_idx],
                notes=notes,
            )

        if best_match is None or (
            match.bos1_date is not None
            and (best_match.bos1_date is None or match.bos1_date > best_match.bos1_date)
        ):
            best_match = match

    if best_match is not None and best_match.bos1_date is not None:
        conf = bos1_weekly_confirmation(full_df, best_match.bos1_date, cfg)
        best_match.bos1_weekly_raw = conf["raw"]
        best_match.bos1_weekly_max = conf["max"]

    return best_match
