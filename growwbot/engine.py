"""The trading engine: turns signals into managed positions, paper or live.

One ``Engine.step()`` does:
  1. reconcile with the broker (live): notice positions a broker-side stop already closed
  2. manage exits: stop, target, exit signal, time stop, intraday square-off
  3. daily-loss breaker: trips the kill switch and flattens if the day's loss hits the limit
  4. look for entries on newly completed bars, if the kill switch is off

``run()`` repeats ``step()`` every ``poll_seconds`` during market hours.
Positions the bot did not open are never touched.
"""

from __future__ import annotations

import csv
import json
import math
import time as _time
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from . import config, data, risk, strategies
from .backtest import regime_series
from .costs import CostModel

IST = ZoneInfo("Asia/Kolkata")
MARKET_OPEN, MARKET_CLOSE = time(9, 15), time(15, 30)
JOURNAL_FIELDS = ["mode", "symbol", "strategy", "product", "qty", "entry_time", "entry", "stop", "target",
                  "exit_time", "exit", "reason", "pnl_gross", "r_multiple"]


def now_ist() -> datetime:
    return datetime.now(IST).replace(tzinfo=None)


def market_open(now: datetime, holidays: list[str] | None = None) -> bool:
    if now.weekday() >= 5 or now.date().isoformat() in set(holidays or []):
        return False
    return MARKET_OPEN <= now.time() <= MARKET_CLOSE


class Engine:
    def __init__(self, cfg: config.Config, broker, log=print):
        self.cfg = cfg
        self.broker = broker
        self.log = log
        self.mode = "live" if broker.live else "paper"
        self.strategy = strategies.get(cfg.strategy.get("name", "supertrend_adx"))
        self.params = cfg.strategy.get("params", {}) or {}
        self.rm = risk.RiskManager(cfg.risk, capital=cfg.capital, persist=True,
                                     costs=CostModel.from_dict(cfg.costs))
        self.state_path = config.state_dir() / f"positions_{self.mode}.json"
        self.journal_path = config.state_dir() / f"journal_{self.mode}.csv"
        self.state = self._load()
        self._regime_cache: tuple[date, bool] | None = None
        self._has_groww = False
        if broker.live:
            self._groww, self._has_groww = broker.g, True
        else:
            try:
                from .groww_client import Groww, has_credentials

                if has_credentials():  # paper mode can still use Groww's real-time prices
                    self._groww, self._has_groww = Groww(), True
            except Exception:
                self._has_groww = False

    # ---- persistence -------------------------------------------------------------
    def _load(self) -> dict:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text())
        return {"positions": {}, "last_bar": {}, "last_daily_eval": ""}

    def save(self) -> None:
        self.state_path.write_text(json.dumps(self.state, indent=2, default=str))

    @property
    def positions(self) -> dict:
        return self.state["positions"]

    def _journal(self, row: dict) -> None:
        new = not self.journal_path.exists()
        with self.journal_path.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=JOURNAL_FIELDS)
            if new:
                w.writeheader()
            w.writerow({k: row.get(k, "") for k in JOURNAL_FIELDS})

    # ---- market data ---------------------------------------------------------------
    def prices(self, symbols: list[str]) -> dict[str, float]:
        if not symbols:
            return {}
        if self._has_groww:
            try:
                return self._groww.ltp(symbols)
            except Exception as e:
                self.log(f"[warn] Groww LTP failed ({e}); falling back to last candle")
        out = {}
        for s in symbols:
            try:
                df = data.load(s, "1minute", days=2, source="yfinance")
                out[s] = float(df["close"].iloc[-1])
            except Exception as e:
                self.log(f"[warn] no price for {s}: {e}")
        return out

    def candles(self, symbol: str, now: datetime) -> pd.DataFrame:
        interval = self.strategy.interval
        days = 10 if data.is_intraday(interval) else 400
        df = data.load(symbol, interval, days=days)
        return data.completed_bars(df, interval, now)

    def regime_ok(self, today: date) -> bool:
        if not self.rm.cfg.get("regime_filter", True):
            return True
        if self._regime_cache and self._regime_cache[0] == today:
            return self._regime_cache[1]
        ok = True
        try:
            nifty = data.load("NIFTY", "1day", days=200)
            reg = regime_series(nifty)
            if reg:
                ok = reg.get(today, list(reg.values())[-1])
        except Exception as e:
            self.log(f"[warn] regime filter skipped, NIFTY data unavailable: {e}")
        self._regime_cache = (today, ok)
        return ok

    # ---- exits -----------------------------------------------------------------------
    def close(self, symbol: str, price: float, now: datetime, reason: str) -> bool:
        p = self.positions.get(symbol)
        if not p:
            return False
        sl_price = self.broker.stop_filled(p.get("stop_order_id", ""))
        if sl_price:  # the broker-side stop beat us to it; don't sell twice
            self._book_exit(symbol, sl_price, now, "broker stop")
            return True
        self.broker.cancel_stop(p.get("stop_order_id", ""))
        fill = self.broker.order(symbol, "SELL", p["qty"], price, p["intraday"])
        if not fill.ok:
            self.log(f"[ERROR] exit for {symbol} failed: {fill.message}. Check Groww now; re-placing stop.")
            if self.broker.live:
                p["stop_order_id"] = self.broker.place_stop(symbol, p["qty"], p["stop"], p["intraday"])
                self.save()
            return False
        self._book_exit(symbol, fill.price, now, reason)
        return True

    def _book_exit(self, symbol: str, price: float, now: datetime, reason: str) -> None:
        p = self.positions.pop(symbol)
        pnl = p["qty"] * (price - p["entry"])
        risk_ps = p["entry"] - p["initial_stop"]
        r = pnl / (p["qty"] * risk_ps) if risk_ps > 0 else 0.0
        self.rm.record_exit(pnl)
        self._journal({**p, "mode": self.mode, "symbol": symbol, "exit_time": now.isoformat(timespec="seconds"),
                       "exit": round(price, 2), "reason": reason, "pnl_gross": round(pnl, 2),
                       "r_multiple": round(r, 2), "product": "MIS" if p["intraday"] else "CNC"})
        self.save()
        self.log(f"EXIT {symbol} x{p['qty']} @ {price:.2f} ({reason}) P&L Rs {pnl:,.2f} before charges")

    def reconcile(self, now: datetime) -> None:
        """Live only: if Groww shows no position where we think we hold one, the broker stop filled."""
        if not self.broker.live or not self.positions:
            return
        try:
            held = {}
            for bp in self.broker.broker_positions():
                held[bp.get("trading_symbol")] = held.get(bp.get("trading_symbol"), 0) + int(bp.get("quantity") or 0)
            holdings = {}
            if any(not p["intraday"] for p in self.positions.values()):
                for h in (self._groww.call("get_holdings_for_user") or {}).get("holdings", []):
                    holdings[h.get("trading_symbol")] = float(h.get("quantity") or 0)
        except Exception as e:
            self.log(f"[warn] reconcile skipped: {e}")
            return
        for sym, p in list(self.positions.items()):
            qty = held.get(sym, 0) + (holdings.get(sym, 0) if not p["intraday"] else 0)
            if qty <= 0:
                self.log(f"{sym}: no longer held at Groww, assuming the broker stop filled at {p['stop']}")
                self._book_exit(sym, p["stop"], now, "broker stop")

    def manage_exits(self, now: datetime, prices: dict[str, float]) -> None:
        for sym, p in list(self.positions.items()):
            px = prices.get(sym)
            if px is None:
                continue
            if px <= p["stop"]:
                if self.broker.live and p.get("stop_order_id"):
                    if not self.broker.stop_dead(p["stop_order_id"]):
                        continue  # the SL-M at Groww handles it; reconcile() books the exit
                    self.log(f"[WARN] broker stop for {sym} is dead; exiting at market.")
                    p["stop_order_id"] = ""
                self.close(sym, px, now, "stop")
            elif p.get("target") and not math.isnan(p["target"]) and px >= p["target"]:
                self.close(sym, px, now, "target")
            elif p["intraday"] and self.rm.squareoff_due(now):
                self.close(sym, px, now, "square-off")

    def signal_exits(self, now: datetime, frames: dict[str, pd.DataFrame], prices: dict[str, float]) -> None:
        for sym, p in list(self.positions.items()):
            if p.get("strategy") != self.strategy.name or sym not in frames:
                continue
            df = frames[sym]
            sig = self.strategy.signals(df, **self.params)
            p["bars"] = int(p.get("bars", 0)) + 1
            reason = "exit signal" if bool(sig["exit"].iloc[-1]) else ""
            if not reason and self.strategy.max_hold_bars and p["bars"] >= self.strategy.max_hold_bars:
                reason = "time stop"
            if reason:
                self.close(sym, prices.get(sym, float(df["close"].iloc[-1])), now, reason)
        self.save()

    def flatten(self, now: datetime, reason: str, intraday_only: bool = False) -> None:
        syms = [s for s, p in self.positions.items() if p["intraday"] or not intraday_only]
        px = self.prices(syms)
        for s in syms:
            self.close(s, px.get(s, self.positions[s]["entry"]), now, reason)

    # ---- entries ---------------------------------------------------------------------
    def open_risk(self) -> float:
        return sum(p["qty"] * max(0.0, p["entry"] - p["stop"]) for p in self.positions.values())

    def try_entry(self, symbol: str, df: pd.DataFrame, price: float, now: datetime, regime_ok: bool) -> None:
        sig = self.strategy.signals(df, **self.params).iloc[-1]
        if not bool(sig["entry"]):
            return
        stop, target = float(sig["stop"]), float(sig["target"])
        tgt = None if math.isnan(target) else target
        cash = self.broker.cash()
        dec = self.rm.check_entry(symbol, price, stop, tgt, now, len(self.positions), self.strategy.intraday,
                                  cash=min(cash, self.cfg.capital), open_risk=self.open_risk(),
                                  signal_close=float(df["close"].iloc[-1]), regime_ok=regime_ok)
        self.log(f"SIGNAL {symbol} {self.strategy.name} price {price:.2f} stop {stop:.2f} "
                 f"target {('-' if tgt is None else f'{tgt:.2f}')}: {dec}")
        if dec.ok:
            self.open(symbol, dec.qty, price, stop, tgt, now, self.strategy.intraday, self.strategy.name)

    def open(self, symbol, qty, price, stop, target, now, intraday, strategy_name) -> bool:
        fill = self.broker.order(symbol, "BUY", qty, price, intraday)
        if not fill.ok:
            self.log(f"[warn] entry {symbol} not filled: {fill.status} {fill.message}")
            return False
        self.rm.record_entry()
        if fill.price <= stop:  # filled through the stop: get straight out
            self.positions[symbol] = dict(qty=fill.qty, entry=fill.price, stop=stop, initial_stop=stop,
                                          target=target, intraday=intraday, strategy=strategy_name,
                                          entry_time=now.isoformat(timespec="seconds"), stop_order_id="", bars=0)
            self.close(symbol, fill.price, now, "filled below stop")
            return False
        sl_id = ""
        if self.broker.live and (self.cfg.execution or {}).get("place_broker_stop", True):
            sl_id = self.broker.place_stop(symbol, fill.qty, stop, intraday)
            if not sl_id:
                self.log(f"[WARN] broker stop for {symbol} was NOT placed; the bot will watch the stop itself.")
        self.positions[symbol] = dict(qty=fill.qty, entry=fill.price, stop=stop, initial_stop=stop,
                                      target=target if target is not None else float("nan"),
                                      intraday=intraday, strategy=strategy_name,
                                      entry_time=now.isoformat(timespec="seconds"), stop_order_id=sl_id, bars=0,
                                      stop_day=now.date().isoformat())
        self.save()
        self.log(f"ENTRY {symbol} x{fill.qty} @ {fill.price:.2f} stop {stop:.2f} ({self.mode})")
        return True

    def refresh_overnight_stops(self, now: datetime) -> None:
        """CNC stops are DAY orders at Groww; place a fresh one each morning."""
        if not self.broker.live:
            return
        for sym, p in self.positions.items():
            if not p["intraday"] and p.get("stop_day") != now.date().isoformat():
                p["stop_order_id"] = self.broker.place_stop(sym, p["qty"], p["stop"], False)
                p["stop_day"] = now.date().isoformat()
        self.save()

    # ---- main step -------------------------------------------------------------------
    def step(self, now: datetime | None = None) -> None:
        now = now or now_ist()
        self.rm.roll_day(now.date())
        self.reconcile(now)
        self.refresh_overnight_stops(now)

        watch = list(dict.fromkeys(self.cfg.watchlist + list(self.positions)))
        prices = self.prices(watch)
        self.manage_exits(now, prices)

        unreal = sum(p["qty"] * (prices.get(s, p["entry"]) - p["entry"]) for s, p in self.positions.items())
        if self.rm.breached_daily_loss(unreal) and not risk.kill_switch_active():
            risk.engage_kill_switch("daily loss limit hit")
            self.log("DAILY LOSS LIMIT HIT: kill switch engaged, flattening all bot positions.")
            self.flatten(now, "daily loss limit")
            return

        # Decide which bars are new.
        intraday = self.strategy.intraday
        if not intraday:
            if self.state.get("last_daily_eval") == now.date().isoformat() or now.time() < time(9, 20):
                return
        frames: dict[str, pd.DataFrame] = {}
        newest_closed = None
        if intraday:  # start of the most recent bar that has fully closed
            step = pd.Timedelta(self.strategy.interval.replace("minute", "min").replace("hour", "h"))
            newest_closed = (pd.Timestamp(now).floor(step) - step).isoformat()
        for sym in watch:
            if newest_closed and self.state["last_bar"].get(sym, "") >= newest_closed:
                continue  # nothing new yet; save an API call
            try:
                df = self.candles(sym, now)
            except Exception as e:
                self.log(f"[warn] {sym}: {e}")
                continue
            if len(df) < 50:
                continue
            last = df.index[-1].isoformat()
            if self.state["last_bar"].get(sym) == last:
                continue
            self.state["last_bar"][sym] = last
            frames[sym] = df
        if not intraday:
            self.state["last_daily_eval"] = now.date().isoformat()

        self.signal_exits(now, frames, prices)
        if risk.kill_switch_active():
            self.save()
            return
        regime_ok = self.regime_ok(now.date())
        for sym, df in frames.items():
            if sym in self.positions or sym not in self.cfg.watchlist:
                continue
            px = prices.get(sym, float(df["close"].iloc[-1]))
            self.try_entry(sym, df, px, now, regime_ok)
        self.save()

    def run(self, once: bool = False, holidays: list[str] | None = None) -> None:
        poll = float((self.cfg.execution or {}).get("poll_seconds", 30))
        self.log(f"growwbot engine: mode={self.mode.upper()} strategy={self.strategy.name} "
                 f"interval={self.strategy.interval} watchlist={len(self.cfg.watchlist)} symbols")
        while True:
            now = now_ist()
            if market_open(now, holidays):
                try:
                    self.step(now)
                except Exception as e:  # keep the loop alive; stops at the broker still protect positions
                    self.log(f"[ERROR] step failed: {e!r}")
            elif not once:
                self.log(f"{now:%H:%M} market closed")
            if once:
                return
            if now.time() > MARKET_CLOSE:
                held = "Swing positions carry overnight; start the engine again tomorrow." if self.positions else ""
                self.log(f"Market closed for the day. Engine stopping. {held}".strip())
                return
            _time.sleep(poll)
