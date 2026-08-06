"""
Universe construction & loading.

`build_universe()` is a slow, once-a-week job (run via the
update_universe.yml workflow): it pulls Dhan's scrip master, keeps NSE cash
equities only, excludes ETFs/T2T/SME series, then enriches with market cap
(via yfinance, since Dhan's own APIs don't expose fundamentals) and writes
the filtered list to `data/universe.csv`.

`get_universe()` is the fast path used by every scan run: it just reads that
CSV and applies the market-cap / price filters from Config.
"""
import concurrent.futures as cf
import os
import time
from datetime import datetime

import pandas as pd

from .data_sources.dhan import load_scrip_master, filter_nse_cash_equities

try:
    import yfinance as yf
except ImportError:
    yf = None


def _market_cap_cr(symbol: str) -> float:
    """Market cap in INR crore, via yfinance fast_info. Returns NaN on failure."""
    if yf is None:
        return float("nan")
    try:
        fi = yf.Ticker(f"{symbol}.NS").fast_info
        mc = getattr(fi, "market_cap", None)
        if not mc:
            return float("nan")
        return mc / 1e7  # 1 crore = 1e7
    except Exception:
        return float("nan")


def build_universe(cfg, max_workers: int = 8, throttle_sec: float = 0.05, retry_pass: bool = True,
                    max_age_days: int = 25) -> pd.DataFrame:
    """
    Rebuild data/universe.csv.

    Market-cap lookups go through free, unofficial Yahoo Finance endpoints
    (via yfinance) which are prone to aggressive rate limiting on bursts of
    thousands of requests. To stay resilient:
      - Previously resolved market caps are cached and reused for
        `max_age_days` before being re-fetched (so one bad/rate-limited run
        doesn't wipe out everything - it only tries to refresh stale/missing
        rows).
      - Failed rows keep whatever value they had before (if any).
    """
    scrip = load_scrip_master(cfg, force_refresh=True)
    candidates = filter_nse_cash_equities(scrip, cfg)
    print(f"[universe] {len(candidates)} NSE cash-equity candidates after series/ETF filter")

    old_df = None
    if os.path.exists(cfg.universe_file):
        try:
            old_df = pd.read_csv(cfg.universe_file)
        except Exception:
            old_df = None

    now = datetime.now()
    to_fetch = []
    cached_mc = {}
    cached_updated = {}
    if old_df is not None and "market_cap_cr" in old_df.columns:
        for _, r in old_df.iterrows():
            if pd.isna(r.get("market_cap_cr")):
                continue
            try:
                age_days = (now - pd.to_datetime(r["updated_at"])).days
            except Exception:
                age_days = max_age_days + 1
            if age_days <= max_age_days:
                cached_mc[r["symbol"]] = r["market_cap_cr"]
                cached_updated[r["symbol"]] = r["updated_at"]

    symbols = candidates["symbol"].tolist()
    to_fetch = [s for s in symbols if s not in cached_mc]
    print(f"[universe] {len(cached_mc)} symbols have a fresh cached market cap (<= {max_age_days}d old); "
          f"fetching {len(to_fetch)} new/stale symbols")

    def worker(sym):
        if throttle_sec:
            time.sleep(throttle_sec)
        return sym, _market_cap_cr(sym)

    fetched = {}
    if to_fetch:
        with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
            for i, (sym, mc) in enumerate(ex.map(worker, to_fetch)):
                fetched[sym] = mc
                if (i + 1) % 100 == 0:
                    print(f"[universe] market cap fetched for {i+1}/{len(to_fetch)}")

        if retry_pass:
            missing = [s for s, mc in fetched.items() if pd.isna(mc)]
            if missing:
                print(f"[universe] retrying {len(missing)} symbols with NaN market cap "
                      f"(smaller batch, gentler pace)...")
                with cf.ThreadPoolExecutor(max_workers=max(2, max_workers // 4)) as ex:
                    futs = {ex.submit(worker, s): s for s in missing}
                    for fut in cf.as_completed(futs):
                        sym = futs[fut]
                        try:
                            _, mc = fut.result()
                        except Exception:
                            mc = float("nan")
                        if not pd.isna(mc):
                            fetched[sym] = mc
                recovered = sum(1 for s in missing if not pd.isna(fetched.get(s, float("nan"))))
                print(f"[universe] retry recovered {recovered}/{len(missing)}")

    updated_at_now = now.isoformat(timespec="seconds")
    rows = []
    for sym in symbols:
        if sym in cached_mc:
            rows.append((sym, cached_mc[sym], cached_updated[sym]))
        elif sym in fetched and not pd.isna(fetched[sym]):
            rows.append((sym, fetched[sym], updated_at_now))
        elif old_df is not None and sym in set(old_df.get("symbol", [])):
            prev = old_df[old_df["symbol"] == sym].iloc[0]
            rows.append((sym, prev.get("market_cap_cr"), prev.get("updated_at")))
        else:
            rows.append((sym, float("nan"), updated_at_now))

    mc_df = pd.DataFrame(rows, columns=["symbol", "market_cap_cr", "updated_at"])
    out = candidates.merge(mc_df, on="symbol", how="left")
    out["exchange_segment"] = "NSE_EQ"
    out["instrument"] = "EQUITY"
    out = out.sort_values("market_cap_cr", ascending=False)

    os.makedirs(os.path.dirname(cfg.universe_file) or ".", exist_ok=True)
    out.to_csv(cfg.universe_file, index=False)
    resolved = out["market_cap_cr"].notna().sum()
    print(f"[universe] wrote {len(out)} rows -> {cfg.universe_file} ({resolved} with market cap resolved, "
          f"{(out['market_cap_cr'].fillna(0) >= cfg.min_market_cap_cr).sum()} pass >= {cfg.min_market_cap_cr} cr)")
    return out




def get_universe(cfg) -> pd.DataFrame:
    if not os.path.exists(cfg.universe_file):
        raise FileNotFoundError(
            f"{cfg.universe_file} not found. Run `python -m smc_scanner.cli build-universe` first "
            "(or wait for the weekly update_universe workflow)."
        )
    df = pd.read_csv(cfg.universe_file)
    df = df[df["market_cap_cr"].fillna(0) >= cfg.min_market_cap_cr]
    return df.reset_index(drop=True)
