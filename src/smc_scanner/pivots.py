"""Fractal swing-pivot detection."""
import numpy as np
import pandas as pd


def find_pivots(df: pd.DataFrame, left: int, right: int):
    """Return (pivot_high, pivot_low) boolean Series, confirmed with a `right`-bar lag."""
    highs = df["High"].values
    lows = df["Low"].values
    n = len(df)
    ph = np.zeros(n, dtype=bool)
    pl = np.zeros(n, dtype=bool)
    for i in range(left, n - right):
        h_window = highs[i - left: i + right + 1]
        l_window = lows[i - left: i + right + 1]
        if highs[i] == h_window.max() and np.argmax(h_window) == left:
            ph[i] = True
        if lows[i] == l_window.min() and np.argmin(l_window) == left:
            pl[i] = True
    return pd.Series(ph, index=df.index), pd.Series(pl, index=df.index)


def find_reaccum_reversals(df: pd.DataFrame, start_idx: int, end_idx: int, left: int = 3, right: int = 3):
    """
    Within [start_idx, end_idx], find every "higher-low reversal" signal: a
    GREEN candle that closes back above the HIGH of a confirmed swing-low
    candle (fractal pivot-low logic, not just any 1-bar dip - that avoids
    flagging noisy 1-2 day wiggles as if they were meaningful pullbacks).

    A pivot low dipping BELOW an earlier pivot/retest low is fine on its own
    - that's a normal, often bullish "spring" (a stop-hunt shakeout before
    the real move - e.g. PGIL dipping to 1901 on 8 Jul then 1921 on 23 Jul,
    both below the 1971 retest; AUBank dipping to 960 on 23 Jul, below the
    1033 pivot from 8 Jul). Both reverse cleanly and are genuine signals.

    BUT: the reversal is only accepted if the swing HIGHS since the retest
    show evidence the uptrend is still alive - i.e. at least one confirmed
    pivot high has matched or exceeded the pivot high before it. If every
    single swing high since the retest has been progressively LOWER than
    the last, with no exception, that's not re-accumulation - it's a
    downtrend (e.g. CUMMINSIND's swing highs 8908->5740->5714->5658
    monotonically declining, 31 Jul reversal rejected). Contrast AUBank
    (1025->1056->1079->1090, rising) or PGIL (2108->2073->2144, ends on a
    fresh high) - both pass and keep their reversals.

    Returns a list of (idx, date, price) tuples in chronological order, one
    per confirmed pivot low that got reversed within the window.
    """
    if end_idx is None or end_idx <= start_idx:
        return []
    ph, pl = find_pivots(df, left, right)
    n = len(df)
    pivot_low_idxs = [i for i in range(start_idx, min(end_idx, n - 1) + 1) if pl.iloc[i]]
    pivot_high_points = [(i, df["High"].values[i]) for i in range(start_idx, min(end_idx, n - 1) + 1) if ph.iloc[i]]

    opens = df["Open"].values
    highs = df["High"].values
    closes = df["Close"].values

    def uptrend_still_alive(as_of_idx) -> bool:
        highs_before = [h for (i, h) in pivot_high_points if i <= as_of_idx]
        if len(highs_before) < 2:
            return True  # not enough swing highs yet to call it a downtrend
        return any(highs_before[k] >= highs_before[k - 1] for k in range(1, len(highs_before)))

    reversals = []
    for p_idx in pivot_low_idxs:
        if not uptrend_still_alive(p_idx):
            continue
        p_high = highs[p_idx]
        for i in range(p_idx + 1, end_idx + 1):
            if closes[i] > opens[i] and closes[i] > p_high:
                reversals.append((i, df.index[i], round(float(closes[i]), 2)))
                break

    return reversals






