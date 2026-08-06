"""Technical indicators used by the scanner (no TA-Lib dependency)."""
import numpy as np
import pandas as pd


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(50)


def macd_hist(series: pd.Series, fast=12, slow=26, signal=9) -> pd.Series:
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    return macd_line - signal_line


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def add_indicators(df: pd.DataFrame, cfg) -> pd.DataFrame:
    df = df.copy()
    df["EMA_FAST"] = ema(df["Close"], cfg.ema_fast)
    df["EMA_SLOW"] = ema(df["Close"], cfg.ema_slow)
    df["RSI"] = rsi(df["Close"], cfg.rsi_period)
    df["MACD_HIST"] = macd_hist(df["Close"])
    df["ATR"] = atr(df, 14)
    df["VOL_SMA"] = df["Volume"].rolling(cfg.vol_sma_period).mean()
    df["VOL_SMA20"] = df["Volume"].rolling(20).mean()
    return df


def confluence_score(df: pd.DataFrame, cfg) -> dict:
    last = df.iloc[-1]
    ref_idx = -3 if len(df) > 3 else -1
    checks = {
        "close_gt_min_price": bool(last["Close"] > cfg.min_price),
        "ema_fast_gt_slow": bool(last["EMA_FAST"] > last["EMA_SLOW"]),
        "ema_fast_rising": bool(last["EMA_FAST"] > df["EMA_FAST"].iloc[ref_idx]),
        "rsi_gt_threshold": bool(last["RSI"] > cfg.rsi_min),
        "rsi_rising": bool(last["RSI"] > df["RSI"].iloc[ref_idx]),
        "macd_hist_positive": bool(last["MACD_HIST"] > 0),
        "volume_above_sma": bool(last["Volume"] > last["VOL_SMA"]),
        "green_candle": bool(last["Close"] > last["Open"]),
        "near_52w_high": bool(
            last["Close"] >= df["Close"].rolling(min(len(df), 252)).max().iloc[-1] * 0.95
        ),
    }
    score = sum(checks.values())
    return {"score": score, "max_score": len(checks), **checks}
