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
"""
import pandas as pd

from .base import DataSource
from .dhan import DhanDataSource, DhanAuthError
from .yfinance_source import YFinanceDataSource


class FallbackDataSource(DataSource):
    def __init__(self, cfg):
        self.cfg = cfg
        self.primary = None
        self.secondary = None

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

    def fetch_ohlc(self, symbol: str, security_id: str = None, exchange_segment: str = "NSE_EQ",
                    instrument: str = "EQUITY", days: int = None) -> pd.DataFrame:
        if self.primary is not None:
            try:
                df = self.primary.fetch_ohlc(symbol, security_id=security_id,
                                              exchange_segment=exchange_segment, instrument=instrument,
                                              days=days)
                if df is not None and not df.empty and len(df) >= 60:
                    return df
                print(f"  [data_source] Dhan returned insufficient data for {symbol} "
                      f"({0 if df is None else len(df)} bars) - falling back to yfinance")
            except Exception as e:
                print(f"  [data_source] Dhan failed for {symbol}: {e} - falling back to yfinance")

        if self.secondary is not None:
            try:
                return self.secondary.fetch_ohlc(symbol, days=days)
            except Exception as e:
                print(f"  [data_source] yfinance also failed for {symbol}: {e}")

        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

