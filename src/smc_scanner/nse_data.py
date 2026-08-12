"""
NSE live "Volume Gainers" enrichment (intraday scan only, 2026-08-12).

Cross-references intraday-scan alerts against NSE's own live Volume Gainers
list (https://www.nseindia.com/market-data/volume-gainers-spurts) - if a
stock we're alerting on is *also* independently flagged by NSE as having
unusually high volume right now, that's a real extra confluence signal
worth calling out prominently (per user example: PITTIENG showed up in
both our PRE_BOS2_READY alert and NSE's volume gainers list on the same
day).

Reliability: NSE's site is known to challenge/block automated requests,
especially from cloud datacenter IPs - which is exactly what GitHub
Actions runners are. This module is designed to fail soft: if the NSE
fetch doesn't work, `fetch_nse_volume_gainers()` returns None and callers
fall back to `is_volume_gainer_fallback()`, which reuses the Volume/
VOL_SMA20 columns the scanner already computes for every symbol during a
normal scan (no extra network calls) - flagging "today's volume is at
least N times its 20-day average" as a same-intent proxy for what NSE's
own list is measuring.
"""
import pandas as pd
import requests

NSE_PAGE_URL = "https://www.nseindia.com/market-data/volume-gainers-spurts"
NSE_API_URL = "https://www.nseindia.com/api/live-analysis-volume-gainers"

_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_nse_volume_gainers(timeout: int = 10):
    """Returns a dict of {symbol: surge_multiple} for every symbol currently
    on NSE's live Volume Gainers list, or None if the fetch failed for any
    reason (network error, non-200, blocked/challenged, malformed
    response). Never raises - a failure here should never take down the
    rest of the scan.

    `surge_multiple` is NSE's own `week1volChange` field, i.e. today's
    volume divided by the symbol's trailing 1-week average volume (verified
    against NSE's own `volume`/`week1AvgVolume` columns - they match
    exactly). 2026-08-12 addition: this used to just be a plain set of
    symbols; now it also carries the multiple so alerts can show "how big"
    the surge is, not just that one exists - the membership check itself
    (which symbols count as "gainers") is unchanged.
    """
    try:
        session = requests.Session()
        session.headers.update(_HEADERS)
        # NSE typically wants a "real browser" warm-up hit on the page
        # itself first to set session cookies before the API call succeeds.
        session.get(NSE_PAGE_URL, timeout=timeout)
        r = session.get(NSE_API_URL, timeout=timeout)
        if r.status_code != 200:
            print(f"[nse_data] volume-gainers fetch failed: HTTP {r.status_code} - "
                  f"falling back to our own volume-vs-average check")
            return None
        data = r.json()
        rows = data.get("data", [])
        gainers = {row["symbol"]: float(row["week1volChange"])
                   for row in rows if "symbol" in row and "week1volChange" in row}
        print(f"[nse_data] fetched {len(gainers)} symbols from NSE's live Volume Gainers list")
        return gainers
    except Exception as e:
        print(f"[nse_data] volume-gainers fetch failed ({e}) - "
              f"falling back to our own volume-vs-average check")
        return None


def is_volume_gainer_fallback(df: pd.DataFrame, cfg):
    """Self-contained fallback when NSE itself couldn't be reached: flags
    "today's volume is at least `volume_gainer_fallback_multiple` times its
    20-day average" using data the scanner already fetched for this symbol
    - no extra network calls, same underlying intent as NSE's own list.

    Returns (is_gainer: bool, surge_multiple: float or None). The pass/fail
    threshold logic is unchanged from before (2026-08-12) - this just also
    returns the actual computed ratio for display, whether or not it
    passed the threshold.
    """
    if df is None or df.empty or "VOL_SMA20" not in df.columns:
        return False, None
    last_vol = df["Volume"].values[-1]
    vol_sma20 = df["VOL_SMA20"].values[-1]
    if pd.isna(last_vol) or pd.isna(vol_sma20) or vol_sma20 <= 0:
        return False, None
    ratio = float(last_vol / vol_sma20)
    is_gainer = bool(last_vol >= cfg.volume_gainer_fallback_multiple * vol_sma20)
    return is_gainer, ratio

