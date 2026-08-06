"""Common interface all data sources implement."""
from abc import ABC, abstractmethod
import pandas as pd


class DataSource(ABC):
    @abstractmethod
    def fetch_ohlc(self, symbol: str, security_id: str = None, exchange_segment: str = None) -> pd.DataFrame:
        """Return a DataFrame indexed by date with columns Open, High, Low, Close, Volume.

        The most recent row may be a *partial* (in-progress) candle when the
        scanner is run in intraday mode - callers should treat the last row's
        indicators as provisional until the session closes.
        """
        raise NotImplementedError
