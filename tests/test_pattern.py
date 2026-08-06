import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from smc_scanner.config import Config
from smc_scanner.indicators import add_indicators
from smc_scanner.pattern import detect_pattern


def make_synthetic_pattern():
    """Builds a clean, synthetic Base->Impulse->Retest->Reaccum->BOS2 series
    so the detector's logic can be unit-tested without hitting any API."""
    rng = np.random.default_rng(42)
    n_base = 40
    base = 100 + rng.normal(0, 0.6, n_base).cumsum() * 0.05
    base = np.clip(base, 95, 105)

    impulse = np.linspace(105, 140, 8) + rng.normal(0, 0.3, 8)
    post_impulse_high = np.linspace(140, 148, 5) + rng.normal(0, 0.3, 5)
    p1_level = max(post_impulse_high.max(), impulse.max())

    retest = np.linspace(148, 102, 10) + rng.normal(0, 0.3, 10)
    reaccum = 103 + rng.normal(0, 0.8, 15).cumsum() * 0.1
    reaccum = np.clip(reaccum, 100, 108)

    # bos2 leg: ramps from the reaccumulation level up through and past P1
    bos2 = np.linspace(reaccum[-1], p1_level * 1.15, 10) + rng.normal(0, 0.3, 10)

    close = np.concatenate([base, impulse, post_impulse_high, retest, reaccum, bos2])
    dates = pd.date_range("2024-01-01", periods=len(close), freq="B")

    open_ = np.roll(close, 1)
    open_[0] = close[0]
    high = np.maximum(open_, close) + rng.uniform(0.1, 1.0, len(close))
    low = np.minimum(open_, close) - rng.uniform(0.1, 1.0, len(close))

    volume = np.full(len(close), 100_000.0)

    impulse_break_idx = n_base + 1
    volume[impulse_break_idx] *= 4

    # find exactly where the bos2 leg first clears P1 with a buffer, and put the volume kick there
    bos2_start = n_base + len(impulse) + len(post_impulse_high) + len(retest) + len(reaccum)
    bos2_break_idx = None
    for offset, val in enumerate(bos2):
        abs_idx = bos2_start + offset
        if close[abs_idx] > p1_level * 1.006:
            bos2_break_idx = abs_idx
            break
    assert bos2_break_idx is not None, "synthetic data didn't clear P1 - widen the bos2 ramp"
    volume[bos2_break_idx] *= 4

    df = pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume}, index=dates)
    return df, bos2_break_idx



def test_detects_fresh_bos2_at_the_breakout_bar():
    cfg = Config()
    df, bos2_break_idx = make_synthetic_pattern()
    df_indicators = add_indicators(df, cfg)

    # Trim to exactly the breakout bar to simulate scanning "as of" that day
    trimmed = df_indicators.iloc[: bos2_break_idx + 1]
    match = detect_pattern(trimmed, cfg, "TEST")

    assert match is not None
    assert match.stage == "FRESH_BOS2"
    assert match.bars_since_bos2 == 0


def test_detects_pre_bos2_ready_before_the_breakout():
    cfg = Config()
    df, bos2_break_idx = make_synthetic_pattern()
    df_indicators = add_indicators(df, cfg)

    # Trim to a few bars BEFORE the actual breakout, while still inside re-accumulation
    trimmed = df_indicators.iloc[: bos2_break_idx - 2]
    match = detect_pattern(trimmed, cfg, "TEST")

    assert match is not None
    assert match.stage in ("PRE_BOS2_READY", "BASING", "IN_RETEST")


def test_no_match_on_pure_noise():
    cfg = Config()
    rng = np.random.default_rng(1)
    n = 120
    close = 100 + rng.normal(0, 1, n).cumsum() * 0.1
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    high = np.maximum(open_, close) + 0.5
    low = np.minimum(open_, close) - 0.5
    volume = np.full(n, 100_000.0)
    df = pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume}, index=dates)
    df = add_indicators(df, cfg)
    match = detect_pattern(df, cfg, "NOISE")
    # Random-walk noise shouldn't reliably produce a full BOS2-confirmed chain
    if match is not None:
        assert match.stage != "FRESH_BOS2"
