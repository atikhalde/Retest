"""
Trade plan generator: turns a pattern match into concrete, actionable
numbers - entry date/price, stop loss, target, and an exit-by window -
using the findings from the historical backtest & stop-loss sweep:

  - Stop loss = the chain's retest low (the "structural" stop) - the sweep
    in scripts/optimize_stop_loss.py showed this beats fixed-% and
    ATR-multiple stops at every point in the 4-7 day holding window.
  - Target = entry +/- `target_reward_risk` x the stop distance (default
    1.0, i.e. a 1:1 reward:risk target) - backtested average risk (~3.33%)
    and average winning-trade return (~3.39%) over a 5-7 day hold are
    almost exactly 1:1, so this is empirically grounded, not arbitrary.
  - Holding period = 4-7 trading days (win rate peaks at day 4 ~67.5%,
    average return peaks at day 7 ~1.48%; edge decays steadily beyond
    day ~10-15). Exit-by dates use the real NSE trading calendar
    (data/nse_holidays.txt + weekends), not just calendar days.

This is only computed for actionable stages (FRESH_REVERSAL, FRESH_BOS2) -
for BASING/IN_RETEST/PRE_BOS2_READY there's no confirmed entry yet.
"""
import os
from datetime import timedelta

import pandas as pd

ACTIONABLE_STAGES = {"FRESH_REVERSAL", "FRESH_BOS2"}

_HOLIDAY_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "nse_holidays.txt")


def _load_holidays():
    try:
        with open(_HOLIDAY_FILE) as f:
            return {pd.Timestamp(line.strip()) for line in f if line.strip()}
    except FileNotFoundError:
        return set()


_HOLIDAYS = None


def _holidays():
    global _HOLIDAYS
    if _HOLIDAYS is None:
        _HOLIDAYS = _load_holidays()
    return _HOLIDAYS


def _next_trading_day(date: pd.Timestamp) -> pd.Timestamp:
    d = pd.Timestamp(date) + timedelta(days=1)
    holidays = _holidays()
    while d.weekday() >= 5 or d in holidays:
        d += timedelta(days=1)
    return d


def _add_trading_days(date: pd.Timestamp, n: int) -> pd.Timestamp:
    d = pd.Timestamp(date)
    holidays = _holidays()
    added = 0
    while added < n:
        d += timedelta(days=1)
        if d.weekday() < 5 and d not in holidays:
            added += 1
    return d


def compute_trade_plan(stage, last_close, last_date, retest_price, cfg) -> dict:
    """
    Returns None if the stage isn't actionable. Otherwise a dict with:
        entry_date, entry_price_ref, stop_loss, risk_pct,
        target_price, target_pct, reward_risk,
        exit_by_min_date, exit_by_max_date, holding_period_note
    """
    if stage not in ACTIONABLE_STAGES:
        return None
    if last_close is None or retest_price is None or pd.isna(last_close) or pd.isna(retest_price):
        return None
    if retest_price >= last_close:
        return None  # degenerate - stop should be below entry

    rr = getattr(cfg, "target_reward_risk", 1.0)
    entry_price_ref = float(last_close)
    stop_loss = float(retest_price)
    risk_pct = round((entry_price_ref - stop_loss) / entry_price_ref * 100, 2)
    target_price = round(entry_price_ref + rr * (entry_price_ref - stop_loss), 2)
    target_pct = round(risk_pct * rr, 2)

    entry_date = _next_trading_day(last_date)
    exit_by_min = _add_trading_days(entry_date, 4)
    exit_by_max = _add_trading_days(entry_date, 7)

    return {
        "entry_date": entry_date.date().isoformat(),
        "entry_price_ref": round(entry_price_ref, 2),
        "stop_loss": round(stop_loss, 2),
        "risk_pct": risk_pct,
        "target_price": target_price,
        "target_pct": target_pct,
        "reward_risk": rr,
        "exit_by_min_date": exit_by_min.date().isoformat(),
        "exit_by_max_date": exit_by_max.date().isoformat(),
        "holding_period_note": "Hold 4-7 trading days (best win rate day 4, best avg return day 7); exit by then regardless of target.",
    }
