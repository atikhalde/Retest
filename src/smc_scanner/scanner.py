"""Scan orchestration: universe -> data -> indicators -> pattern -> alerts."""
import concurrent.futures as cf
import json
import os
from datetime import datetime

import pandas as pd

from .indicators import add_indicators, confluence_score
from .pattern import detect_pattern
from .notify import send_telegram, format_alert

STAGE_PRIORITY = {
    "FRESH_BOS2": 0,
    "FRESH_REVERSAL": 1,
    "PRE_BOS2_READY": 2,
    "BASING": 3,
    "IN_RETEST": 4,
    "STALE_BOS2": 5,
}

ALERTABLE_STAGES = {"PRE_BOS2_READY", "FRESH_BOS2", "FRESH_REVERSAL"}


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

    def d(x):
        return x.date().isoformat() if x is not None and hasattr(x, "date") else None

    return {
        "symbol": symbol,
        "stage": match.stage,
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
        "volatility_contracted": match.volatility_contracted,
        "atr_contraction_ratio": round(float(match.atr_contraction_ratio), 2) if not pd.isna(match.atr_contraction_ratio) else None,
        "distance_to_p1_pct": round(float(match.distance_to_p1_pct) * 100, 2) if not pd.isna(match.distance_to_p1_pct) else None,
        "BOS2_date": d(match.bos2_date),
        "BOS2_price": round(float(match.bos2_price), 2) if match.bos2_price else None,
        "bars_since_bos2": match.bars_since_bos2,
        "confluence_score": f"{conf['score']}/{conf['max_score']}",
        "confluence_raw": conf["score"],
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
    out = out.sort_values(["_prio", "confluence_raw"], ascending=[True, False]).drop(columns=["_prio", "confluence_raw"])
    out = out.reset_index(drop=True)

    os.makedirs(cfg.results_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out.to_csv(os.path.join(cfg.results_dir, f"scan_{ts}.csv"), index=False)
    out.to_csv(os.path.join(cfg.results_dir, "latest_scan.csv"), index=False)

    if send_alerts:
        _alert_on_transitions(cfg, out)

    return out


def _alert_on_transitions(cfg, out: pd.DataFrame):
    state = _load_state(cfg)
    new_state = dict(state)
    alerts_sent = 0

    for row in out.to_dict("records"):
        sym = row["symbol"]
        prev_stage = state.get(sym)
        cur_stage = row["stage"]
        new_state[sym] = cur_stage

        if cur_stage in ALERTABLE_STAGES and prev_stage != cur_stage:
            msg = format_alert(row)
            if send_telegram(msg):
                alerts_sent += 1

    _save_state(cfg, new_state)
    print(f"[alerts] sent {alerts_sent} telegram alert(s) for new stage transitions")
