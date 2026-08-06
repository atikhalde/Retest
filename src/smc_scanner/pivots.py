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
    candle (using the same fractal pivot-low logic as the rest of the
    scanner, not just any 1-bar dip - that avoids flagging noisy 1-2 day
    wiggles as if they were meaningful pullbacks). A tactical, earlier entry
    style than waiting for a full resistance breakout - buying confirmation
    that the latest real dip has reversed, right within the base.

    Returns a list of (idx, date, price) tuples in chronological order, one
    per confirmed pivot low that got reversed within the window.
    """
    if end_idx is None or end_idx <= start_idx:
        return []
    _, pl = find_pivots(df, left, right)
    n = len(df)
    pivot_low_idxs = [i for i in range(start_idx, min(end_idx, n - 1) + 1) if pl.iloc[i]]

    opens = df["Open"].values
    highs = df["High"].values
    closes = df["Close"].values

    reversals = []
    for p_idx in pivot_low_idxs:
        p_high = highs[p_idx]
        for i in range(p_idx + 1, end_idx + 1):
            if closes[i] > opens[i] and closes[i] > p_high:
                reversals.append((i, df.index[i], round(float(closes[i]), 2)))
                break

    return reversals


