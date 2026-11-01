"""Long-only trading strategies built from the indicators module.

A strategy turns a candle DataFrame into a signal DataFrame with columns:

  ``entry``  bool   go long at the *next* bar's open (decided on this bar's close)
  ``exit``   bool   close any open position at the next bar's open
  ``stop``   float  initial protective stop for an entry on this bar
  ``target`` float  profit target for an entry on this bar (NaN = none, ride the exit signal)

Signals only use completed bars, so the backtester and the live engine behave
the same way: decide on a closed candle, act on the next one.

These are well-known, documented setups, not secret edges. None of them is
guaranteed to make money; run ``growwbot backtest`` on your own symbols, with
costs, before you trust any of them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from typing import Callable

import numpy as np
import pandas as pd

from . import indicators as ind


@dataclass(frozen=True)
class Strategy:
    name: str
    description: str
    interval: str          # Groww candle interval, e.g. "1day", "5minute", "15minute"
    intraday: bool         # True -> MIS product, squared off the same day
    fn: Callable[..., pd.DataFrame]
    defaults: dict = field(default_factory=dict)
    max_hold_bars: int | None = None

    @property
    def product(self) -> str:
        return "MIS" if self.intraday else "CNC"

    def signals(self, df: pd.DataFrame, **overrides) -> pd.DataFrame:
        params = {**self.defaults, **overrides}
        out = self.fn(df, **params)
        out["entry"] = out["entry"].fillna(False).astype(bool)
        out["exit"] = out["exit"].fillna(False).astype(bool)
        # An entry needs a valid stop below the signal close.
        bad = out["entry"] & ~(out["stop"] < df["close"])
        out.loc[bad, "entry"] = False
        return out[["entry", "exit", "stop", "target"]]


def _cross_above(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a > b) & (a.shift(1) <= b.shift(1))


def _cross_below(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a < b) & (a.shift(1) >= b.shift(1))


# --------------------------------------------------------------------------- swing (daily, CNC)

def ema_trend(df, fast=9, slow=21, trend=200, adx_min=20.0, rsi_lo=50.0, rsi_hi=70.0,
              stop_atr=2.0, target_atr=4.0):
    """EMA crossover in the direction of the long-term trend, confirmed by ADX and RSI."""
    c = df["close"]
    f, s, t = ind.ema(c, fast), ind.ema(c, slow), ind.ema(c, trend)
    a = ind.atr(df, 14)
    adx = ind.adx(df)["adx"]
    r = ind.rsi(c, 14)
    entry = _cross_above(f, s) & (c > t) & (adx >= adx_min) & r.between(rsi_lo, rsi_hi)
    return pd.DataFrame({
        "entry": entry,
        "exit": _cross_below(f, s),
        "stop": c - stop_atr * a,
        "target": c + target_atr * a,
    })


def supertrend_adx(df, st_period=10, st_mult=3.0, adx_min=20.0, trend=50, rvol_min=1.2, rr=2.0):
    """Supertrend flips up, with ADX trend strength, above the EMA, on above-average volume."""
    c = df["close"]
    st = ind.supertrend(df, st_period, st_mult)
    adx = ind.adx(df)["adx"]
    rvol = ind.relative_volume(df["volume"])
    flip_up = (st["direction"] == 1) & (st["direction"].shift(1) == -1)
    entry = flip_up & (adx >= adx_min) & (c > ind.ema(c, trend)) & (rvol >= rvol_min)
    stop = st["supertrend"]
    return pd.DataFrame({
        "entry": entry,
        "exit": (st["direction"] == -1) & (st["direction"].shift(1) == 1),
        "stop": stop,
        "target": c + rr * (c - stop),
    })


def rsi2_reversion(df, rsi_entry=10.0, rsi_exit=70.0, trend=200, exit_sma=5, stop_atr=2.5):
    """Larry Connors' RSI(2) pullback: buy short-term oversold dips inside a long-term uptrend."""
    c = df["close"]
    r2 = ind.rsi(c, 2)
    a = ind.atr(df, 14)
    entry = (c > ind.sma(c, trend)) & (r2 < rsi_entry)
    exit_ = (c > ind.sma(c, exit_sma)) | (r2 > rsi_exit)
    return pd.DataFrame({
        "entry": entry,
        "exit": exit_,
        "stop": c - stop_atr * a,
        "target": np.nan,
    })


def macd_momentum(df, trend_fast=50, trend_slow=200, rsi_min=50.0, stop_atr=2.0, target_atr=4.0):
    """MACD line crosses its signal while the 50 EMA is above the 200 EMA."""
    c = df["close"]
    m = ind.macd(c)
    e50, e200 = ind.ema(c, trend_fast), ind.ema(c, trend_slow)
    a = ind.atr(df, 14)
    entry = _cross_above(m["macd"], m["signal"]) & (c > e50) & (e50 > e200) & (ind.rsi(c, 14) > rsi_min)
    return pd.DataFrame({
        "entry": entry,
        "exit": _cross_below(m["macd"], m["signal"]),
        "stop": c - stop_atr * a,
        "target": c + target_atr * a,
    })


def donchian_breakout(df, period=20, exit_period=10, trend=50, rvol_min=1.5, stop_atr=2.0):
    """Turtle-style breakout: close above the prior 20-bar high on strong volume."""
    c = df["close"]
    d = ind.donchian(df, period)
    d_exit = ind.donchian(df, exit_period)
    a = ind.atr(df, 14)
    entry = (c > d["upper"]) & (c > ind.ema(c, trend)) & (ind.relative_volume(df["volume"]) >= rvol_min)
    return pd.DataFrame({
        "entry": entry,
        "exit": c < d_exit["lower"],
        "stop": c - stop_atr * a,
        "target": np.nan,
    })


# --------------------------------------------------------------------------- intraday (MIS)

def _bar_time(df) -> pd.Series:
    return pd.Series([ts.time() for ts in df.index], index=df.index)


def vwap_pullback(df, rsi_lo=45.0, rsi_hi=65.0, lookback=3, rr=2.0, last_entry="14:30"):
    """Intraday trend-pullback: above VWAP, EMA9 > EMA21, dip to EMA21/VWAP, bullish close."""
    c, lo = df["close"], df["low"]
    v = ind.vwap(df)
    e9, e21 = ind.ema(c, 9), ind.ema(c, 21)
    a = ind.atr(df, 14)
    r = ind.rsi(c, 14)
    touched = (lo.shift(1) <= e21.shift(1) * 1.001) | (lo.shift(1) <= v.shift(1) * 1.001)
    bullish = (c > df["open"]) & (c > e9)
    t = _bar_time(df)
    in_window = (t >= time(9, 30)) & (t <= time.fromisoformat(last_entry))
    entry = (c > v) & (e9 > e21) & touched & bullish & r.between(rsi_lo, rsi_hi) & in_window
    stop = pd.concat([lo.rolling(lookback).min(), v], axis=1).min(axis=1) - 0.1 * a
    return pd.DataFrame({
        "entry": entry,
        "exit": c < v,
        "stop": stop,
        "target": c + rr * (c - stop),
    })


def opening_range_breakout(df, range_minutes=15, last_entry="11:00", rvol_min=1.5, rr=2.0):
    """First close above the 09:15 opening range, above VWAP, on high relative volume.

    Stop at the middle of the opening range; one entry per day at most.
    """
    t = _bar_time(df)
    day = pd.Series(df.index.date, index=df.index)
    start = time(9, 15)
    end_minute = 15 + range_minutes
    range_end = time(9 + end_minute // 60, end_minute % 60)
    in_range = (t >= start) & (t < range_end)
    or_high = df["high"].where(in_range).groupby(day).transform("max")
    or_low = df["low"].where(in_range).groupby(day).transform("min")
    c = df["close"]
    v = ind.vwap(df)
    rvol = ind.relative_volume(df["volume"])
    after = (t >= range_end) & (t <= time.fromisoformat(last_entry))
    breakout = after & (c > or_high) & (c > v) & (rvol >= rvol_min)
    first = breakout & (breakout.astype(int).groupby(day).cumsum() == 1)
    stop = (or_high + or_low) / 2.0
    return pd.DataFrame({
        "entry": first,
        "exit": c < v,
        "stop": stop,
        "target": c + rr * (c - stop),
    })


# --------------------------------------------------------------------------- v2 (Nov 2026)
# Rewrites of the strategies that lost money in docs/14-historical-validation.md.
# Each change was decided from *why* the original lost (costs, cut winners,
# churn), then judged on stocks and years the change was not designed on.
# Results: docs/15-strategy-v2.md. The originals stay for comparison.

def _chandelier_exit(df, period=22, mult=3.0):
    """Close below the highest high of the last ``period`` bars minus ``mult`` ATRs."""
    a = ind.atr(df, period)
    return df["close"] < df["high"].rolling(period, min_periods=period).max() - mult * a


def ema_trend_v2(df, fast=20, slow=50, trend=200, adx_min=20.0, stop_atr=3.0, trail=22, trail_atr=3.0):
    """Slower EMA 20/50 cross above the 200 EMA; no profit target, Chandelier trailing exit.

    v1 lost because the 9/21 cross-back exit and a fixed 4 ATR target cut the few
    big winners a trend strategy lives on, and its many short trades paid charges each time.
    """
    c = df["close"]
    f, s, t = ind.ema(c, fast), ind.ema(c, slow), ind.ema(c, trend)
    a = ind.atr(df, 14)
    entry = _cross_above(f, s) & (c > t) & (ind.adx(df)["adx"] >= adx_min)
    return pd.DataFrame({
        "entry": entry,
        "exit": _chandelier_exit(df, trail, trail_atr) | (c < t),
        "stop": c - stop_atr * a,
        "target": np.nan,
    })


def macd_momentum_v2(df, trend_fast=50, trend_slow=200, stop_atr=3.0, trail=22, trail_atr=3.0):
    """MACD crosses up from *below zero* (a pullback ending) in a 50>200 EMA uptrend;
    no target, Chandelier trailing exit instead of the MACD cross-back."""
    c = df["close"]
    m = ind.macd(c)
    e50, e200 = ind.ema(c, trend_fast), ind.ema(c, trend_slow)
    a = ind.atr(df, 14)
    entry = _cross_above(m["macd"], m["signal"]) & (m["macd"] < 0) & (c > e50) & (e50 > e200)
    return pd.DataFrame({
        "entry": entry,
        "exit": _chandelier_exit(df, trail, trail_atr) | (c < e200),
        "stop": c - stop_atr * a,
        "target": np.nan,
    })


def donchian_breakout_v2(df, period=55, exit_period=20, trend=200, stop_atr=3.0):
    """Classic Turtle System 2: 55-day breakout above the 200 EMA, exit at the 20-day low.

    v1's 20/10 channels traded about twice as often for the same trend, paying charges each time.
    """
    c = df["close"]
    d = ind.donchian(df, period)
    d_exit = ind.donchian(df, exit_period)
    a = ind.atr(df, 20)
    entry = (c > d["upper"]) & (c > ind.ema(c, trend))
    return pd.DataFrame({
        "entry": entry,
        "exit": c < d_exit["lower"],
        "stop": c - stop_atr * a,
        "target": np.nan,
    })


def rsi2_reversion_v2(df, rsi_entry=5.0, trend=200, exit_sma=5, stop_atr=3.0, min_drop_atr=1.5):
    """RSI(2) < 5 dip-buy above the 200 SMA, only after a real pullback (close at least
    1.5 ATR under its 5-day high), so the expected bounce is big enough to pay delivery charges.
    Exit above the 5 SMA, max 5 bars."""
    c = df["close"]
    a = ind.atr(df, 14)
    pullback = df["high"].rolling(5).max() - c >= min_drop_atr * a
    entry = (c > ind.sma(c, trend)) & (ind.rsi(c, 2) < rsi_entry) & pullback
    return pd.DataFrame({
        "entry": entry,
        "exit": c > ind.sma(c, exit_sma),
        "stop": c - stop_atr * a,
        "target": np.nan,
    })


def vwap_pullback_v2(df, rsi_lo=45.0, rsi_hi=65.0, lookback=3, rr=2.0, last_entry="13:30", min_stop_atr=1.0):
    """v1 entry, but no exit on the first close below VWAP (it fired within a few bars
    on most trades), a stop at least 1 ATR wide so charges are a small share of the risk,
    one entry per day per stock. Exits: stop, 2R target or the 15:10 square-off."""
    c, lo = df["close"], df["low"]
    v = ind.vwap(df)
    e9, e21 = ind.ema(c, 9), ind.ema(c, 21)
    a = ind.atr(df, 14)
    touched = (lo.shift(1) <= e21.shift(1) * 1.001) | (lo.shift(1) <= v.shift(1) * 1.001)
    t = _bar_time(df)
    day = pd.Series(df.index.date, index=df.index)
    in_window = (t >= time(9, 45)) & (t <= time.fromisoformat(last_entry))
    raw = (c > v) & (e9 > e21) & touched & (c > df["open"]) & (c > e9) & ind.rsi(c, 14).between(rsi_lo, rsi_hi) & in_window
    entry = raw & (raw.astype(int).groupby(day).cumsum() == 1)
    stop = pd.concat([lo.rolling(lookback).min(), v, c - min_stop_atr * a], axis=1).min(axis=1) - 0.1 * a
    return pd.DataFrame({"entry": entry, "exit": False, "stop": stop, "target": c + rr * (c - stop)})


def opening_range_breakout_v2(df, range_minutes=30, last_entry="11:30", rvol_min=1.5, rr=2.0):
    """30-minute opening range; stop at the range low, 2R target, no VWAP exit, one entry a day."""
    t = _bar_time(df)
    day = pd.Series(df.index.date, index=df.index)
    end_minute = 15 + range_minutes
    range_end = time(9 + end_minute // 60, end_minute % 60)
    in_range = (t >= time(9, 15)) & (t < range_end)
    or_high = df["high"].where(in_range).groupby(day).transform("max")
    or_low = df["low"].where(in_range).groupby(day).transform("min")
    c = df["close"]
    after = (t >= range_end) & (t <= time.fromisoformat(last_entry))
    breakout = after & (c > or_high) & (c > ind.vwap(df)) & (ind.relative_volume(df["volume"]) >= rvol_min)
    first = breakout & (breakout.astype(int).groupby(day).cumsum() == 1)
    return pd.DataFrame({"entry": first, "exit": False, "stop": or_low, "target": c + rr * (c - or_low)})


STRATEGIES: dict[str, Strategy] = {
    s.name: s
    for s in [
        Strategy("ema_trend", "EMA 9/21 crossover above the 200 EMA, ADX >= 20, RSI 50-70", "1day", False, ema_trend),
        Strategy("supertrend_adx", "Supertrend(10,3) flips up, ADX >= 20, above EMA50, RVOL >= 1.2", "1day", False, supertrend_adx),
        Strategy("rsi2_reversion", "Connors RSI(2) < 10 dip-buy above the 200 SMA, exit above the 5 SMA", "1day", False, rsi2_reversion, max_hold_bars=10),
        Strategy("macd_momentum", "MACD crosses signal with EMA50 > EMA200 and RSI > 50", "1day", False, macd_momentum),
        Strategy("donchian_breakout", "20-day high breakout on volume, exit at the 10-day low", "1day", False, donchian_breakout),
        Strategy("vwap_pullback", "Intraday pullback to VWAP/EMA21 in an uptrend (5-minute)", "5minute", True, vwap_pullback),
        Strategy("orb", "15-minute opening-range breakout above VWAP on volume (5-minute)", "5minute", True, opening_range_breakout),
        Strategy("ema_trend_v2", "EMA 20/50 cross above the 200 EMA, ADX >= 20, Chandelier trailing exit", "1day", False, ema_trend_v2),
        Strategy("macd_momentum_v2", "MACD crosses up below zero in a 50>200 EMA uptrend, Chandelier trailing exit", "1day", False, macd_momentum_v2),
        Strategy("donchian_breakout_v2", "Turtle 55-day breakout above the 200 EMA, exit at the 20-day low", "1day", False, donchian_breakout_v2),
        Strategy("rsi2_reversion_v2", "RSI(2) < 5 after a 1.5 ATR pullback above the 200 SMA, exit above the 5 SMA", "1day", False, rsi2_reversion_v2, max_hold_bars=5),
        Strategy("vwap_pullback_v2", "VWAP/EMA21 pullback, wider stop, no VWAP exit, one entry a day (5-minute)", "5minute", True, vwap_pullback_v2),
        Strategy("orb_v2", "30-minute opening-range breakout, stop at the range low, 2R target (5-minute)", "5minute", True, opening_range_breakout_v2),
    ]
}


def get(name: str) -> Strategy:
    try:
        return STRATEGIES[name]
    except KeyError:
        raise SystemExit(f"Unknown strategy '{name}'. Choose from: {', '.join(STRATEGIES)}")
