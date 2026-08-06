from .dhan import DhanDataSource
from .yfinance_source import YFinanceDataSource


def get_data_source(cfg):
    if cfg.data_source == "dhan":
        return DhanDataSource(cfg)
    elif cfg.data_source == "yfinance":
        return YFinanceDataSource(cfg)
    raise ValueError(f"Unknown data_source: {cfg.data_source}")
