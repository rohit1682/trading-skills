import numpy as np
import pandas as pd

from growwbot import indicators as ind
from growwbot import strategies


def test_rsi_extremes():
    up = pd.Series(np.arange(1, 60, dtype=float))
    assert ind.rsi(up, 14).iloc[-1] == 100.0
    down = pd.Series(np.arange(60, 1, -1, dtype=float))
    assert ind.rsi(down, 14).iloc[-1] < 1e-9
    flat = pd.Series(np.full(40, 10.0))
    assert ind.rsi(flat, 14).iloc[-1] == 50.0


def test_rsi_wilder_reference():
    # StockCharts' published RSI(14) worked example.
    closes = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08, 45.89, 46.03, 45.61,
              46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64]
    r = ind.rsi(pd.Series(closes), 14)
    assert r.round(2).tolist()[14:] == [70.46, 66.25, 66.48, 69.35, 66.29, 57.92]


def test_atr_constant_range():
    df = pd.DataFrame({"open": 100.0, "high": 102.0, "low": 98.0, "close": 100.0, "volume": 1}, index=range(50))
    assert abs(ind.atr(df, 14).iloc[-1] - 4.0) < 1e-9


def test_macd_hist_is_line_minus_signal(daily):
    m = ind.macd(daily["close"])
    assert np.allclose((m["macd"] - m["signal"]).dropna(), m["hist"].dropna())


def test_vwap_resets_each_day(intraday):
    v = ind.vwap(intraday)
    first_bars = intraday.groupby(intraday.index.date).head(1)
    tp = (first_bars["high"] + first_bars["low"] + first_bars["close"]) / 3
    assert np.allclose(v.loc[first_bars.index], tp)


def test_supertrend_follows_trend():
    n = 120
    up = np.linspace(100, 200, n // 2)
    down = np.linspace(200, 100, n // 2)
    c = np.r_[up, down]
    df = pd.DataFrame({"open": c, "high": c + 1, "low": c - 1, "close": c, "volume": 1.0},
                      index=pd.bdate_range("2024-01-01", periods=n))
    st = ind.supertrend(df)
    assert st["direction"].iloc[n // 2 - 5] == 1
    assert st["direction"].iloc[-1] == -1


def test_no_lookahead_in_any_strategy(daily, intraday):
    """Signals on a truncated history must equal the same bars computed on the full history."""
    for s in strategies.STRATEGIES.values():
        df = intraday if s.intraday else daily
        cut = int(len(df) * 0.7)
        full = s.signals(df)
        part = s.signals(df.iloc[:cut])
        a, b = full.iloc[:cut], part
        assert (a["entry"] == b["entry"]).all(), s.name
        assert (a["exit"] == b["exit"]).all(), s.name
        assert np.allclose(a["stop"].fillna(0), b["stop"].fillna(0)), s.name


def test_entries_have_stop_below_close(daily, intraday):
    for s in strategies.STRATEGIES.values():
        df = intraday if s.intraday else daily
        sig = s.signals(df)
        e = sig[sig["entry"]]
        assert (e["stop"] < df.loc[e.index, "close"]).all(), s.name


def test_strategies_fire_on_synthetic_data(daily, intraday):
    fired = {s.name: int(s.signals(intraday if s.intraday else daily)["entry"].sum()) for s in strategies.STRATEGIES.values()}
    assert sum(fired.values()) > 0, fired
