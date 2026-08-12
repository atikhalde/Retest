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
    data_source: str = "dhan"          # "dhan" (Dhan primary, auto-falls back to yfinance
                                        # per-symbol on any failure), "dhan_only" (no fallback,
                                        # for debugging Dhan itself), or "yfinance" (no Dhan at all)
    daily_history_days: int = 400      # how much daily history to keep/fetch for LIVE scans
    intraday_interval_min: str = "5"   # Dhan intraday candle size used to build "today's" forming daily bar
    scan_mode: str = "eod"             # "eod" or "intraday" - controls whether today's partial candle is included

    # `backtest` is research tooling and wants much deeper history than a
    # live scan needs (more chains -> more statistically meaningful stats).
    # Overridable per-run via `--years` on the CLI.
    backtest_history_years: float = 5.0

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
    # BOS1 must be a genuine breakout to a new N-week high (matching the
    # original TradingView indicator's "close > 26W high" entry gate) - NOT
    # just any minor local pivot. 130 trading days ~= 26 weeks.
    bos1_lookback_weeks: int = 26
    bos1_lookback_bars: int = 130
    breakout_buffer: float = 0.005
    vol_mult_impulse: float = 1.5
    lookback_bars: int = 150

    # ---------------- retest ----------------
    # Real NSE mid/large-caps routinely see 7-10% intra-base drawdowns
    # without the broader bullish structure actually being invalidated
    # (e.g. AUBank dipped ~7.75% below its P0 during re-accumulation before
    # continuing - a tighter 5% tolerance wrongly invalidated that chain).
    max_undercut_pct: float = 0.10
    retest_zone_pct: float = 0.10

    # ---------------- re-accumulation / pre-breakout ----------------
    min_reaccum_bars: int = 5          # min bars of basing before BOS2 is eligible / before PRE_BOS2_READY fires
    max_reaccum_bars: int = 90
    pre_bos2_proximity_pct: float = 0.03    # within 3% of P1 => PRE_BOS2_READY candidate
    pre_bos2_max_atr_ratio: float = 0.75    # ATR(reaccum) / ATR(impulse) must contract below this => "coiled"

    # ---------------- BOS #2 / continuation ----------------
    vol_mult_bos2: float = 1.3
    recency_bars: int = 5              # how many bars back a BOS2 still counts as FRESH

    # ---------------- trade plan (entry/stop/target) ----------------
    # Backtested avg risk (~3.33%) and avg winning-trade return (~3.39%)
    # over the best 5-7 day hold are almost exactly 1:1 - see
    # scripts/optimize_stop_loss.py and README "Best stop-loss..." section.
    target_reward_risk: float = 1.0
    hold_days_min: int = 4
    hold_days_max: int = 7


    # ---------------- confluence / quality ----------------
    ema_fast: int = 20
    ema_slow: int = 50
    rsi_period: int = 14
    rsi_min: float = 55.0
    vol_sma_period: int = 10

    # ---------------- NSE volume-gainers enrichment (intraday scan only) ----------------
    # Cross-references intraday alerts against NSE's live Volume Gainers
    # list (nse_data.py). If NSE itself can't be reached (common from cloud
    # IPs like GitHub Actions runners), falls back to flagging today's
    # volume >= this many times the symbol's own 20-day average, using data
    # the scan already fetched - no extra network calls needed for the
    # fallback path.
    volume_gainer_fallback_multiple: float = 5.0

    # ---------------- Dhan API ----------------
    dhan_base_url: str = "https://api.dhan.co/v2"
    dhan_auth_url: str = "https://auth.dhan.co"
    dhan_requests_per_sec: float = 3.0     # documented limit is 5/sec, but a real production
                                            # run got rate-limited (DH-904) on ~100% of requests
                                            # at 4/sec - more headroom + the fallback.py circuit
                                            # breaker (2026-08-08) handle this together
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
        c.backtest_history_years = _f("BACKTEST_HISTORY_YEARS", c.backtest_history_years)
        c.recency_bars = _i("RECENCY_BARS", c.recency_bars)
        c.min_reaccum_bars = _i("MIN_REACCUM_BARS", c.min_reaccum_bars)
        c.pre_bos2_proximity_pct = _f("PRE_BOS2_PROXIMITY_PCT", c.pre_bos2_proximity_pct)
        c.debug = _b("SCANNER_DEBUG", c.debug)
        return c
