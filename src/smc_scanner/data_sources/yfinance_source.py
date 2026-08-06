"""yfinance fallback data source - handy for local testing without Dhan creds,
or for backtesting since it gives easy access to long daily history for free."""
import pandas as pd

from .base import DataSource

try:
    import yfinance as yf
except ImportError:
    yf = None


class YFinanceDataSource(DataSource):
    def __init__(self, cfg):
        self.cfg = cfg
        if yf is None:
            raise ImportError("pip install yfinance to use the yfinance data source")

    def fetch_ohlc(self, symbol: str, security_id: str = None, exchange_segment: str = None, **kwargs) -> pd.DataFrame:
        yf_symbol = symbol if "." in symbol else f"{symbol}.NS"
        df = yf.download(yf_symbol, period="2y", interval="1d", progress=False, auto_adjust=False)
        if df is None or df.empty:
            return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        return df[["Open", "High", "Low", "Close", "Volume"]].dropna()
