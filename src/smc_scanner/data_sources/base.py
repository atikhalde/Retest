"""Common interface all data sources implement."""
from abc import ABC, abstractmethod
import pandas as pd


class DataSource(ABC):
    @abstractmethod
    def fetch_ohlc(self, symbol: str, security_id: str = None, exchange_segment: str = None,
                    days: int = None) -> pd.DataFrame:
        """Return a DataFrame indexed by date with columns Open, High, Low, Close, Volume.

        `days`: optional override for how many calendar days of history to
        fetch (e.g. from the backtest CLI's `--years`). If omitted, each
        source falls back to its own default tuned for live scanning.

        The most recent row may be a *partial* (in-progress) candle when the
        scanner is run in intraday mode - callers should treat the last row's
        indicators as provisional until the session closes.
        """
        raise NotImplementedError

