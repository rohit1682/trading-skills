"""Exercise the live code path against a fake Groww SDK (no network, no real orders)."""

from datetime import datetime

import pytest

from growwbot import broker as brk
from growwbot import config, engine
from growwbot.groww_client import Groww
from tests.test_backtest_engine import FakeData, _df_with_entry_on_last_bar


class FakeSDK:
    def __init__(self):
        self.orders = {}
        self.calls = []
        self.position_qty = {}
        self.n = 0
        self.market_price = 1000.0

    def place_order(self, **kw):
        self.calls.append(("place_order", kw))
        self.n += 1
        oid = f"GMK{self.n}"
        status = "OPEN" if kw["order_type"] == "SL_M" else "EXECUTED"
        price = kw.get("price") or self.market_price
        self.orders[oid] = {**kw, "order_status": status, "filled_quantity": kw["quantity"] if status == "EXECUTED" else 0,
                            "average_fill_price": price}
        if status == "EXECUTED":
            sign = 1 if kw["transaction_type"] == "BUY" else -1
            self.position_qty[kw["trading_symbol"]] = self.position_qty.get(kw["trading_symbol"], 0) + sign * kw["quantity"]
        return {"groww_order_id": oid, "order_status": status}

    def get_order_status(self, groww_order_id, segment):
        return self.orders[groww_order_id]

    def get_order_detail(self, groww_order_id, segment):
        return self.orders[groww_order_id]

    def cancel_order(self, segment, groww_order_id):
        self.calls.append(("cancel_order", groww_order_id))
        self.orders[groww_order_id]["order_status"] = "CANCELLED"
        return {"order_status": "CANCELLED"}

    def get_available_margin_details(self):
        return {"clear_cash": 100000.0, "equity_margin_details": {"cnc_balance_available": 100000.0}}

    def get_instrument_by_exchange_and_trading_symbol(self, exchange, trading_symbol):
        return {"tick_size": 0.05}

    def get_positions_for_user(self, segment=None):
        return {"positions": [{"trading_symbol": s, "quantity": q} for s, q in self.position_qty.items()]}

    def get_holdings_for_user(self, timeout=None):
        return {"holdings": []}

    def get_order_list(self, segment=None, page=None, page_size=None):
        return {"order_list": list(self.orders.values())}


@pytest.fixture
def live_engine(monkeypatch):
    monkeypatch.setenv("GROWW_ENABLE_LIVE", config.LIVE_ACK)
    cfg = config.load()
    cfg.mode = "live"
    cfg.watchlist = ["AAA"]
    cfg.strategy = {"name": "ema_trend", "params": {}}
    cfg.risk = {**cfg.risk, "regime_filter": False}
    sdk = FakeSDK()
    monkeypatch.setattr(Groww, "api", property(lambda self: sdk))
    df, _ = _df_with_entry_on_last_bar()
    fake = FakeData(df)
    monkeypatch.setattr(engine.data, "load", fake.load)
    monkeypatch.setattr(engine.data, "completed_bars", fake.completed_bars)
    b = brk.make_broker(cfg, live_flag=True)
    eng = engine.Engine(cfg, b, log=lambda *_: None)
    px = float(df["close"].iloc[-1])
    sdk.market_price = px
    monkeypatch.setattr(eng, "prices", lambda syms: {s: px for s in syms})
    return eng, sdk, px


def test_live_entry_places_order_and_broker_stop(live_engine):
    eng, sdk, px = live_engine
    eng.step(datetime(2026, 10, 27, 9, 30))
    kinds = [(c[1]["order_type"], c[1]["transaction_type"]) for c in sdk.calls if c[0] == "place_order"]
    assert kinds == [("MARKET", "BUY"), ("SL_M", "SELL")]
    sl = [c[1] for c in sdk.calls if c[0] == "place_order"][1]
    assert sl["product"] == "CNC" and sl["validity"] == "DAY"
    assert round(sl["trigger_price"] / 0.05, 6).is_integer()
    assert eng.positions["AAA"]["stop_order_id"]


def test_live_stop_is_left_to_broker_then_reconciled(live_engine, monkeypatch):
    eng, sdk, px = live_engine
    eng.step(datetime(2026, 10, 27, 9, 30))
    pos = eng.positions["AAA"]
    n_calls = len(sdk.calls)
    monkeypatch.setattr(eng, "prices", lambda syms: {s: pos["stop"] - 1 for s in syms})
    eng.step(datetime(2026, 10, 27, 10, 0))
    assert len(sdk.calls) == n_calls  # bot did not send its own sell: the SL-M is working
    # broker stop fills -> position disappears at Groww -> reconcile books it
    sdk.position_qty["AAA"] = 0
    eng.step(datetime(2026, 10, 27, 10, 5))
    assert "AAA" not in eng.positions


def test_live_target_cancels_stop_then_sells(live_engine, monkeypatch):
    eng, sdk, px = live_engine
    eng.step(datetime(2026, 10, 27, 9, 30))
    pos = eng.positions["AAA"]
    sl_id = pos["stop_order_id"]
    monkeypatch.setattr(eng, "prices", lambda syms: {s: pos["target"] + 1 for s in syms})
    eng.step(datetime(2026, 10, 27, 11, 0))
    assert ("cancel_order", sl_id) in sdk.calls
    last = [c[1] for c in sdk.calls if c[0] == "place_order"][-1]
    assert last["transaction_type"] == "SELL" and last["order_type"] == "MARKET"
    assert "AAA" not in eng.positions
