"""Scan orchestration: universe -> data -> indicators -> pattern -> alerts."""
import concurrent.futures as cf
import json
import os
from datetime import datetime

import pandas as pd

from .indicators import add_indicators, confluence_score
from .pattern import detect_pattern
from .notify import send_telegram, format_alert
from .scoring import compute_quality_score
from .trade_plan import compute_trade_plan


STAGE_PRIORITY = {
    "FRESH_BOS2": 0,
    "FRESH_REVERSAL": 1,
    "PRE_BOS2_READY": 2,
    "BASING": 3,
    "IN_RETEST": 4,
    "STALE_BOS2": 5,
}

# Stages that still get computed and written to the scan CSV/report. Only
# FRESH_REVERSAL and PRE_BOS2_READY are ever alerted on Telegram (see
# _is_alert_worthy) - FRESH_BOS2 stays "visible in the report, silent on
# Telegram" per explicit user direction (2026-08-07/08): too many low-signal
# pings once the universe grew from 5 -> 643 symbols, most of them 1-5 trading
# days stale (recency_bars=5 window) rather than same-day events.
#
# "Fresh" means something different per stage since only FRESH_REVERSAL is a
# discrete one-bar event:
#   - FRESH_REVERSAL: the reversal bar IS today's/this session's bar
#     (Reversal_date == last_date), not up to recency_bars days old.
#   - PRE_BOS2_READY: this is a persisting coiled-state (can stay true for
#     many days while a stock sits under resistance), so "fresh" means the
#     symbol just TRANSITIONED into it this run (previous tracked stage in
#     state.json wasn't already PRE_BOS2_READY) - alert once on entry, not
#     once per day it continues to sit there.
# Both additionally require quality_grade A or B (score >= 65).
ALERTABLE_STAGES = {"FRESH_REVERSAL", "PRE_BOS2_READY"}

ALERT_QUALITY_GRADES = ("A", "B")  # first letter of quality_grade, e.g. "B - Good Setup"


def scan_symbol(row, data_source, cfg) -> dict:
    symbol = row["symbol"]
    security_id = row.get("security_id")
    exchange_segment = row.get("exchange_segment", "NSE_EQ")
    instrument = row.get("instrument", "EQUITY")
    try:
        df = data_source.fetch_ohlc(symbol, security_id=security_id, exchange_segment=exchange_segment,
                                     instrument=instrument) if hasattr(data_source, "fetch_ohlc") else None
    except TypeError:
        df = data_source.fetch_ohlc(symbol, security_id=security_id, exchange_segment=exchange_segment)
    except Exception as e:
        print(f"  [!] {symbol}: fetch error {e}")
        return None

    if df is None or df.empty or len(df) < 60:
        return None

    df = add_indicators(df, cfg)
    match = detect_pattern(df, cfg, symbol)
    if match is None:
        return None

    conf = confluence_score(df, cfg)
    quality = compute_quality_score(
        stage=match.stage,
        confluence_raw=conf["score"], confluence_max=conf["max_score"],
        num_reversals=match.num_reversals,
        volatility_contracted=match.volatility_contracted if not pd.isna(match.volatility_contracted) else None,
        reaccum_bars=match.reaccum_bars,
    )
    # entry/stop/target reference to whichever level is the actual trigger:
    # the reversal price for FRESH_REVERSAL, else last_close for FRESH_BOS2
    trigger_price = match.reversal_price if match.stage == "FRESH_REVERSAL" and not pd.isna(match.reversal_price) else match.last_close
    plan = compute_trade_plan(match.stage, trigger_price, match.last_date, match.retest_price, cfg)

    def d(x):

        return x.date().isoformat() if x is not None and hasattr(x, "date") else None

    return {
        "symbol": symbol,
        "stage": match.stage,
        "quality_score": quality["quality_score"],
        "quality_grade": quality["quality_grade"],
        "last_close": round(float(match.last_close), 2),
        "last_date": d(match.last_date),
        "P0_base_level": round(float(match.p0_price), 2) if match.p0_price else None,
        "BOS1_date": d(match.bos1_date),
        "BOS1_price": round(float(match.bos1_price), 2) if match.bos1_price else None,
        "P1_resistance": round(float(match.p1_price), 2) if match.p1_price else None,
        "Retest_date": d(match.retest_date),
        "Retest_price": round(float(match.retest_price), 2) if match.retest_price else None,
        "Reaccum_bars": match.reaccum_bars,
        "Reversal_date": d(match.reversal_date),
        "Reversal_price": round(float(match.reversal_price), 2) if match.reversal_price and not pd.isna(match.reversal_price) else None,
        "num_reversals": match.num_reversals,
        "volatility_contracted": match.volatility_contracted,
        "atr_contraction_ratio": round(float(match.atr_contraction_ratio), 2) if not pd.isna(match.atr_contraction_ratio) else None,
        "distance_to_p1_pct": round(float(match.distance_to_p1_pct) * 100, 2) if not pd.isna(match.distance_to_p1_pct) else None,
        "BOS2_date": d(match.bos2_date),
        "BOS2_price": round(float(match.bos2_price), 2) if match.bos2_price else None,
        "bars_since_bos2": match.bars_since_bos2,
        "confluence_score": f"{conf['score']}/{conf['max_score']}",
        "confluence_raw": conf["score"],
        "entry_date": plan["entry_date"] if plan else None,
        "entry_price_ref": plan["entry_price_ref"] if plan else None,
        "stop_loss": plan["stop_loss"] if plan else None,
        "risk_pct": plan["risk_pct"] if plan else None,
        "target_price": plan["target_price"] if plan else None,
        "target_pct": plan["target_pct"] if plan else None,
        "reward_risk": plan["reward_risk"] if plan else None,
        "exit_by_min_date": plan["exit_by_min_date"] if plan else None,
        "exit_by_max_date": plan["exit_by_max_date"] if plan else None,
        "notes": match.notes,
    }




def _load_state(cfg) -> dict:
    if os.path.exists(cfg.state_file):
        with open(cfg.state_file) as f:
            return json.load(f)
    return {}


def _save_state(cfg, state: dict):
    os.makedirs(os.path.dirname(cfg.state_file) or ".", exist_ok=True)
    with open(cfg.state_file, "w") as f:
        json.dump(state, f, indent=2)


def run_scan(cfg, universe_df: pd.DataFrame, data_source, max_workers: int = 4,
             send_alerts: bool = True) -> pd.DataFrame:
    rows = []
    records = universe_df.to_dict("records")

    with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(scan_symbol, r, data_source, cfg): r["symbol"] for r in records}
        for i, fut in enumerate(cf.as_completed(futures)):
            sym = futures[fut]
            try:
                res = fut.result()
            except Exception as e:
                print(f"  [!] {sym}: {e}")
                res = None
            if res:
                rows.append(res)
            if (i + 1) % 50 == 0:
                print(f"[scan] processed {i+1}/{len(records)}")

    if not rows:
        return pd.DataFrame()

    out = pd.DataFrame(rows)
    out["_prio"] = out["stage"].map(STAGE_PRIORITY).fillna(9)
    out = out.sort_values(["_prio", "quality_score"], ascending=[True, False]).drop(columns=["_prio", "confluence_raw"])
    out = out.reset_index(drop=True)

    os.makedirs(cfg.results_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out.to_csv(os.path.join(cfg.results_dir, f"scan_{ts}.csv"), index=False)
    out.to_csv(os.path.join(cfg.results_dir, "latest_scan.csv"), index=False)

    if send_alerts:
        _alert_on_transitions(cfg, out)

    return out


def _is_alert_worthy(row: dict, prev_stage: str = None) -> bool:
    """Per-stage freshness + quality-floor gate (2026-08-07, extended 2026-08-08).

    FRESH_REVERSAL: alert only if the reversal happened on the MOST RECENT
    bar (Reversal_date == last_date), i.e. today's close - not up to
    `recency_bars` (5) days stale, which is what caused alerts like
    "reversal confirmed 5d ago" to fire well after the move already happened.

    PRE_BOS2_READY: alert only if the symbol just entered this stage (its
    previously tracked stage in state.json was something else) - it's a
    persisting coiled-state, not a one-bar event, so this is the "fresh"
    equivalent: once per entry, not once per day it continues to sit there.

    Both: quality_grade must be A or B (score >= 65) - cuts C/D-grade noise
    (e.g. POWERGRID 29.4, CIEINDIA 33.9) that shouldn't page anyone.
    """
    stage = row.get("stage")
    if stage not in ALERTABLE_STAGES:
        return False
    grade = str(row.get("quality_grade") or "")
    if not grade or grade[0] not in ALERT_QUALITY_GRADES:
        return False

    if stage == "FRESH_REVERSAL":
        reversal_date = row.get("Reversal_date")
        last_date = row.get("last_date")
        return bool(reversal_date) and bool(last_date) and reversal_date == last_date

    if stage == "PRE_BOS2_READY":
        return prev_stage != "PRE_BOS2_READY"

    return False


def _alert_on_transitions(cfg, out: pd.DataFrame):
    state = _load_state(cfg)
    new_state = dict(state)
    alerts_sent = 0

    for row in out.to_dict("records"):
        sym = row["symbol"]
        cur_stage = row["stage"]
        prev_entry = state.get(sym) or {}
        # tolerate the old (pre-2026-08-07) state.json schema, where the
        # value was just a bare stage string instead of a dict
        if isinstance(prev_entry, dict):
            prev_stage = prev_entry.get("stage")
            prev_reversal_alerted = prev_entry.get("last_reversal_alerted")
        else:
            prev_stage = prev_entry
            prev_reversal_alerted = None

        entry = {"stage": cur_stage}
        reversal_date = row.get("Reversal_date")

        if cur_stage == "FRESH_REVERSAL" and reversal_date == prev_reversal_alerted:
            worthy = False  # already alerted for this exact reversal date (same-day re-run guard)
        else:
            worthy = _is_alert_worthy(row, prev_stage=prev_stage)

        if worthy:
            msg = format_alert(row)
            if send_telegram(msg):
                alerts_sent += 1
                if cur_stage == "FRESH_REVERSAL":
                    entry["last_reversal_alerted"] = reversal_date
        elif prev_reversal_alerted:
            # carry forward so we don't lose the dedup marker on days this
            # symbol isn't alert-worthy
            entry["last_reversal_alerted"] = prev_reversal_alerted

        new_state[sym] = entry

    _save_state(cfg, new_state)
    print(f"[alerts] sent {alerts_sent} telegram alert(s) "
          f"(FRESH_REVERSAL same-day / PRE_BOS2_READY fresh-entry, grade A/B only)")
