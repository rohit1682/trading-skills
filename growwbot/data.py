"""Candle loading: Groww historical API first, then yfinance, then local CSV.

All loaders return a DataFrame indexed by naive IST timestamps with columns
``open, high, low, close, volume``, sorted, without duplicates.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from . import config

IST = "Asia/Kolkata"

# Groww: max days per request for each interval.
GROWW_MAX_DAYS = {
    "1minute": 30, "2minute": 30, "3minute": 30, "5minute": 30,
    "10minute": 90, "15minute": 90, "30minute": 90,
    "1hour": 180, "4hour": 180, "1day": 180, "1week": 180, "1month": 180,
}
YF_INTERVAL = {"1minute": "1m", "2minute": "2m", "5minute": "5m", "15minute": "15m",
               "30minute": "30m", "1hour": "60m", "1day": "1d", "1week": "1wk", "1month": "1mo"}
YF_MAX_DAYS = {"1m": 7, "2m": 59, "5m": 59, "15m": 59, "30m": 59, "60m": 729}
INDEX_YF = {"NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK"}
COLS = ["open", "high", "low", "close", "volume"]


def is_intraday(interval: str) -> bool:
    return interval not in ("1day", "1week", "1month")


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df[COLS].astype(float)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df.dropna(subset=["open", "high", "low", "close"])


def _groww_rows_to_df(rows: list) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=COLS)
    df = pd.DataFrame([r[:6] for r in rows], columns=["ts", *COLS])
    if isinstance(df["ts"].iloc[0], (int, float)):
        idx = pd.to_datetime(df["ts"], unit="s", utc=True).dt.tz_convert(IST).dt.tz_localize(None)
    else:
        idx = pd.to_datetime(df["ts"])
    df.index = pd.DatetimeIndex(idx, name="ts")
    df["volume"] = df["volume"].fillna(0)
    return _clean(df)


def from_groww(symbol: str, interval: str, days: int, client=None, end: datetime | None = None) -> pd.DataFrame:
    from .groww_client import Groww

    client = client or Groww()
    end = end or datetime.now()
    start = end - timedelta(days=days)
    step = timedelta(days=GROWW_MAX_DAYS.get(interval, 30))
    frames, cur = [], start
    while cur < end:
        nxt = min(cur + step, end)
        rows = client.candles(symbol, interval, cur.strftime("%Y-%m-%d %H:%M:%S"), nxt.strftime("%Y-%m-%d %H:%M:%S"))
        frames.append(_groww_rows_to_df(rows))
        cur = nxt
    frames = [f for f in frames if not f.empty]
    return _clean(pd.concat(frames)) if frames else pd.DataFrame(columns=COLS)


def from_yfinance(symbol: str, interval: str, days: int) -> pd.DataFrame:
    import yfinance as yf

    yf_int = YF_INTERVAL.get(interval)
    if yf_int is None:
        raise ValueError(f"yfinance has no {interval} candles")
    days = min(days, YF_MAX_DAYS.get(yf_int, days))
    ticker = INDEX_YF.get(symbol, f"{symbol}.NS")
    raw = yf.download(ticker, period=f"{days}d", interval=yf_int, auto_adjust=False, progress=False, threads=False)
    if raw is None or raw.empty:
        return pd.DataFrame(columns=COLS)
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    raw = raw.rename(columns=str.lower)
    idx = raw.index
    if idx.tz is not None:
        idx = idx.tz_convert(IST).tz_localize(None)
    raw.index = pd.DatetimeIndex(idx, name="ts")
    return _clean(raw)


def from_csv(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.lower().strip() for c in df.columns]
    ts_col = next(c for c in df.columns if c in ("ts", "timestamp", "date", "datetime", "time"))
    df.index = pd.DatetimeIndex(pd.to_datetime(df.pop(ts_col)), name="ts")
    if df.index.tz is not None:
        df.index = df.index.tz_convert(IST).tz_localize(None)
    return _clean(df)


def load(symbol: str, interval: str = "1day", days: int = 365, source: str = "auto", csv: str | None = None) -> pd.DataFrame:
    """Load candles. ``source``: auto | groww | yfinance | csv."""
    if source == "csv" or csv:
        path = csv or config.home() / "data" / f"{symbol}_{interval}.csv"
        return from_csv(path)
    errors = []
    if source in ("auto", "groww"):
        from .groww_client import has_credentials

        if has_credentials():
            try:
                df = from_groww(symbol, interval, days)
                if not df.empty:
                    return df
                errors.append("groww: no candles")
            except Exception as e:  # network, auth, SDK missing
                errors.append(f"groww: {e}")
                if source == "groww":
                    raise
        elif source == "groww":
            raise RuntimeError("No Groww credentials in .env")
    if source in ("auto", "yfinance"):
        try:
            df = from_yfinance(symbol, interval, days)
            if not df.empty:
                return df
            errors.append("yfinance: no candles")
        except Exception as e:
            errors.append(f"yfinance: {e}")
    raise RuntimeError(f"Could not load {symbol} {interval}: " + "; ".join(errors))


def completed_bars(df: pd.DataFrame, interval: str, now: datetime | None = None) -> pd.DataFrame:
    """Drop the still-forming last candle so signals never repaint."""
    if df.empty:
        return df
    now = now or datetime.now()
    if is_intraday(interval):
        minutes = {"1minute": 1, "2minute": 2, "3minute": 3, "5minute": 5, "10minute": 10, "15minute": 15,
                   "30minute": 30, "1hour": 60, "4hour": 240}[interval]
        if df.index[-1] + timedelta(minutes=minutes) > now:
            return df.iloc[:-1]
        return df
    # Daily: today's bar is incomplete until the 15:30 close.
    last = df.index[-1]
    if last.date() == now.date() and now.time() < datetime.strptime("15:30", "%H:%M").time():
        return df.iloc[:-1]
    return df
