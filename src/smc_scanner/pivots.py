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
