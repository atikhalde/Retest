"""
Dhan-primary, yfinance-secondary data source.

Tries Dhan first for every symbol (that's what the live scanner should use -
real-time, accurate NSE data via your own broker account). If Dhan raises
an error (auth failure, rate limit, bad security_id, network issue) or
returns insufficient data for a symbol, it transparently falls back to
yfinance for that symbol only, logs why, and keeps going - one bad symbol
or a temporary Dhan outage never kills the whole scan.

If Dhan can't even be initialized at all (e.g. no credentials configured),
the whole run falls back to yfinance for every symbol instead of crashing.

Circuit breaker (2026-08-08, tightened same day per user request): a real
production run saw Dhan reject ~100% of requests with rate-limit errors
(DH-904 "Too many requests on server from single user") - almost
certainly residual account-level throttling from a burst of prior scans,
not something a per-request backoff can fix. Once Dhan has failed with a
rate-limit error `CIRCUIT_BREAKER_THRESHOLD` times in a row (with no
successes in between - currently 3, tightened down from an initial 8
since even that many wasted attempts felt too slow to fail over), this
class stops even trying Dhan for the rest of the run and goes straight to
yfinance for every remaining symbol - no point hammering an API that's
actively telling us to back off, and it means the scan doesn't waste one
HTTP round-trip per symbol on a call that's already proven doomed for
this run.
"""
import threading

import pandas as pd

from .base import DataSource
from .dhan import DhanDataSource, DhanAuthError
from .yfinance_source import YFinanceDataSource


class FallbackDataSource(DataSource):
    RATE_LIMIT_MARKERS = ("429", "DH-904", "DH-805", "Rate_Limit")
    CIRCUIT_BREAKER_THRESHOLD = 3

    def __init__(self, cfg):
        self.cfg = cfg
        self.primary = None
        self.secondary = None
        self._lock = threading.Lock()
        self._consecutive_rate_limit_failures = 0
        self._dhan_circuit_open = False

        try:
            self.primary = DhanDataSource(cfg)
        except Exception as e:
            print(f"[data_source] Dhan unavailable at startup ({e}) - "
                  f"every symbol will use yfinance for this run")

        try:
            self.secondary = YFinanceDataSource(cfg)
        except Exception as e:
            print(f"[data_source] yfinance fallback unavailable ({e})")

        if self.primary is None and self.secondary is None:
            raise RuntimeError(
                "No data source available: Dhan failed to initialize and "
                "yfinance isn't usable either. Check credentials / `pip install yfinance`."
            )

    def _is_rate_limit_error(self, exc: Exception) -> bool:
        msg = str(exc)
        return any(marker in msg for marker in self.RATE_LIMIT_MARKERS)

    def fetch_ohlc(self, symbol: str, security_id: str = None, exchange_segment: str = "NSE_EQ",
                    instrument: str = "EQUITY", days: int = None) -> pd.DataFrame:
        if self.primary is not None and not self._dhan_circuit_open:
            try:
                df = self.primary.fetch_ohlc(symbol, security_id=security_id,
                                              exchange_segment=exchange_segment, instrument=instrument,
                                              days=days)
                if df is not None and not df.empty and len(df) >= 60:
                    if self._consecutive_rate_limit_failures:
                        with self._lock:
                            self._consecutive_rate_limit_failures = 0
                    return df
                print(f"  [data_source] Dhan returned insufficient data for {symbol} "
                      f"({0 if df is None else len(df)} bars) - falling back to yfinance")
            except Exception as e:
                print(f"  [data_source] Dhan failed for {symbol}: {e} - falling back to yfinance")
                if self._is_rate_limit_error(e):
                    with self._lock:
                        self._consecutive_rate_limit_failures += 1
                        if (self._consecutive_rate_limit_failures >= self.CIRCUIT_BREAKER_THRESHOLD
                                and not self._dhan_circuit_open):
                            self._dhan_circuit_open = True
                            print(f"  [data_source] Dhan rate-limited {self.CIRCUIT_BREAKER_THRESHOLD} "
                                  f"times in a row - disabling Dhan for the rest of this run, "
                                  f"using yfinance only from here on")
                else:
                    with self._lock:
                        self._consecutive_rate_limit_failures = 0

        if self.secondary is not None:
            try:
                return self.secondary.fetch_ohlc(symbol, days=days)
            except Exception as e:
                print(f"  [data_source] yfinance also failed for {symbol}: {e}")

        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])


