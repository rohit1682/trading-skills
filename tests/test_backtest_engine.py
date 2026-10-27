from datetime import datetime

import pandas as pd
import pytest

from growwbot import backtest as bt
from growwbot import broker as brk
from growwbot import config, data, engine, risk, strategies
from tests.conftest import make_daily


def universe():
    return {f"S{i}": make_daily(seed=i) for i in range(4)}


def test_backtest_runs_and_accounts_costs():
    res = bt.run(universe(), strategies.get("ema_trend"), initial_capital=100_000)
    m = res.metrics()
    assert m["trades"] > 0
    assert m["total_costs"] > 0
    # Final equity must equal capital + net P&L of all closed trades.
    assert m["final_equity"] == pytest.approx(100_000 + sum(t.pnl for t in res.trades), abs=1.0)


def test_all_strategies_backtest(intraday):
    for s in strategies.STRATEGIES.values():
        data_ = {"X": intraday} if s.intraday else universe()
        res = bt.run(data_, s, initial_capital=100_000)
        assert len(res.equity) > 0, s.name
        if s.intraday:
            # nothing held overnight
            assert all(t.entry_time.date() == t.exit_time.date() for t in res.trades), s.name


def test_risk_limits_respected_in_backtest():
    res = bt.run(universe(), strategies.get("supertrend_adx"), risk_cfg={"max_open_positions": 1},
                 initial_capital=100_000)
    spans = sorted((t.entry_time, t.exit_time) for t in res.trades)
    for (a0, a1), (b0, _) in zip(spans, spans[1:]):
        assert b0 >= a1  # never two positions at once


def test_split_out_of_sample():
    u = universe()
    cut = bt.cut_point(u, 0.7)
    oos = bt.run(u, strategies.get("ema_trend"), start=cut)
    assert all(t.entry_time >= cut for t in oos.trades)


def test_live_gate_requires_all_three(monkeypatch):
    cfg = config.load()
    assert isinstance(brk.make_broker(cfg, live_flag=False), brk.PaperBroker)
    with pytest.raises(brk.LiveTradingNotAllowed):
        brk.make_broker(cfg, live_flag=True)
    cfg.mode = "live"
    with pytest.raises(brk.LiveTradingNotAllowed):
        brk.make_broker(cfg, live_flag=True)  # env ack missing
    monkeypatch.setenv("GROWW_ENABLE_LIVE", "yes")
    with pytest.raises(brk.LiveTradingNotAllowed):
        brk.make_broker(cfg, live_flag=True)  # wrong ack text
    monkeypatch.setenv("GROWW_ENABLE_LIVE", config.LIVE_ACK)
    assert isinstance(brk.make_broker(cfg, live_flag=True), brk.GrowwBroker)
    cfg.mode = "paper"
    assert isinstance(brk.make_broker(cfg, live_flag=False), brk.PaperBroker)


def test_reference_id_format():
    for _ in range(50):
        r = brk.new_reference_id()
        assert 8 <= len(r) <= 20 and r.replace("-", "").isalnum() and r.count("-") <= 2


def test_tick_rounding():
    assert brk.round_to_tick(1234.567, 0.10) == 1234.5
    assert brk.round_to_tick(99.999, 0.01) == 99.99
    assert brk.round_to_tick(512.33, 0.05) == 512.30


class FakeData:
    """Feeds the engine a fixed daily history and price, so no network is used."""

    def __init__(self, df):
        self.df = df

    def load(self, symbol, interval, days=365, source="auto", csv=None):
        return self.df

    def completed_bars(self, df, interval, now=None):
        return df


def _engine(monkeypatch, df, price, strategy="ema_trend"):
    cfg = config.load()
    cfg.watchlist = ["AAA"]
    cfg.strategy = {"name": strategy, "params": {}}
    cfg.risk = {**cfg.risk, "regime_filter": False}
    fake = FakeData(df)
    monkeypatch.setattr(engine.data, "load", fake.load)
    monkeypatch.setattr(engine.data, "completed_bars", fake.completed_bars)
    eng = engine.Engine(cfg, brk.PaperBroker(cfg), log=lambda *_: None)
    monkeypatch.setattr(eng, "prices", lambda syms: {s: price for s in syms})
    return eng


def _df_with_entry_on_last_bar():
    s = strategies.get("ema_trend")
    df = make_daily(seed=11)
    sig = s.signals(df)
    last_entry = sig.index[sig["entry"]][-1]
    return df.loc[:last_entry], s.signals(df.loc[:last_entry]).iloc[-1]


def test_engine_paper_entry_then_stop(monkeypatch):
    df, sig = _df_with_entry_on_last_bar()
    px = float(df["close"].iloc[-1])
    eng = _engine(monkeypatch, df, px)
    eng.step(datetime(2026, 10, 27, 9, 30))
    assert "AAA" in eng.positions
    pos = eng.positions["AAA"]
    assert pos["stop"] == pytest.approx(float(sig["stop"]))
    # price drops through the stop -> exit, journaled, risk state updated
    monkeypatch.setattr(eng, "prices", lambda syms: {s: pos["stop"] - 1 for s in syms})
    eng.step(datetime(2026, 10, 27, 11, 0))
    assert "AAA" not in eng.positions
    journal = pd.read_csv(eng.journal_path)
    assert journal.iloc[-1]["reason"] == "stop" and journal.iloc[-1]["pnl_gross"] < 0
    assert eng.rm.day.realised_pnl < 0


def test_engine_respects_kill_switch(monkeypatch):
    df, _ = _df_with_entry_on_last_bar()
    eng = _engine(monkeypatch, df, float(df["close"].iloc[-1]))
    risk.engage_kill_switch("test")
    eng.step(datetime(2026, 10, 27, 9, 30))
    assert eng.positions == {}


def test_engine_daily_loss_breaker_flattens(monkeypatch):
    df, _ = _df_with_entry_on_last_bar()
    px = float(df["close"].iloc[-1])
    eng = _engine(monkeypatch, df, px)
    eng.step(datetime(2026, 10, 27, 9, 30))
    assert eng.positions
    eng.rm.day.realised_pnl = -eng.rm.daily_loss_limit()  # pretend earlier trades lost the limit
    eng.step(datetime(2026, 10, 27, 12, 0))
    assert risk.kill_switch_active()
    assert eng.positions == {}


def test_completed_bars_drops_forming_candle(intraday):
    last = intraday.index[-1]
    assert len(data.completed_bars(intraday, "5minute", now=last + pd.Timedelta(minutes=2))) == len(intraday) - 1
    assert len(data.completed_bars(intraday, "5minute", now=last + pd.Timedelta(minutes=6))) == len(intraday)


def test_market_hours():
    assert engine.market_open(datetime(2026, 10, 27, 10, 0))
    assert not engine.market_open(datetime(2026, 10, 25, 10, 0))  # Sunday
    assert not engine.market_open(datetime(2026, 10, 27, 16, 0))
    assert not engine.market_open(datetime(2026, 10, 27, 10, 0), holidays=["2026-10-27"])


def test_engine_intraday_entry_and_squareoff(monkeypatch, intraday):
    s = strategies.get("vwap_pullback")
    sig = s.signals(intraday)
    entries = sig.index[sig["entry"]]
    last_entry = [t for t in entries if t.hour < 14][-1]  # inside the 09:30-14:30 entry window
    df = intraday.loc[:last_entry]
    px = float(df["close"].iloc[-1])
    eng = _engine(monkeypatch, df, px, strategy="vwap_pullback")
    now = last_entry.to_pydatetime() + pd.Timedelta(minutes=6)
    eng.step(now)
    assert eng.positions["AAA"]["intraday"] is True
    eng.step(now.replace(hour=15, minute=11))
    assert "AAA" not in eng.positions
    assert pd.read_csv(eng.journal_path).iloc[-1]["reason"] == "square-off"
