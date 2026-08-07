"""
Dhan HQ v2 data source.

Auth
----
Two supported modes (checked in this order):

1. TOTP auto-login (recommended for unattended GitHub Actions runs):
   Set DHAN_CLIENT_ID, DHAN_PIN, DHAN_TOTP_SECRET (the base32 secret you get
   when enabling "Setup TOTP" for API access under My Profile > Access
   DhanHQ APIs on web.dhan.co). A fresh 24h access token is minted on every
   run - nothing to rotate manually, and it survives weekends/holidays.

2. Static access token (simplest for local/manual runs):
   Set DHAN_CLIENT_ID + DHAN_ACCESS_TOKEN directly (generated from
   web.dhan.co, valid 24h). You must refresh this secret yourself once a day.

Rate limiting
-------------
Dhan's documented limit for Data APIs is 5 requests/second (100,000/day).
`_throttle()` sleeps just enough to stay under that regardless of how the
scanner is parallelized.

Failure handling: fail fast, no sleep-and-retry backoff (2026-08-08).
FallbackDataSource already falls back to yfinance per-symbol the instant
Dhan raises - that fallback IS the retry, so Dhan itself never sleeps and
retries on rate-limit/generic errors, it just raises immediately. The one
exception is a stale token in TOTP auto-refresh mode, which gets a single
immediate retry with a freshly minted token (a stale STATIC/Option-B token
would fail identically every time, so that mode doesn't retry at all -
straight to the yfinance fallback). This was a real production issue: a
12m38s intraday-scan run had 111/643 symbols each burning ~4.5s of pure
`time.sleep()` before giving up on Dhan anyway, pushing the run past the
15-minute cron interval and triggering GitHub Actions' concurrency queue
to cancel piled-up runs.
"""
import os
import time
import threading
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
import requests

try:
    import pyotp
except ImportError:
    pyotp = None

from .base import DataSource


class DhanAuthError(RuntimeError):
    pass


class DhanDataSource(DataSource):
    def __init__(self, cfg):
        self.cfg = cfg
        self.client_id = os.environ.get("DHAN_CLIENT_ID")
        if not self.client_id:
            raise DhanAuthError("DHAN_CLIENT_ID is not set")

        self._access_token = None
        self._token_expiry = None
        self._lock = threading.Lock()
        self._last_call_ts = 0.0

        self._static_token = os.environ.get("DHAN_ACCESS_TOKEN")
        self._pin = os.environ.get("DHAN_PIN")
        self._totp_secret = os.environ.get("DHAN_TOTP_SECRET")

    # ------------------------------------------------------------------ auth
    def _generate_token_via_totp(self) -> str:
        if pyotp is None:
            raise DhanAuthError("pyotp not installed but DHAN_TOTP_SECRET is set")
        if not self._pin:
            raise DhanAuthError("DHAN_PIN is required alongside DHAN_TOTP_SECRET")
        code = pyotp.TOTP(self._totp_secret).now()
        url = f"{self.cfg.dhan_auth_url}/app/generateAccessToken"
        r = requests.post(
            url, params={"dhanClientId": self.client_id, "pin": self._pin, "totp": code},
            timeout=15,
        )
        if r.status_code != 200:
            raise DhanAuthError(f"generateAccessToken failed: {r.status_code} {r.text}")
        data = r.json()
        token = data.get("accessToken")
        if not token:
            raise DhanAuthError(f"generateAccessToken returned no token: {data}")
        return token

    def _access_token_value(self) -> str:
        with self._lock:
            if self._access_token and self._token_expiry and datetime.now() < self._token_expiry:
                return self._access_token
            if self._totp_secret:
                self._access_token = self._generate_token_via_totp()
                self._token_expiry = datetime.now() + timedelta(hours=23)
            elif self._static_token:
                self._access_token = self._static_token
                self._token_expiry = datetime.now() + timedelta(hours=23)
            else:
                raise DhanAuthError(
                    "No Dhan credentials found: set either "
                    "(DHAN_CLIENT_ID + DHAN_PIN + DHAN_TOTP_SECRET) or "
                    "(DHAN_CLIENT_ID + DHAN_ACCESS_TOKEN)"
                )
            return self._access_token

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "access-token": self._access_token_value(),
            "client-id": self.client_id,
        }

    # -------------------------------------------------------------- throttle
    def _throttle(self):
        with self._lock:
            min_interval = 1.0 / max(self.cfg.dhan_requests_per_sec, 0.1)
            now = time.time()
            wait = self._last_call_ts + min_interval - now
            if wait > 0:
                time.sleep(wait)
            self._last_call_ts = time.time()

    def _post(self, path: str, payload: dict) -> dict:
        """Fail fast, no sleep-and-retry backoff (2026-08-08 fix).

        Real evidence from a production intraday-scan run: 111/643 symbols
        hit Dhan rate-limit-type responses on every one of 3 attempts, each
        one burning ~4.5s of pure `time.sleep()` backoff (1.5s + 3.0s)
        before finally giving up and falling back to yfinance anyway - that
        alone accounted for ~8+ minutes of a 12m38s scan, pushing it past
        the 15-minute intraday cron interval and causing GitHub Actions'
        `concurrency` queue to cancel piled-up runs.

        FallbackDataSource already falls back to yfinance per-symbol the
        moment Dhan raises - there is no benefit to Dhan retrying/sleeping
        here, since the fallback IS the retry. The one exception: a stale
        token in TOTP auto-refresh mode is worth a single immediate retry
        (with a freshly minted token) - but a stale STATIC token (Option B)
        will fail identically every time, so don't bother retrying that
        either, just fail straight to the fallback.
        """
        url = f"{self.cfg.dhan_base_url}{path}"
        last_exc = None
        attempts = 2 if self._totp_secret else 1  # only TOTP mode can mint a genuinely new token
        for attempt in range(attempts):
            self._throttle()
            try:
                r = requests.post(url, json=payload, headers=self._headers(), timeout=20)
            except requests.RequestException as e:
                raise RuntimeError(f"Dhan request failed on {path}: {e}") from e
            if r.status_code == 200:
                return r.json()
            if r.status_code in (401, 807, 808, 809) and attempt < attempts - 1:
                # stale token AND we can mint a fresh one (TOTP mode) - retry
                # immediately, no sleep
                with self._lock:
                    self._access_token = None
                continue
            last_exc = RuntimeError(f"Dhan API error {r.status_code} on {path}: {r.text[:300]}")
            break
        raise last_exc


    # ----------------------------------------------------------------- data
    def fetch_daily(self, security_id: str, exchange_segment: str, instrument: str,
                     from_date: str, to_date: str) -> pd.DataFrame:
        payload = {
            "securityId": str(security_id),
            "exchangeSegment": exchange_segment,
            "instrument": instrument,
            "expiryCode": 0,
            "oi": False,
            "fromDate": from_date,
            "toDate": to_date,
        }
        data = self._post("/charts/historical", payload)
        return self._to_df(data)

    def fetch_intraday(self, security_id: str, exchange_segment: str, instrument: str,
                        from_date: str, to_date: str, interval: str = "5") -> pd.DataFrame:
        payload = {
            "securityId": str(security_id),
            "exchangeSegment": exchange_segment,
            "instrument": instrument,
            "interval": interval,
            "oi": False,
            "fromDate": from_date,
            "toDate": to_date,
        }
        data = self._post("/charts/intraday", payload)
        return self._to_df(data)

    @staticmethod
    def _to_df(data: dict) -> pd.DataFrame:
        if not data or not data.get("timestamp"):
            return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
        idx = pd.to_datetime(data["timestamp"], unit="s", utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
        df = pd.DataFrame({
            "Open": data["open"], "High": data["high"], "Low": data["low"],
            "Close": data["close"], "Volume": data["volume"],
        }, index=idx)
        return df

    def get_today_partial_daily_bar(self, security_id: str, exchange_segment: str, instrument: str) -> Optional[dict]:
        """Aggregate today's intraday candles into one OHLCV bar (the 'in-progress' daily candle)."""
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            intraday = self.fetch_intraday(
                security_id, exchange_segment, instrument,
                from_date=f"{today} 09:15:00", to_date=f"{today} 23:59:59",
                interval=self.cfg.intraday_interval_min,
            )
        except Exception:
            return None
        if intraday.empty:
            return None
        return {
            "date": pd.Timestamp(datetime.now().date()),
            "Open": intraday["Open"].iloc[0],
            "High": intraday["High"].max(),
            "Low": intraday["Low"].min(),
            "Close": intraday["Close"].iloc[-1],
            "Volume": intraday["Volume"].sum(),
        }

    def fetch_ohlc(self, symbol: str, security_id: str = None, exchange_segment: str = "NSE_EQ",
                    instrument: str = "EQUITY", days: int = None) -> pd.DataFrame:
        to_date = datetime.now().strftime("%Y-%m-%d")
        n_days = days if days else self.cfg.daily_history_days
        from_date = (datetime.now() - timedelta(days=n_days)).strftime("%Y-%m-%d")
        df = self.fetch_daily(security_id, exchange_segment, instrument, from_date, to_date)
        if df.empty:
            return df
        df.index = pd.to_datetime(df.index).normalize()
        df = df[~df.index.duplicated(keep="last")].sort_index()

        if self.cfg.scan_mode == "intraday":
            bar = self.get_today_partial_daily_bar(security_id, exchange_segment, instrument)
            if bar is not None:
                today_ts = pd.Timestamp(bar["date"])
                row = pd.DataFrame([{
                    "Open": bar["Open"], "High": bar["High"], "Low": bar["Low"],
                    "Close": bar["Close"], "Volume": bar["Volume"],
                }], index=[today_ts])
                if today_ts in df.index:
                    df.loc[today_ts] = row.iloc[0]
                else:
                    df = pd.concat([df, row])
                df = df.sort_index()
        return df


# ------------------------------------------------------------------ scrip master

def load_scrip_master(cfg, force_refresh: bool = False) -> pd.DataFrame:
    """Download (and cache) Dhan's instrument master CSV."""
    cache_path = cfg.dhan_scrip_master_cache
    need_download = force_refresh or not os.path.exists(cache_path)
    if not need_download:
        age_hours = (time.time() - os.path.getmtime(cache_path)) / 3600.0
        need_download = age_hours > cfg.dhan_scrip_master_max_age_hours

    if need_download:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        r = requests.get(cfg.dhan_scrip_master_url, timeout=60)
        r.raise_for_status()
        with open(cache_path, "wb") as f:
            f.write(r.content)

    df = pd.read_csv(cache_path, low_memory=False)
    return df


def filter_nse_cash_equities(scrip_df: pd.DataFrame, cfg) -> pd.DataFrame:
    """NSE cash-market, regular-series equities, excluding ETFs / T2T / SME / debt series."""
    df = scrip_df.copy()
    df = df[
        (df["SEM_EXM_EXCH_ID"] == "NSE")
        & (df["SEM_SEGMENT"] == "E")
        & (df["SEM_INSTRUMENT_NAME"] == "EQUITY")
        & (~df["SEM_EXCH_INSTRUMENT_TYPE"].isin(cfg.exclude_instrument_types))
        & (~df["SEM_SERIES"].isin(cfg.exclude_series))
    ]
    return df[["SEM_SMST_SECURITY_ID", "SEM_TRADING_SYMBOL", "SM_SYMBOL_NAME"]].rename(
        columns={"SEM_SMST_SECURITY_ID": "security_id", "SEM_TRADING_SYMBOL": "symbol",
                 "SM_SYMBOL_NAME": "name"}
    ).drop_duplicates(subset=["symbol"])
