"""Setup odds: replay one planned trade thousands of times before you risk money.

Adapted from the "time machine" idea in Jake Schincariol's day-trader-skill
(MIT), rebuilt for this repo's data loader, strategies and NSE sessions.

The question it answers is narrow and useful: *if the next few bars behave
like this stock's own recent bars, how often does this exact plan hit the
target before the stop?* It answers three ways:

  1. **Bootstrap replays.** Resample the stock's own past bars (for intraday,
     matched to the same time of day) and walk the trade forward bar by bar.
  2. **Historical precedent.** Re-run the same strategy on this symbol's real
     history and report what actually happened.
  3. **Break-even arithmetic.** A 2R target only needs to win 1 in 3 of the
     trades that reach a side. The verdict compares the replays to that bar,
     so a low win rate is not automatically bad news (and a high one is not
     automatically good).

It is a simulation built from recent history, not a prediction. Results, news
and circuit limits do things the sample never did.
"""

from __future__ import annotations

import math
from datetime import time as dtime

import numpy as np
import pandas as pd

BARS_PER_DAY_GUESS = {"1minute": 375, "2minute": 188, "3minute": 125, "5minute": 75,
                      "10minute": 38, "15minute": 25, "30minute": 13, "1hour": 7}


def _ratios(df: pd.DataFrame) -> np.ndarray:
    """Each bar as (open, high, low, close) divided by the previous close."""
    prev = df["close"].shift(1)
    r = np.column_stack([
        (df["open"] / prev).to_numpy(),
        (df["high"] / prev).to_numpy(),
        (df["low"] / prev).to_numpy(),
        (df["close"] / prev).to_numpy(),
    ])
    ok = np.isfinite(r).all(axis=1) & (r > 0).all(axis=1)
    return r[ok], ok


def build_pools(df: pd.DataFrame, intraday: bool, window: int = 2) -> list[np.ndarray] | np.ndarray:
    """A sampling pool of bar ratios.

    Intraday returns one pool per slot in the trading day, drawn from the same
    slot plus or minus ``window`` slots, so the opening hour's volatility is
    not used to model the lunch lull. Daily returns a single pool.
    """
    r, ok = _ratios(df)
    if not intraday:
        return r
    slots = pd.Series(range(len(df)), index=df.index)
    day = pd.Series(df.index.date, index=df.index)
    slot_of_bar = slots.groupby(day).rank(method="first").astype(int).to_numpy()[ok] - 1
    n_slots = int(slot_of_bar.max()) + 1 if len(slot_of_bar) else 0
    pools = []
    for s in range(n_slots):
        sel = np.abs(slot_of_bar - s) <= window
        pools.append(r[sel] if sel.sum() >= 30 else r)
    return pools


def replay(
    pools,
    entry: float,
    stop: float,
    target: float | None,
    bars: int,
    sims: int = 10000,
    seed: int = 19,
    start_slot: int = 0,
) -> dict:
    """Walk ``sims`` paths forward ``bars`` bars from ``entry``.

    Within a bar the stop is checked before the target, and a bar that opens
    through the stop fills at the open, so a gap can cost more than 1R. Both
    choices make the result pessimistic on purpose.
    """
    rng = np.random.default_rng(seed)
    risk = entry - stop
    if risk <= 0:
        raise ValueError("stop must be below entry for a long")

    price = np.full(sims, float(entry))
    live = np.ones(sims, dtype=bool)
    exit_price = np.full(sims, np.nan)
    hit_target = np.zeros(sims, dtype=bool)
    hit_stop = np.zeros(sims, dtype=bool)
    bars_held = np.full(sims, bars, dtype=int)

    per_slot = isinstance(pools, list)
    for b in range(bars):
        if not live.any():
            break
        pool = pools[min(start_slot + b, len(pools) - 1)] if per_slot else pools
        draw = pool[rng.integers(0, len(pool), size=sims)]
        o = price * draw[:, 0]
        h = price * draw[:, 1]
        l = price * draw[:, 2]
        c = price * draw[:, 3]

        gapped = live & (o <= stop)
        stopped = live & ~gapped & (l <= stop)
        targeted = live & ~gapped & ~stopped & (h >= target) if target else np.zeros(sims, dtype=bool)

        for mask, px in ((gapped, o), (stopped, np.full(sims, float(stop))), (targeted, np.full(sims, float(target or 0)))):
            if mask.any():
                exit_price[mask] = px[mask]
                bars_held[mask] = b + 1
        hit_stop |= gapped | stopped
        hit_target |= targeted
        live &= ~(gapped | stopped | targeted)
        price = np.where(live, c, price)

    open_at_end = np.isnan(exit_price)
    final = np.where(open_at_end, price, exit_price)
    r_multiple = (final - entry) / risk
    decided = int(hit_target.sum() + hit_stop.sum())
    pct = lambda a, q: round(float(np.percentile(a, q)), 2)

    out = {
        "sims": sims, "seed": seed, "bars": bars,
        "entry": round(entry, 2), "stop": round(stop, 2),
        "target": None if not target else round(target, 2),
        "risk_per_share": round(risk, 2),
        "reward_risk": None if not target else round((target - entry) / risk, 2),
        "target_first_pct": round(100 * float(hit_target.mean()), 1),
        "stop_first_pct": round(100 * float(hit_stop.mean()), 1),
        "neither_pct": round(100 * float(open_at_end.mean()), 1),
        "green_pct": round(100 * float((hit_target | (open_at_end & (final > entry))).mean()), 1),
        "avg_r": round(float(r_multiple.mean()), 3),
        "median_r": round(float(np.median(r_multiple)), 3),
        "exit_price": {"p5": pct(final, 5), "median": pct(final, 50), "p95": pct(final, 95)},
        "worse_than_1R_loss_pct": round(100 * float((r_multiple < -1.001).mean()), 1),
        "median_bars_to_exit": int(np.median(bars_held[~open_at_end])) if decided else None,
    }
    out.update(verdict(out))
    return out


def verdict(o: dict) -> dict:
    """Compare the replays to the win rate the reward:risk actually needs."""
    decided = o["target_first_pct"] + o["stop_first_pct"]
    rr = o["reward_risk"]
    if decided < 1 or not rr or rr <= 0:
        return {"breakeven_win_rate_pct": None, "edge_points": None,
                "verdict": "Too few replays reached the stop or the target to judge."}
    share = 100 * o["target_first_pct"] / decided
    need = 100 / (1 + rr)
    edge = share - need
    if abs(edge) < 5:
        word = "Close to a coin flip" if abs(rr - 1) < 0.01 else "Close to break-even"
    elif edge >= 15:
        word = "Leans strongly toward the target"
    elif edge >= 5:
        word = "Leans toward the target"
    elif edge <= -15:
        word = "Leans strongly toward the stop"
    else:
        word = "Leans toward the stop"
    note = (f"{word}: of the replays that reached a side, {share:.0f}% hit the target, "
            f"and a {rr:.1f}R target needs {need:.0f}% to break even.")
    extra = []
    if o["neither_pct"] >= 40:
        extra.append(f"{o['neither_pct']}% of replays reached neither; the exit price decides those.")
    if (o["avg_r"] > 0) != (edge > 0) and abs(o["avg_r"]) > 0.02:
        extra.append(f"Average R ({o['avg_r']:+.3f}) points the other way, because of the undecided replays.")
    if o["worse_than_1R_loss_pct"] >= 5:
        extra.append(f"{o['worse_than_1R_loss_pct']}% of replays gapped through the stop and lost more than 1R.")
    return {"breakeven_win_rate_pct": round(need, 1), "edge_points": round(edge, 1),
            "verdict": note, "notes": extra}


def reconcile(out: dict, prec: dict | None) -> None:
    """Add a note when the replays and the real history point different ways."""
    if not prec or prec.get("trades", 0) < 3 or out.get("edge_points") is None:
        return
    sim_up, hist_up = out["edge_points"] > 0, prec["avg_r"] > 0
    if sim_up != hist_up:
        out.setdefault("notes", []).append(
            f"The replays and the history disagree: the replays lean {'toward' if sim_up else 'against'} "
            f"the target, but this strategy's {prec['trades']} real trades on this symbol averaged "
            f"{prec['avg_r']:+}R. Trust the history more; the replays assume the future resembles "
            f"a resampled past.")


def bars_remaining(interval: str, now, squareoff: str = "15:10", default_hold: int = 20) -> int:
    """Intraday: bars from now to square-off. Daily and above: a holding horizon."""
    if interval not in BARS_PER_DAY_GUESS:
        return default_hold
    minutes = {"1minute": 1, "2minute": 2, "3minute": 3, "5minute": 5, "10minute": 10,
               "15minute": 15, "30minute": 30, "1hour": 60}[interval]
    end = dtime.fromisoformat(squareoff)
    left = (end.hour * 60 + end.minute) - (now.hour * 60 + now.minute)
    return max(1, math.ceil(left / minutes))


def precedent(symbol: str, df: pd.DataFrame, strategy, params: dict | None, risk_cfg: dict | None,
              costs=None, capital: float = 100000.0) -> dict:
    """What this same strategy actually did on this symbol's real history."""
    from . import backtest as bt

    res = bt.run({symbol: df}, strategy, params=params or {},
                 risk_cfg={**(risk_cfg or {}), "regime_filter": False, "max_trades_per_day": 99},
                 initial_capital=capital, costs=costs)
    trades = res.trades
    if not trades:
        return {"trades": 0, "note": f"{strategy.name} never fired on {symbol} in this history."}
    r = [t.r_multiple for t in trades]
    wins = [x for x in r if x > 0]
    reasons = {}
    for t in trades:
        reasons[t.reason] = reasons.get(t.reason, 0) + 1
    return {
        "trades": len(trades),
        "win_rate_pct": round(100 * len(wins) / len(trades), 1),
        "avg_r": round(float(np.mean(r)), 3),
        "best_r": round(max(r), 2), "worst_r": round(min(r), 2),
        "by_exit": reasons,
        "first": str(trades[0].entry_time.date()), "last": str(trades[-1].entry_time.date()),
    }
