"""
Central configuration for the SMC structure scanner.

Every tunable knob lives here. Values can be overridden via environment
variables (handy for GitHub Actions) - see `from_env()`.
"""
from dataclasses import dataclass, field
import os


def _f(name, default):
    v = os.environ.get(name)
    return float(v) if v not in (None, "") else default


def _i(name, default):
    v = os.environ.get(name)
    return int(v) if v not in (None, "") else default


def _s(name, default):
    v = os.environ.get(name)
    return v if v not in (None, "") else default


def _b(name, default):
    v = os.environ.get(name)
    if v is None or v == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Config:
    # ---------------- data source ----------------
    data_source: str = "dhan"          # "dhan" or "yfinance"
    daily_history_days: int = 400      # how much daily history to keep/fetch
    intraday_interval_min: str = "5"   # Dhan intraday candle size used to build "today's" forming daily bar
    scan_mode: str = "eod"             # "eod" or "intraday" - controls whether today's partial candle is included

    # ---------------- universe ----------------
    universe_file: str = "data/universe.csv"     # symbol,security_id,exchange_segment,market_cap_cr
    min_market_cap_cr: float = 1000.0
    min_price: float = 20.0
    exclude_series: tuple = ("BE", "BZ", "GS", "SG", "SM", "ST", "MF", "SF", "GB", "TB", "IV")
    exclude_instrument_types: tuple = ("ETF",)

    # ---------------- pivot detection (fractal) ----------------
    pivot_left: int = 4
    pivot_right: int = 4

    # ---------------- impulse / BOS #1 ----------------
    breakout_buffer: float = 0.005
    vol_mult_impulse: float = 1.5
    lookback_bars: int = 150

    # ---------------- retest ----------------
    max_undercut_pct: float = 0.05
    retest_zone_pct: float = 0.06

    # ---------------- re-accumulation / pre-breakout ----------------
    min_reaccum_bars: int = 5          # min bars of basing before BOS2 is eligible / before PRE_BOS2_READY fires
    max_reaccum_bars: int = 60
    pre_bos2_proximity_pct: float = 0.03    # within 3% of P1 => PRE_BOS2_READY candidate
    pre_bos2_max_atr_ratio: float = 0.75    # ATR(reaccum) / ATR(impulse) must contract below this => "coiled"

    # ---------------- BOS #2 / continuation ----------------
    vol_mult_bos2: float = 1.3
    recency_bars: int = 5              # how many bars back a BOS2 still counts as FRESH

    # ---------------- confluence / quality ----------------
    ema_fast: int = 20
    ema_slow: int = 50
    rsi_period: int = 14
    rsi_min: float = 55.0
    vol_sma_period: int = 10

    # ---------------- Dhan API ----------------
    dhan_base_url: str = "https://api.dhan.co/v2"
    dhan_auth_url: str = "https://auth.dhan.co"
    dhan_requests_per_sec: float = 4.0     # keep under the documented 5 req/sec limit
    dhan_scrip_master_url: str = "https://images.dhan.co/api-data/api-scrip-master.csv"
    dhan_scrip_master_cache: str = "data/cache/scrip_master.csv"
    dhan_scrip_master_max_age_hours: int = 24

    # ---------------- state / alerting ----------------
    state_file: str = "results/state.json"
    results_dir: str = "results"

    debug: bool = False

    @staticmethod
    def from_env() -> "Config":
        c = Config()
        c.data_source = _s("SCANNER_DATA_SOURCE", c.data_source)
        c.scan_mode = _s("SCANNER_MODE", c.scan_mode)
        c.min_market_cap_cr = _f("MIN_MARKET_CAP_CR", c.min_market_cap_cr)
        c.min_price = _f("MIN_PRICE", c.min_price)
        c.recency_bars = _i("RECENCY_BARS", c.recency_bars)
        c.min_reaccum_bars = _i("MIN_REACCUM_BARS", c.min_reaccum_bars)
        c.pre_bos2_proximity_pct = _f("PRE_BOS2_PROXIMITY_PCT", c.pre_bos2_proximity_pct)
        c.debug = _b("SCANNER_DEBUG", c.debug)
        return c
