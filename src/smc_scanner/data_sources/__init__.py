from .dhan import DhanDataSource
from .yfinance_source import YFinanceDataSource
from .fallback import FallbackDataSource


def get_data_source(cfg):
    if cfg.data_source == "dhan":
        # Dhan primary, yfinance secondary - resilient by default for live scans
        return FallbackDataSource(cfg)
    elif cfg.data_source == "dhan_only":
        # strict Dhan-only mode, no fallback (useful for debugging Dhan itself)
        return DhanDataSource(cfg)
    elif cfg.data_source == "yfinance":
        return YFinanceDataSource(cfg)
    raise ValueError(f"Unknown data_source: {cfg.data_source}")
