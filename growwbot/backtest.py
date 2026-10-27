"""Portfolio backtester with Groww costs, slippage and the same risk rules as live.

Rules of the simulation (chosen to be pessimistic, not flattering):
  * Signals are read on a bar's close; orders fill at the NEXT bar's open, plus slippage.
  * If a bar touches both the stop and the target, the stop is assumed to fill first.
  * A gap through the stop fills at the open, not at the stop.
  * Intraday (MIS) positions are closed at ``squareoff_time`` or the day's last bar.
  * Every entry passes ``RiskManager.check_entry`` (position limits, daily loss, ...).
  * Costs: Groww brokerage, STT, stamp duty, exchange, SEBI, GST, DP (see costs.py).

What it cannot model: partial fills, order-book depth, circuit locks, API
outages, your own discipline. Expect live results to be worse than this.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime

import numpy as np
import pandas as pd

from .costs import CostModel
from .risk import RiskManager
from .strategies import Strategy


@dataclass
class Position:
    symbol: str
    qty: int
    entry: float
    stop: float
    target: float
    entry_time: datetime
    risk_per_share: float
    entry_cost: float
    bars: int = 0


@dataclass
class Trade:
    symbol: str
    entry_time: datetime
    exit_time: datetime
    qty: int
    entry: float
    exit: float
    reason: str
    pnl: float          # net of all costs
    costs: float
    r_multiple: float


@dataclass
class Result:
    trades: list[Trade]
    equity: pd.Series
    initial_capital: float
    blocked: dict[str, int] = field(default_factory=dict)

    def trades_df(self) -> pd.DataFrame:
        return pd.DataFrame([t.__dict__ for t in self.trades])

    def metrics(self) -> dict:
        eq = self.equity
        n = len(self.trades)
        pnl = np.array([t.pnl for t in self.trades]) if n else np.array([])
        wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
        final = float(eq.iloc[-1]) if len(eq) else self.initial_capital
        days = max(1, (eq.index[-1] - eq.index[0]).days) if len(eq) > 1 else 1
        years = days / 365.25
        total_ret = final / self.initial_capital - 1
        cagr = (final / self.initial_capital) ** (1 / years) - 1 if years >= 0.25 and final > 0 else float("nan")
        dd = (eq / eq.cummax() - 1).min() if len(eq) else 0.0
        daily = eq.resample("1D").last().dropna().pct_change().dropna()
        sharpe = float(daily.mean() / daily.std() * math.sqrt(252)) if len(daily) > 2 and daily.std() > 0 else float("nan")
        gross_win, gross_loss = wins.sum(), -losses.sum()
        return {
            "trades": n,
            "win_rate_pct": round(100 * len(wins) / n, 1) if n else 0.0,
            "net_pnl": round(float(pnl.sum()), 2),
            "total_costs": round(sum(t.costs for t in self.trades), 2),
            "total_return_pct": round(100 * total_ret, 2),
            "cagr_pct": round(100 * cagr, 2) if not math.isnan(cagr) else None,
            "max_drawdown_pct": round(100 * float(dd), 2),
            "sharpe": round(sharpe, 2) if not math.isnan(sharpe) else None,
            "profit_factor": round(float(gross_win / gross_loss), 2) if gross_loss > 0 else None,
            "avg_win": round(float(wins.mean()), 2) if len(wins) else 0.0,
            "avg_loss": round(float(losses.mean()), 2) if len(losses) else 0.0,
            "expectancy_per_trade": round(float(pnl.mean()), 2) if n else 0.0,
            "avg_r": round(float(np.mean([t.r_multiple for t in self.trades])), 2) if n else 0.0,
            "final_equity": round(final, 2),
            "signals_blocked_by_risk": sum(self.blocked.values()),
        }


def regime_series(nifty_daily: pd.DataFrame | None, ema_period: int = 50) -> dict[date, bool] | None:
    """date -> True if NIFTY's *previous* daily close was above its EMA (no look-ahead)."""
    if nifty_daily is None or nifty_daily.empty:
        return None
    c = nifty_daily["close"]
    above = (c > c.ewm(span=ema_period, adjust=False, min_periods=ema_period).mean()).shift(1)
    return {ts.date(): bool(v) for ts, v in above.dropna().items()}


def run(
    data: dict[str, pd.DataFrame],
    strategy: Strategy,
    params: dict | None = None,
    risk_cfg: dict | None = None,
    initial_capital: float = 50000.0,
    slippage_pct: float = 0.05,
    costs: CostModel | None = None,
    regime: dict[date, bool] | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> Result:
    """Simulate ``strategy`` on ``data``. Signals use the full history (so indicators
    are warmed up); trading only happens between ``start`` and ``end``."""
    costs = costs or CostModel()
    params = params or {}
    rm = RiskManager(risk_cfg, capital=initial_capital, persist=False)
    slip = slippage_pct / 100.0
    intraday = strategy.intraday

    sigs = {s: strategy.signals(df, **params) for s, df in data.items() if len(df) > 0}
    frames = {s: data[s] for s in sigs}
    # Mark each symbol's last bar of each day (for intraday square-off).
    last_of_day = {}
    for s, df in frames.items():
        d = pd.Series(df.index.date, index=df.index)
        last_of_day[s] = d != d.shift(-1)

    timeline = sorted(set().union(*[df.index for df in frames.values()])) if frames else []
    timeline = [t for t in timeline if (start is None or t >= start) and (end is None or t < end)]
    cash = float(initial_capital)
    positions: dict[str, Position] = {}
    pending_entry: dict[str, tuple[float, float, float]] = {}  # sym -> (stop, target, signal_close)
    pending_exit: dict[str, str] = {}
    last_close: dict[str, float] = {}
    trades: list[Trade] = []
    blocked: dict[str, int] = {}
    equity_pts: list[tuple[datetime, float]] = []

    def close_pos(sym: str, price: float, ts: datetime, reason: str) -> None:
        nonlocal cash
        p = positions.pop(sym)
        exit_cost = costs.order_cost("SELL", price, p.qty, intraday)
        cash += p.qty * price - exit_cost
        pnl = p.qty * (price - p.entry) - p.entry_cost - exit_cost
        r = pnl / (p.qty * p.risk_per_share) if p.risk_per_share > 0 else 0.0
        trades.append(Trade(sym, p.entry_time, ts, p.qty, round(p.entry, 2), round(price, 2), reason,
                            round(pnl, 2), round(p.entry_cost + exit_cost, 2), round(r, 2)))
        rm.record_exit(pnl)

    def equity_now() -> float:
        return cash + sum(p.qty * last_close.get(s, p.entry) for s, p in positions.items())

    for ts in timeline:
        rm.roll_day(ts.date())
        for sym, df in frames.items():
            if ts not in df.index:
                continue
            bar = df.loc[ts]
            o, h, l, c = float(bar["open"]), float(bar["high"]), float(bar["low"]), float(bar["close"])
            eod = bool(last_of_day[sym].loc[ts])

            # 1) queued exit from the previous bar's signal
            if sym in pending_exit and sym in positions:
                close_pos(sym, o * (1 - slip), ts, pending_exit[sym])
            pending_exit.pop(sym, None)

            # 2) queued entry
            if sym in pending_entry and sym not in positions:
                stop, target, sig_close = pending_entry[sym]
                price = o * (1 + slip)
                tgt = None if (target is None or math.isnan(target)) else target
                open_risk = sum(p.qty * max(0.0, p.entry - p.stop) for p in positions.values())
                rm.capital = equity_now()
                regime_ok = True if regime is None else regime.get(ts.date(), True)
                dec = rm.check_entry(sym, price, stop, tgt, ts.to_pydatetime(), len(positions), intraday,
                                     cash=cash, open_risk=open_risk, signal_close=sig_close,
                                     regime_ok=regime_ok, check_kill_switch=False)
                if dec.ok:
                    entry_cost = costs.order_cost("BUY", price, dec.qty, intraday)
                    cash -= dec.qty * price + entry_cost
                    positions[sym] = Position(sym, dec.qty, price, stop, tgt if tgt else float("nan"),
                                              ts.to_pydatetime(), price - stop, entry_cost)
                    rm.record_entry()
                else:
                    key = dec.reasons[0].split(" ")[0] if dec.reasons else "unknown"
                    blocked[key] = blocked.get(key, 0) + 1
            pending_entry.pop(sym, None)

            # 3) stops / targets inside this bar
            if sym in positions:
                p = positions[sym]
                p.bars += 1
                if o <= p.stop:
                    close_pos(sym, o * (1 - slip), ts, "stop (gap)")
                elif l <= p.stop:
                    close_pos(sym, p.stop * (1 - slip), ts, "stop")
                elif not math.isnan(p.target) and h >= p.target:
                    close_pos(sym, p.target, ts, "target")
                elif intraday and (eod or rm.squareoff_due(ts.to_pydatetime())):
                    close_pos(sym, c * (1 - slip), ts, "square-off")
                elif strategy.max_hold_bars and p.bars >= strategy.max_hold_bars:
                    pending_exit[sym] = "time stop"

            last_close[sym] = c

            # 4) new signals on this bar's close
            row = sigs[sym].loc[ts]
            if sym in positions and bool(row["exit"]):
                pending_exit[sym] = "exit signal"
            elif sym not in positions and bool(row["entry"]) and not (intraday and eod):
                pending_entry[sym] = (float(row["stop"]), float(row["target"]), c)

        # daily loss breaker (realised + open)
        unreal = sum(p.qty * (last_close.get(s, p.entry) - p.entry) for s, p in positions.items())
        if not rm.day.halted_reason and rm.breached_daily_loss(unreal):
            rm.day.halted_reason = "daily loss limit"
        equity_pts.append((ts, equity_now()))

    # close anything still open at the last price
    if positions and timeline:
        for sym in list(positions):
            close_pos(sym, last_close[sym], timeline[-1], "end of data")
        equity_pts[-1] = (timeline[-1], cash)

    eq = pd.Series([v for _, v in equity_pts], index=pd.DatetimeIndex([t for t, _ in equity_pts]), dtype=float)
    return Result(trades, eq, initial_capital, blocked)


def buy_and_hold(data: dict[str, pd.DataFrame], initial_capital: float) -> dict:
    """Equal-weight buy-and-hold of the same symbols over the same period (before costs)."""
    rets = [float(df["close"].iloc[-1] / df["open"].iloc[0] - 1) for df in data.values() if len(df) > 1]
    if not rets:
        return {}
    r = float(np.mean(rets))
    return {"total_return_pct": round(100 * r, 2), "final_equity": round(initial_capital * (1 + r), 2)}


def cut_point(data: dict[str, pd.DataFrame], frac: float) -> pd.Timestamp:
    """Timestamp that splits the combined history into in-sample / out-of-sample."""
    all_ts = sorted(set().union(*[df.index for df in data.values()]))
    return all_ts[int(len(all_ts) * frac)]
