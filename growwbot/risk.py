"""Risk management: position sizing, pre-trade checks, daily limits, kill switch.

Every entry -- backtest, paper or live -- passes through ``RiskManager.check_entry``.
A rejection is final for that signal. Exits are never blocked.

These rules keep each loss and each day's losses small. They do not make a
trade win.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time
from pathlib import Path

from . import config

DEFAULTS = {
    "risk_per_trade_pct": 0.5,
    "max_position_pct": 20.0,
    "max_open_positions": 3,
    "max_daily_loss_pct": 2.0,
    "max_trades_per_day": 4,
    "max_consecutive_losses": 3,
    "min_reward_risk": 1.5,
    "min_price": 50.0,
    "max_slippage_pct": 0.5,
    "blocked_symbols": [],
    "no_entries_before": "09:30",
    "no_entries_after": "14:30",
    "squareoff_time": "15:10",
    "regime_filter": True,
    # Skip a trade when Groww's round-trip charges would eat more than this % of
    # the rupees it risks. 0 turns the check off. See docs/14-historical-validation.md:
    # on a Rs 50k account most delivery trades failed it, and those trades lost money.
    "max_cost_pct_of_risk": 25.0,
}


def _t(s: str) -> time:
    return time.fromisoformat(s)


@dataclass
class DayState:
    day: str = field(default_factory=lambda: date.today().isoformat())
    trades: int = 0
    realised_pnl: float = 0.0
    consecutive_losses: int = 0
    halted_reason: str = ""


@dataclass
class Decision:
    ok: bool
    qty: int = 0
    reasons: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return ("PASS" if self.ok else "BLOCK") + f" qty={self.qty}" + ("" if not self.reasons else " | " + "; ".join(self.reasons))


# ----------------------------------------------------------------------------- kill switch

def kill_switch_path() -> Path:
    return config.state_dir() / "KILL_SWITCH"


def kill_switch_active() -> bool:
    return kill_switch_path().exists()


def engage_kill_switch(reason: str) -> None:
    kill_switch_path().write_text(f"{datetime.now().isoformat(timespec='seconds')} {reason}\n")


def release_kill_switch() -> bool:
    p = kill_switch_path()
    if p.exists():
        p.unlink()
        return True
    return False


# ----------------------------------------------------------------------------- manager

class RiskManager:
    def __init__(self, risk_cfg: dict | None = None, capital: float = 50000.0, persist: bool = False,
                 costs=None):
        self.cfg = {**DEFAULTS, **(risk_cfg or {})}
        self.costs = costs  # CostModel; None -> the cost check uses Groww's default charges
        self.capital = float(capital)
        self.persist = persist
        self.day = self._load() if persist else DayState()

    # ---- state -----------------------------------------------------------------
    def _path(self) -> Path:
        return config.state_dir() / "risk_day.json"

    def _load(self) -> DayState:
        p = self._path()
        if p.exists():
            st = DayState(**json.loads(p.read_text()))
            if st.day == date.today().isoformat():
                return st
        return DayState()

    def _save(self) -> None:
        if self.persist:
            self._path().write_text(json.dumps(asdict(self.day), indent=2))

    def roll_day(self, today: date) -> None:
        if self.day.day != today.isoformat():
            self.day = DayState(day=today.isoformat())
            self._save()

    # ---- sizing ----------------------------------------------------------------
    def size(self, entry: float, stop: float, cash: float | None = None) -> int:
        """Shares such that hitting the stop loses ~risk_per_trade_pct of capital,
        capped by max_position_pct and available cash."""
        per_share = entry - stop
        if per_share <= 0 or entry <= 0:
            return 0
        risk_budget = self.capital * self.cfg["risk_per_trade_pct"] / 100.0
        by_risk = math.floor(risk_budget / per_share)
        by_cap = math.floor(self.capital * self.cfg["max_position_pct"] / 100.0 / entry)
        qty = min(by_risk, by_cap)
        if cash is not None:
            qty = min(qty, math.floor(cash / entry))
        return max(0, int(qty))

    # ---- checks ----------------------------------------------------------------
    def daily_loss_limit(self) -> float:
        return self.capital * self.cfg["max_daily_loss_pct"] / 100.0

    def check_entry(
        self,
        symbol: str,
        entry: float,
        stop: float,
        target: float | None,
        now: datetime,
        open_positions: int,
        intraday: bool,
        cash: float | None = None,
        open_risk: float = 0.0,
        signal_close: float | None = None,
        regime_ok: bool = True,
        check_kill_switch: bool = True,
    ) -> Decision:
        c = self.cfg
        self.roll_day(now.date())
        reasons: list[str] = []
        if check_kill_switch and kill_switch_active():
            reasons.append("kill switch is ON (run `growwbot unkill` after you have checked why)")
        if self.day.halted_reason:
            reasons.append(f"trading halted today: {self.day.halted_reason}")
        if symbol.upper() in {s.upper() for s in c["blocked_symbols"]}:
            reasons.append("symbol is blocked")
        if entry < c["min_price"]:
            reasons.append(f"price {entry:.2f} under min_price {c['min_price']}")
        if not (stop < entry):
            reasons.append("stop must be below entry for a long")
        if target is not None and not math.isnan(target):
            rr = (target - entry) / (entry - stop) if entry > stop else 0.0
            if rr < c["min_reward_risk"]:
                reasons.append(f"reward:risk {rr:.2f} under {c['min_reward_risk']}")
        if signal_close and entry > signal_close * (1 + c["max_slippage_pct"] / 100.0):
            reasons.append(f"price ran {100 * (entry / signal_close - 1):.2f}% past the signal close")
        if open_positions >= c["max_open_positions"]:
            reasons.append(f"already {open_positions} open positions (max {c['max_open_positions']})")
        if self.day.trades >= c["max_trades_per_day"]:
            reasons.append(f"{self.day.trades} trades today (max {c['max_trades_per_day']})")
        if self.day.consecutive_losses >= c["max_consecutive_losses"]:
            reasons.append(f"{self.day.consecutive_losses} losses in a row today")
        if c["regime_filter"] and not regime_ok:
            reasons.append("market regime filter: NIFTY 50 below its 50-day EMA")
        if intraday:
            t = now.time()
            if t < _t(c["no_entries_before"]) or t > _t(c["no_entries_after"]):
                reasons.append(f"outside entry window {c['no_entries_before']}-{c['no_entries_after']}")
        qty = self.size(entry, stop, cash)
        if qty < 1:
            reasons.append("position size rounds to 0 shares (stop too wide or capital too small)")
        elif entry > stop and float(c.get("max_cost_pct_of_risk") or 0) > 0:
            from .costs import CostModel

            cost = (self.costs or CostModel()).round_trip(entry, entry, qty, intraday)
            risk_rs = qty * (entry - stop)
            if cost > risk_rs * float(c["max_cost_pct_of_risk"]) / 100.0:
                reasons.append(f"charges Rs {cost:,.0f} are {100 * cost / risk_rs:.0f}% of the Rs {risk_rs:,.0f} at risk "
                               f"(max {c['max_cost_pct_of_risk']}%): position too small for the fees")
        # Worst case today if this and every open trade hit their stops.
        new_risk = qty * max(0.0, entry - stop)
        worst = -self.day.realised_pnl + open_risk + new_risk
        if worst > self.daily_loss_limit():
            reasons.append(f"would put Rs {worst:,.0f} at risk today (daily limit Rs {self.daily_loss_limit():,.0f})")
        return Decision(ok=not reasons, qty=qty if not reasons else 0, reasons=reasons)

    # ---- bookkeeping -------------------------------------------------------------
    def record_entry(self) -> None:
        self.day.trades += 1
        self._save()

    def record_exit(self, pnl: float) -> None:
        self.day.realised_pnl += pnl
        self.day.consecutive_losses = self.day.consecutive_losses + 1 if pnl < 0 else 0
        if self.day.consecutive_losses >= self.cfg["max_consecutive_losses"]:
            self.day.halted_reason = f"{self.day.consecutive_losses} consecutive losses"
        self._save()

    def breached_daily_loss(self, unrealised_pnl: float = 0.0) -> bool:
        return (self.day.realised_pnl + unrealised_pnl) <= -self.daily_loss_limit()

    def squareoff_due(self, now: datetime) -> bool:
        return now.time() >= _t(self.cfg["squareoff_time"])
