"""Order execution: a paper broker (default) and the live Groww broker.

Live orders need ALL THREE of:
  1. ``mode = "live"`` in config.toml
  2. ``GROWW_ENABLE_LIVE=YES_I_ACCEPT_REAL_MONEY_RISK`` in .env
  3. the ``--live`` flag on the command
Anything less gives you the paper broker, which never contacts Groww's order APIs.
"""

from __future__ import annotations

import json
import secrets
import time as _time
from dataclasses import dataclass
from datetime import datetime

from . import config
from .costs import CostModel

FILLED = {"EXECUTED", "COMPLETED", "DELIVERY_AWAITED"}
DEAD = {"REJECTED", "FAILED", "CANCELLED"}


@dataclass
class Fill:
    ok: bool
    symbol: str
    side: str
    qty: int
    price: float
    order_id: str = ""
    status: str = ""
    message: str = ""


def new_reference_id(prefix: str = "gb") -> str:
    """Groww order_reference_id: 8-20 alphanumeric chars, at most two hyphens."""
    return f"{prefix}{datetime.now():%m%d%H%M}{secrets.token_hex(3)}"[:20]


def fallback_tick(price: float) -> float:
    """Approximate NSE price-band tick sizes; the live broker prefers the instrument's own tick_size."""
    if price < 250:
        return 0.01
    if price < 1000:
        return 0.05
    if price < 5000:
        return 0.10
    if price < 10000:
        return 0.50
    if price < 20000:
        return 1.00
    return 5.00


def round_to_tick(price: float, tick: float, down: bool = True) -> float:
    import math

    steps = price / tick
    steps = math.floor(steps + 1e-9) if down else math.ceil(steps - 1e-9)
    return round(steps * tick, 2)


class LiveTradingNotAllowed(SystemExit):
    pass


def live_blockers(cfg: config.Config, live_flag: bool) -> list[str]:
    missing = []
    if not live_flag:
        missing.append("the --live flag was not passed")
    if cfg.mode != "live":
        missing.append(f'config.toml has mode = "{cfg.mode}" (needs "live")')
    if not config.live_env_ack():
        missing.append(f"GROWW_ENABLE_LIVE in .env is not {config.LIVE_ACK}")
    return missing


def make_broker(cfg: config.Config, live_flag: bool = False):
    if not live_flag:
        return PaperBroker(cfg)
    missing = live_blockers(cfg, live_flag)
    if missing:
        raise LiveTradingNotAllowed("Live trading refused:\n  - " + "\n  - ".join(missing))
    return GrowwBroker(cfg)


# ----------------------------------------------------------------------------- paper

class PaperBroker:
    """Simulated fills at the reference price +/- slippage, with Groww costs.

    Keeps a cash balance in state/paper_account.json so paper P&L carries over
    between runs. Uses Groww LTP for prices when credentials exist (read-only
    market-data calls), otherwise the price the caller passes in.
    """

    live = False

    def __init__(self, cfg: config.Config):
        self.cfg = cfg
        ex = cfg.execution or {}
        self.slip = float(ex.get("slippage_pct", 0.05)) / 100.0
        self.costs = CostModel.from_dict(cfg.costs)
        self.path = config.state_dir() / "paper_account.json"
        if self.path.exists():
            self.account = json.loads(self.path.read_text())
        else:
            self.account = {"cash": float(cfg.capital), "started": datetime.now().isoformat(timespec="seconds")}
            self._save()

    def _save(self):
        self.path.write_text(json.dumps(self.account, indent=2))

    def cash(self) -> float:
        return float(self.account["cash"])

    def reset(self, capital: float) -> None:
        self.account = {"cash": float(capital), "started": datetime.now().isoformat(timespec="seconds")}
        self._save()

    def order(self, symbol: str, side: str, qty: int, ref_price: float, intraday: bool, **_) -> Fill:
        side = side.upper()
        price = ref_price * (1 + self.slip) if side == "BUY" else ref_price * (1 - self.slip)
        price = round(price, 2)
        fee = self.costs.order_cost(side, price, qty, intraday)
        if side == "BUY":
            need = price * qty + fee
            if need > self.cash():
                return Fill(False, symbol, side, 0, 0.0, status="REJECTED", message="insufficient paper cash")
            self.account["cash"] = round(self.cash() - need, 2)
        else:
            self.account["cash"] = round(self.cash() + price * qty - fee, 2)
        self._save()
        return Fill(True, symbol, side, qty, price, order_id="PAPER-" + new_reference_id("p"), status="EXECUTED",
                    message=f"paper fill, charges Rs {fee:.2f}")

    def place_stop(self, symbol: str, qty: int, trigger: float, intraday: bool) -> str:
        return ""  # the engine monitors paper stops itself

    def stop_filled(self, order_id: str) -> float | None:
        return None

    def cancel_stop(self, order_id: str) -> None:
        return None


# ----------------------------------------------------------------------------- live

class GrowwBroker:
    """Real orders through the Groww Trade API. Every call is logged to state/orders.log."""

    live = True

    def __init__(self, cfg: config.Config):
        from .groww_client import Groww

        self.cfg = cfg
        ex = cfg.execution or {}
        self.g = Groww(max_orders_per_second=float(ex.get("max_orders_per_second", 1)))
        self.order_type = str(ex.get("entry_order_type", "MARKET")).upper()
        self.limit_buffer = float(ex.get("limit_buffer_pct", 0.1)) / 100.0
        self.log_path = config.state_dir() / "orders.log"
        self._ticks: dict[str, float] = {}

    def tick(self, symbol: str, price: float) -> float:
        if symbol not in self._ticks:
            try:
                inst = self.g.call("get_instrument_by_exchange_and_trading_symbol", exchange="NSE", trading_symbol=symbol)
                self._ticks[symbol] = float(inst.get("tick_size") or 0) or fallback_tick(price)
            except Exception:
                self._ticks[symbol] = fallback_tick(price)
        return self._ticks[symbol]

    def _log(self, event: str, payload) -> None:
        with self.log_path.open("a") as f:
            f.write(json.dumps({"t": datetime.now().isoformat(timespec="seconds"), "event": event, "data": payload},
                               default=str) + "\n")

    def cash(self) -> float:
        return self.g.cash_available()

    def _wait_fill(self, order_id: str, qty: int, timeout_s: float = 30.0) -> tuple[str, int, float]:
        deadline = _time.monotonic() + timeout_s
        status, filled = "", 0
        while _time.monotonic() < deadline:
            st = self.g.call("get_order_status", groww_order_id=order_id, segment="CASH") or {}
            status, filled = str(st.get("order_status", "")).upper(), int(st.get("filled_quantity") or 0)
            if status in FILLED or status in DEAD or filled >= qty:
                break
            _time.sleep(1.0)
        detail = self.g.call("get_order_detail", groww_order_id=order_id, segment="CASH") or {}
        avg = float(detail.get("average_fill_price") or 0.0)
        filled = int(detail.get("filled_quantity") or filled)
        return status, filled, avg

    def order(self, symbol: str, side: str, qty: int, ref_price: float, intraday: bool, **_) -> Fill:
        side = side.upper()
        product = "MIS" if intraday else "CNC"
        kwargs = dict(
            trading_symbol=symbol, quantity=int(qty), validity="DAY", exchange="NSE", segment="CASH",
            product=product, transaction_type=side, order_reference_id=new_reference_id(),
        )
        if self.order_type == "LIMIT" and side == "BUY":
            kwargs.update(order_type="LIMIT",
                          price=round_to_tick(ref_price * (1 + self.limit_buffer), self.tick(symbol, ref_price)))
        else:
            kwargs.update(order_type="MARKET")
        self._log("place_order", kwargs)
        try:
            resp = self.g.order_call("place_order", **kwargs) or {}
        except Exception as e:
            self._log("place_order_error", repr(e))
            return Fill(False, symbol, side, 0, 0.0, status="ERROR", message=repr(e))
        self._log("place_order_resp", resp)
        oid = resp.get("groww_order_id", "")
        status, filled, avg = self._wait_fill(oid, qty)
        self._log("fill", {"id": oid, "status": status, "filled": filled, "avg": avg})
        if filled <= 0:
            if status not in DEAD:  # still open after the wait: cancel so nothing fills behind our back
                try:
                    self.g.order_call("cancel_order", segment="CASH", groww_order_id=oid)
                except Exception as e:
                    self._log("cancel_error", repr(e))
            return Fill(False, symbol, side, 0, 0.0, oid, status, "not filled")
        return Fill(True, symbol, side, filled, avg or ref_price, oid, status)

    def place_stop(self, symbol: str, qty: int, trigger: float, intraday: bool) -> str:
        """Broker-side SL-M sell, so the position is protected even if this bot dies.
        DAY validity: for CNC swing trades the engine re-places it every morning."""
        kwargs = dict(
            trading_symbol=symbol, quantity=int(qty), validity="DAY", exchange="NSE", segment="CASH",
            product="MIS" if intraday else "CNC", order_type="SL_M", transaction_type="SELL",
            trigger_price=round_to_tick(trigger, self.tick(symbol, trigger)), order_reference_id=new_reference_id("sl"),
        )
        self._log("place_stop", kwargs)
        try:
            resp = self.g.order_call("place_order", **kwargs) or {}
            self._log("place_stop_resp", resp)
            return resp.get("groww_order_id", "")
        except Exception as e:
            self._log("place_stop_error", repr(e))
            return ""

    def stop_filled(self, order_id: str) -> float | None:
        """Average fill price if the broker-side stop already executed, else None."""
        if not order_id:
            return None
        try:
            d = self.g.call("get_order_detail", groww_order_id=order_id, segment="CASH") or {}
        except Exception as e:
            self._log("stop_status_error", repr(e))
            return None
        if str(d.get("order_status", "")).upper() in FILLED and int(d.get("filled_quantity") or 0) > 0:
            return float(d.get("average_fill_price") or 0.0) or None
        return None

    def stop_dead(self, order_id: str) -> bool:
        """True if the broker-side stop was rejected, failed or cancelled (position unprotected)."""
        try:
            d = self.g.call("get_order_status", groww_order_id=order_id, segment="CASH") or {}
        except Exception:
            return False
        return str(d.get("order_status", "")).upper() in DEAD

    def cancel_stop(self, order_id: str) -> None:
        if not order_id:
            return
        try:
            self._log("cancel_stop", order_id)
            self.g.order_call("cancel_order", segment="CASH", groww_order_id=order_id)
        except Exception as e:
            self._log("cancel_stop_error", repr(e))

    def broker_positions(self) -> list[dict]:
        return (self.g.call("get_positions_for_user", segment="CASH") or {}).get("positions", [])

    def open_orders(self) -> list[dict]:
        orders = (self.g.call("get_order_list", segment="CASH", page=0, page_size=25) or {}).get("order_list", [])
        return [o for o in orders if str(o.get("order_status", "")).upper() not in FILLED | DEAD]
