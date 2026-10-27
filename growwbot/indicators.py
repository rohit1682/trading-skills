"""Technical indicators on OHLCV DataFrames.

Every function takes a pandas DataFrame (or Series) indexed by timestamp with
lower-case columns ``open, high, low, close, volume`` and returns a Series or
DataFrame aligned to the same index. Nothing here looks ahead: the value at
bar ``t`` only uses bars ``<= t``.

Smoothing conventions follow the originals:
  * RSI, ATR and ADX use Wilder's smoothing (alpha = 1/period).
  * EMA uses the standard span-based alpha (2 / (period + 1)).
  * Supertrend uses Wilder ATR and the usual "final band" carry-forward rules.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def _wilder(series: pd.Series, period: int) -> pd.Series:
    """Wilder's moving average (TradingView ``ta.rma``): seeded with the SMA of the
    first ``period`` valid values, then ``prev + (x - prev) / period``."""
    x = series.to_numpy(dtype=float)
    out = np.full(len(x), np.nan)
    valid = np.flatnonzero(~np.isnan(x))
    if len(valid) < period:
        return pd.Series(out, index=series.index)
    start = valid[period - 1]
    prev = np.nanmean(x[valid[0]:start + 1])
    out[start] = prev
    for i in range(start + 1, len(x)):
        if not np.isnan(x[i]):
            prev = prev + (x[i] - prev) / period
        out[i] = prev
    return pd.Series(out, index=series.index)


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = _wilder(gain, period)
    avg_loss = _wilder(loss, period)
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - 100.0 / (1.0 + rs)
    # No losses in the window -> RSI 100; flat window -> 50.
    out = out.where(avg_loss != 0.0, np.where(avg_gain > 0.0, 100.0, 50.0))
    return out.where(avg_gain.notna())


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    ranges = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()],
        axis=1,
    )
    return ranges.max(axis=1)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    return _wilder(true_range(df), period)


def bollinger(close: pd.Series, period: int = 20, mult: float = 2.0) -> pd.DataFrame:
    mid = sma(close, period)
    std = close.rolling(period, min_periods=period).std(ddof=0)
    return pd.DataFrame({"mid": mid, "upper": mid + mult * std, "lower": mid - mult * std})


def vwap(df: pd.DataFrame) -> pd.Series:
    """Session VWAP that resets every calendar day (intraday data only)."""
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    day = pd.Series(df.index.date, index=df.index)
    pv = (typical * df["volume"]).groupby(day).cumsum()
    vol = df["volume"].groupby(day).cumsum()
    return pv / vol.replace(0, np.nan)


def supertrend(df: pd.DataFrame, period: int = 10, mult: float = 3.0) -> pd.DataFrame:
    """Returns columns ``supertrend`` (the line) and ``direction`` (+1 up, -1 down)."""
    a = atr(df, period)
    hl2 = (df["high"] + df["low"]) / 2.0
    basic_up = (hl2 + mult * a).to_numpy()
    basic_dn = (hl2 - mult * a).to_numpy()
    close = df["close"].to_numpy()
    n = len(df)
    final_up = np.full(n, np.nan)
    final_dn = np.full(n, np.nan)
    line = np.full(n, np.nan)
    direction = np.zeros(n)
    for i in range(n):
        if np.isnan(basic_up[i]):
            continue
        if i == 0 or np.isnan(final_up[i - 1]):
            final_up[i], final_dn[i] = basic_up[i], basic_dn[i]
            direction[i] = 1 if close[i] >= hl2.iloc[i] else -1
        else:
            final_up[i] = basic_up[i] if (basic_up[i] < final_up[i - 1] or close[i - 1] > final_up[i - 1]) else final_up[i - 1]
            final_dn[i] = basic_dn[i] if (basic_dn[i] > final_dn[i - 1] or close[i - 1] < final_dn[i - 1]) else final_dn[i - 1]
            if direction[i - 1] == 1:
                direction[i] = -1 if close[i] < final_dn[i] else 1
            else:
                direction[i] = 1 if close[i] > final_up[i] else -1
        line[i] = final_dn[i] if direction[i] == 1 else final_up[i]
    direction = np.where(np.isnan(line), np.nan, direction)
    return pd.DataFrame({"supertrend": line, "direction": direction}, index=df.index)


def adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    tr = _wilder(true_range(df), period)
    plus_di = 100.0 * _wilder(plus_dm, period) / tr
    minus_di = 100.0 * _wilder(minus_dm, period) / tr
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return pd.DataFrame({"adx": _wilder(dx, period), "plus_di": plus_di, "minus_di": minus_di})


def donchian(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """Highest high / lowest low of the *previous* ``period`` bars (excludes the current bar)."""
    return pd.DataFrame(
        {
            "upper": df["high"].rolling(period, min_periods=period).max().shift(1),
            "lower": df["low"].rolling(period, min_periods=period).min().shift(1),
        }
    )


def relative_volume(volume: pd.Series, period: int = 20) -> pd.Series:
    """Volume divided by the average of the previous ``period`` bars."""
    return volume / volume.rolling(period, min_periods=period).mean().shift(1)


def add_all(df: pd.DataFrame, intraday: bool = False) -> pd.DataFrame:
    """Convenience: a copy of ``df`` with the common indicator columns attached."""
    out = df.copy()
    c = out["close"]
    for p in (9, 21, 50, 200):
        out[f"ema{p}"] = ema(c, p)
    out["sma200"] = sma(c, 200)
    out["rsi14"] = rsi(c, 14)
    out["rsi2"] = rsi(c, 2)
    m = macd(c)
    out["macd"], out["macd_signal"], out["macd_hist"] = m["macd"], m["signal"], m["hist"]
    out["atr14"] = atr(out, 14)
    bb = bollinger(c)
    out["bb_mid"], out["bb_upper"], out["bb_lower"] = bb["mid"], bb["upper"], bb["lower"]
    st = supertrend(out)
    out["supertrend"], out["st_dir"] = st["supertrend"], st["direction"]
    ax = adx(out)
    out["adx"], out["plus_di"], out["minus_di"] = ax["adx"], ax["plus_di"], ax["minus_di"]
    out["rvol"] = relative_volume(out["volume"])
    if intraday:
        out["vwap"] = vwap(out)
    return out
