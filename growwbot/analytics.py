"""Market and portfolio analytics behind the research skills.

Everything here is read-only: no function places or changes orders.

  * ``market_regime``      NIFTY trend + watchlist breadth + India VIX -> exposure posture
  * ``screen``             technical screens (presets or your own expression)
  * ``relative_strength``  momentum ranking vs NIFTY (IBD-style weighted returns)
  * ``pivot_levels``       classic pivots, CPR, Camarilla, recent swing highs/lows
  * ``monte_carlo``        bootstrap a trade list into drawdown / ruin odds
  * ``walk_forward``       parameter search judged only on unseen data
  * ``portfolio_review``   health check of holdings (trend, stop, concentration)
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from . import indicators as ind


# ----------------------------------------------------------------------------- universes

def universe(name_or_symbols, cfg: config.Config | None = None) -> list[str]:
    """``watchlist`` | a file name in universes/ (``nifty50``) | a path | a list of symbols."""
    if isinstance(name_or_symbols, (list, tuple)) and len(name_or_symbols) > 1:
        return [s.upper() for s in name_or_symbols]
    name = name_or_symbols[0] if isinstance(name_or_symbols, (list, tuple)) else name_or_symbols
    if name in (None, "", "watchlist"):
        return list((cfg or config.load()).watchlist)
    for path in (config.home() / "universes" / f"{name}.txt", Path(name)):
        if path.exists():
            lines = [ln.strip().upper() for ln in path.read_text().splitlines()]
            return [ln for ln in lines if ln and not ln.startswith("#")]
    return [str(name).upper()]


def _last(df: pd.DataFrame) -> pd.Series:
    return ind.add_all(df).iloc[-1]


# ----------------------------------------------------------------------------- regime

def market_regime(nifty: pd.DataFrame, frames: dict[str, pd.DataFrame], vix: pd.DataFrame | None = None) -> dict:
    """Score 0-100 from index trend, breadth and volatility, with a suggested posture."""
    n = _last(nifty)
    c = float(n["close"])
    ret20 = float(nifty["close"].iloc[-1] / nifty["close"].iloc[-21] - 1) if len(nifty) > 21 else float("nan")

    above50 = above200 = highs = lows = counted = 0
    for df in frames.values():
        if len(df) < 210:
            continue
        x = _last(df)
        counted += 1
        above50 += x["close"] > x["ema50"]
        above200 += x["close"] > x["ema200"]
        hi20 = df["high"].iloc[-21:-1].max()
        lo20 = df["low"].iloc[-21:-1].min()
        highs += df["close"].iloc[-1] > hi20
        lows += df["close"].iloc[-1] < lo20
    b50 = 100 * above50 / counted if counted else float("nan")
    b200 = 100 * above200 / counted if counted else float("nan")

    vix_level = vix_chg = None
    if vix is not None and len(vix) > 6:
        vix_level = float(vix["close"].iloc[-1])
        vix_chg = float(vix["close"].iloc[-1] / vix["close"].iloc[-6] - 1) * 100

    score, notes = 0, []
    def add(cond, pts, yes, no):
        nonlocal score
        if cond:
            score += pts
            notes.append(f"+{pts} {yes}")
        else:
            notes.append(f"+0 {no}")
    add(c > n["ema50"], 20, "NIFTY above its 50-day EMA", "NIFTY below its 50-day EMA")
    add(n["ema50"] > n["ema200"], 20, "50 EMA above 200 EMA (primary uptrend)", "50 EMA below 200 EMA")
    add(not math.isnan(b50) and b50 >= 50, 20, f"{b50:.0f}% of stocks above 50 EMA", f"only {b50:.0f}% of stocks above 50 EMA")
    add(not math.isnan(b200) and b200 >= 50, 15, f"{b200:.0f}% above 200 EMA", f"only {b200:.0f}% above 200 EMA")
    if vix_level is None:
        score += 8
        notes.append("+8 India VIX unavailable (neutral)")
    else:
        add(vix_level < 16, 15, f"India VIX calm at {vix_level:.1f}", f"India VIX elevated at {vix_level:.1f}")
    add(n["adx"] >= 20 and n["plus_di"] > n["minus_di"], 10, "ADX confirms an up-trend", "no confirmed up-trend on ADX")

    if score >= 70:
        posture, mult = "RISK-ON: normal position sizes", 1.0
    elif score >= 40:
        posture, mult = "CAUTIOUS: half risk per trade, fewer positions, tighter selection", 0.5
    else:
        posture, mult = "DEFENSIVE: no new swing longs; protect capital", 0.0
    return {
        "score": score, "posture": posture, "suggested_risk_multiplier": mult,
        "nifty_close": round(c, 2), "nifty_vs_ema50_pct": round(100 * (c / n["ema50"] - 1), 2),
        "nifty_vs_ema200_pct": round(100 * (c / n["ema200"] - 1), 2),
        "nifty_20d_return_pct": round(100 * ret20, 2) if not math.isnan(ret20) else None,
        "nifty_rsi14": round(float(n["rsi14"]), 1), "nifty_adx": round(float(n["adx"]), 1),
        "breadth_above_ema50_pct": None if math.isnan(b50) else round(b50, 1),
        "breadth_above_ema200_pct": None if math.isnan(b200) else round(b200, 1),
        "new_20d_highs": int(highs), "new_20d_lows": int(lows), "stocks_counted": counted,
        "india_vix": None if vix_level is None else round(vix_level, 2),
        "india_vix_5d_change_pct": None if vix_chg is None else round(vix_chg, 1),
        "reasons": notes,
    }


# ----------------------------------------------------------------------------- screener

PRESETS = {
    "trend_leaders": "close > ema50 and ema50 > ema200 and rsi14 >= 50 and rsi14 <= 70 and adx >= 20 and from_high_pct >= -10",
    "oversold_uptrend": "close > sma200 and (rsi14 < 35 or rsi2 < 10)",
    "breakout_watch": "from_20d_high_pct >= -3 and bb_width_rank <= 0.25 and close > ema50",
    "volume_surge": "rvol >= 2 and change_pct > 0",
    "supertrend_up": "st_dir == 1 and close > ema200 and adx >= 20",
    "near_52w_high": "from_high_pct >= -5 and close > ema50",
    "below_200ema": "close < ema200",
}


def screen_row(symbol: str, df: pd.DataFrame) -> dict | None:
    if len(df) < 60:
        return None
    x = ind.add_all(df)
    last = x.iloc[-1]
    width = (x["bb_upper"] - x["bb_lower"]) / x["bb_mid"]
    c = float(last["close"])
    row = {k: float(last[k]) for k in ("close", "ema9", "ema21", "ema50", "ema200", "sma200", "rsi14", "rsi2",
                                        "macd_hist", "adx", "st_dir", "atr14", "rvol")}
    row.update(
        symbol=symbol,
        change_pct=100 * (c / float(x["close"].iloc[-2]) - 1),
        from_high_pct=100 * (c / float(df["high"].tail(250).max()) - 1),
        from_20d_high_pct=100 * (c / float(df["high"].iloc[-21:-1].max()) - 1),
        bb_width_rank=float(width.tail(120).rank(pct=True).iloc[-1]),
        atr_pct=100 * float(last["atr14"]) / c,
    )
    return row


def screen(frames: dict[str, pd.DataFrame], expr: str) -> pd.DataFrame:
    """Rows that satisfy a preset name or a pandas query over the indicator columns."""
    rows = [r for s, df in frames.items() if (r := screen_row(s, df))]
    if not rows:
        return pd.DataFrame()
    table = pd.DataFrame(rows).set_index("symbol")
    query = PRESETS.get(expr, expr)
    out = table.query(query, engine="python")
    cols = ["close", "change_pct", "rsi14", "adx", "rvol", "from_high_pct", "atr_pct"]
    return out[cols].round(2).sort_values("from_high_pct", ascending=False)


# ----------------------------------------------------------------------------- relative strength

def relative_strength(frames: dict[str, pd.DataFrame], benchmark: pd.DataFrame | None = None) -> pd.DataFrame:
    """IBD-style weighted momentum: 40 % last 3 months, 20 % each of the three quarters before.

    ``rs_rating`` is the percentile (1-99) within the universe you passed in.
    """
    def perf(close: pd.Series, days: int) -> float:
        return float(close.iloc[-1] / close.iloc[-days - 1] - 1) if len(close) > days else float("nan")

    rows = []
    bench_3m = perf(benchmark["close"], 63) if benchmark is not None else float("nan")
    for s, df in frames.items():
        c = df["close"]
        if len(c) < 130:
            continue
        q = [perf(c, 63), perf(c, 126), perf(c, 189), perf(c, 252)]
        q = [v if not math.isnan(v) else q[i - 1] if i else 0.0 for i, v in enumerate(q)]
        score = 0.4 * q[0] + 0.2 * q[1] + 0.2 * q[2] + 0.2 * q[3]
        rows.append({"symbol": s, "ret_1m_pct": 100 * perf(c, 21), "ret_3m_pct": 100 * q[0], "ret_6m_pct": 100 * q[1],
                     "ret_12m_pct": 100 * q[3], "vs_nifty_3m_pct": 100 * (q[0] - bench_3m) if not math.isnan(bench_3m) else None,
                     "above_ema50": bool(c.iloc[-1] > ind.ema(c, 50).iloc[-1]), "score": score})
    if not rows:
        return pd.DataFrame()
    t = pd.DataFrame(rows).set_index("symbol")
    t["rs_rating"] = (t["score"].rank(pct=True) * 98 + 1).round().astype(int)
    return t.drop(columns="score").sort_values("rs_rating", ascending=False).round(2)


# ----------------------------------------------------------------------------- levels

def pivot_levels(daily: pd.DataFrame, swing_lookback: int = 60) -> dict:
    """Levels for the NEXT session from the last completed daily bar, plus nearby swing support/resistance."""
    last = daily.iloc[-1]
    h, l, c = float(last["high"]), float(last["low"]), float(last["close"])
    p = (h + l + c) / 3
    bc = (h + l) / 2
    tc = 2 * p - bc
    rng = h - l
    classic = {"R3": h + 2 * (p - l), "R2": p + rng, "R1": 2 * p - l, "P": p, "S1": 2 * p - h, "S2": p - rng, "S3": l - 2 * (h - p)}
    cam = {"H4": c + rng * 1.1 / 2, "H3": c + rng * 1.1 / 4, "L3": c - rng * 1.1 / 4, "L4": c - rng * 1.1 / 2}
    cpr_top, cpr_bot = max(tc, bc), min(tc, bc)
    width_pct = 100 * (cpr_top - cpr_bot) / p
    # 5-bar fractal swing points over the lookback
    d = daily.tail(swing_lookback)
    hi, lo = d["high"], d["low"]
    sh = hi[(hi == hi.rolling(5, center=True).max())].dropna()
    sl = lo[(lo == lo.rolling(5, center=True).min())].dropna()
    return {
        "based_on": str(daily.index[-1].date()), "prev_high": round(h, 2), "prev_low": round(l, 2), "prev_close": round(c, 2),
        "classic": {k: round(v, 2) for k, v in classic.items()},
        "cpr": {"TC": round(cpr_top, 2), "P": round(p, 2), "BC": round(cpr_bot, 2), "width_pct": round(width_pct, 3),
                "read": "narrow CPR: trending day more likely" if width_pct < 0.25 else
                        "wide CPR: range-bound day more likely" if width_pct > 0.6 else "average CPR"},
        "camarilla": {k: round(v, 2) for k, v in cam.items()},
        # nearest swing points above (resistance) and below (support) the last close
        "resistance": [round(float(v), 2) for v in sorted({*sh, *sl}) if v > c][:3],
        "support": [round(float(v), 2) for v in sorted({*sh, *sl}, reverse=True) if v < c][:3],
        "atr14": round(float(ind.atr(daily).iloc[-1]), 2),
    }


# ----------------------------------------------------------------------------- monte carlo

def monte_carlo(r_multiples: list[float], risk_pct: float = 0.5, n_trades: int | None = None, sims: int = 5000,
                ruin_dd_pct: float = 30.0, seed: int = 42) -> dict:
    """Bootstrap the R-multiples of past trades into many alternative orderings.

    Each trade changes equity by ``R x risk_pct %`` (compounded), so the result
    is about the strategy's distribution, independent of account size.
    """
    r = np.asarray([x for x in r_multiples if not math.isnan(x)], dtype=float)
    if len(r) < 10:
        raise ValueError("need at least 10 trades for a meaningful simulation")
    n = n_trades or len(r)
    rng = np.random.default_rng(seed)
    draws = rng.choice(r, size=(sims, n), replace=True)
    equity = np.cumprod(1 + draws * risk_pct / 100.0, axis=1)
    peak = np.maximum.accumulate(np.concatenate([np.ones((sims, 1)), equity], axis=1), axis=1)[:, 1:]
    dd = (equity / peak - 1).min(axis=1) * 100
    final = (equity[:, -1] - 1) * 100
    # longest losing streak per simulated path
    losing = draws < 0
    streak = np.zeros(sims, dtype=int)
    cur = np.zeros(sims, dtype=int)
    for j in range(n):
        cur = np.where(losing[:, j], cur + 1, 0)
        streak = np.maximum(streak, cur)
    pct = lambda a, q: round(float(np.percentile(a, q)), 2)
    return {
        "trades_in_sample": int(len(r)), "trades_per_path": n, "simulations": sims, "risk_per_trade_pct": risk_pct,
        "avg_r": round(float(r.mean()), 3), "win_rate_pct": round(100 * float((r > 0).mean()), 1),
        "return_pct": {"p5": pct(final, 5), "median": pct(final, 50), "p95": pct(final, 95)},
        "max_drawdown_pct": {"median": pct(dd, 50), "p95_worst": pct(dd, 5), "p99_worst": pct(dd, 1)},
        "prob_losing_money_pct": round(100 * float((final < 0).mean()), 1),
        f"prob_drawdown_over_{int(ruin_dd_pct)}pct": round(100 * float((dd <= -ruin_dd_pct).mean()), 2),
        "losing_streak": {"median": int(np.median(streak)), "p95": int(np.percentile(streak, 95))},
    }


# ----------------------------------------------------------------------------- walk-forward

DEFAULT_GRIDS = {
    "ema_trend": {"adx_min": [15, 20, 25], "stop_atr": [1.5, 2.0, 2.5], "target_atr": [3.0, 4.0]},
    "supertrend_adx": {"st_mult": [2.0, 3.0], "adx_min": [15, 20, 25], "rr": [1.5, 2.0, 3.0]},
    "rsi2_reversion": {"rsi_entry": [5, 10, 15], "stop_atr": [2.0, 3.0]},
    "macd_momentum": {"rsi_min": [45, 50, 55], "stop_atr": [1.5, 2.0, 2.5]},
    "donchian_breakout": {"period": [20, 40, 55], "exit_period": [10, 20], "rvol_min": [1.0, 1.5]},
    "vwap_pullback": {"rr": [1.5, 2.0, 2.5], "rsi_lo": [40, 45]},
    "orb": {"range_minutes": [15, 30], "rr": [1.5, 2.0, 3.0]},
}


def parse_grid(text: str | None, strategy_name: str) -> dict:
    """'adx_min=20,25 rr=2,3' -> {'adx_min': [20, 25], 'rr': [2, 3]}"""
    if not text:
        return DEFAULT_GRIDS.get(strategy_name, {})
    grid = {}
    for part in text.split():
        k, v = part.split("=", 1)
        grid[k] = [float(x) if "." in x else int(x) for x in v.split(",")]
    return grid


@dataclass
class Fold:
    train_start: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp | None
    best_params: dict
    train_score: float
    test_return_pct: float
    test_trades: int
    test_pf: float | None


def walk_forward(data: dict[str, pd.DataFrame], strategy, grid: dict, folds: int = 4, run_kwargs: dict | None = None,
                 min_trades: int = 5) -> dict:
    """Anchored walk-forward: optimise on everything before each test window, then trade the window blind."""
    from . import backtest as bt

    run_kwargs = run_kwargs or {}
    all_ts = sorted(set().union(*[df.index for df in data.values()]))
    edges = [all_ts[int(len(all_ts) * i / (folds + 1))] for i in range(1, folds + 1)] + [None]
    combos = [dict(zip(grid, vals)) for vals in itertools.product(*grid.values())] if grid else [{}]

    def score(m: dict) -> float:
        if m["trades"] < min_trades:
            return -1e9
        pf = m["profit_factor"] or 0.0
        return m["total_return_pct"] + 5 * min(pf, 3.0) + 0.5 * m["max_drawdown_pct"]

    results: list[Fold] = []
    for i in range(folds):
        train_end, test_start, test_end = edges[i], edges[i], edges[i + 1]
        best, best_s = {}, -1e18
        for p in combos:
            m = bt.run(data, strategy, params=p, end=train_end, **run_kwargs).metrics()
            s = score(m)
            if s > best_s:
                best, best_s = p, s
        tm = bt.run(data, strategy, params=best, start=test_start, end=test_end, **run_kwargs).metrics()
        results.append(Fold(all_ts[0], test_start, test_end, best, round(best_s, 2), tm["total_return_pct"],
                            tm["trades"], tm["profit_factor"]))
    oos = [f.test_return_pct for f in results]
    default_oos = []
    for i in range(folds):
        dm = bt.run(data, strategy, params={}, start=edges[i], end=edges[i + 1], **run_kwargs).metrics()
        default_oos.append(dm["total_return_pct"])
    chosen = [tuple(sorted(f.best_params.items())) for f in results]
    stable = len(set(chosen)) == 1
    oos_total = 100 * (np.prod([1 + x / 100 for x in oos]) - 1)
    default_total = 100 * (np.prod([1 + x / 100 for x in default_oos]) - 1)
    test_trades = sum(f.test_trades for f in results)
    if oos_total <= 0 and default_total <= 0:
        verdict = "Neither tuned nor default parameters made money out of sample: don't trade this strategy on these symbols."
    elif oos_total > default_total:
        verdict = "Tuned parameters beat the defaults out of sample."
    else:
        verdict = "Tuning did NOT beat the defaults out of sample: keep the defaults (the tuning was curve-fitting)."
    if test_trades < 30:
        verdict += f" Only {test_trades} out-of-sample trades: too few to rely on."
    if not stable:
        verdict += " The best parameters changed between folds, a sign of noise rather than a robust setting."
    return {
        "strategy": strategy.name, "combinations_tested": len(combos), "folds": [f.__dict__ for f in results],
        "oos_return_pct_compounded": round(oos_total, 2),
        "default_params_oos_return_pct_compounded": round(default_total, 2),
        "oos_trades": test_trades, "params_stable_across_folds": stable, "verdict": verdict,
    }


# ----------------------------------------------------------------------------- portfolio

def portfolio_review(holdings: list[dict], frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """holdings: [{'symbol', 'qty', 'avg_price'}] -> one row per holding with flags."""
    rows, total = [], 0.0
    for h in holdings:
        df = frames.get(h["symbol"])
        if df is None or len(df) < 60:
            continue
        x = ind.add_all(df).iloc[-1]
        c = float(x["close"])
        value = c * float(h["qty"])
        total += value
        stop = max(c - 2.5 * float(x["atr14"]), float(x["ema50"]) * 0.98 if c > x["ema50"] else c - 2.5 * float(x["atr14"]))
        trend = "up" if c > x["ema50"] > x["ema200"] else "down" if c < x["ema50"] < x["ema200"] else "mixed"
        rows.append({"symbol": h["symbol"], "qty": h["qty"], "avg_price": round(float(h["avg_price"]), 2), "ltp": round(c, 2),
                     "pnl_pct": round(100 * (c / float(h["avg_price"]) - 1), 2) if h["avg_price"] else None,
                     "value": round(value, 2), "trend": trend, "rsi14": round(float(x["rsi14"]), 1),
                     "from_52w_high_pct": round(100 * (c / float(df["high"].tail(250).max()) - 1), 1),
                     "suggested_stop": round(stop, 2), "stop_risk_pct": round(100 * (1 - stop / c), 2)})
    t = pd.DataFrame(rows)
    if t.empty:
        return t
    t["weight_pct"] = (100 * t["value"] / total).round(1)
    flags = []
    for _, r in t.iterrows():
        f = []
        if r.weight_pct > 25:
            f.append("concentrated >25%")
        if r.trend == "down":
            f.append("downtrend (below 50 & 200 EMA)")
        if r.pnl_pct is not None and r.pnl_pct < -15 and r.trend != "up":
            f.append("deep loss without uptrend")
        if r.rsi14 > 75:
            f.append("overbought, consider trailing the stop")
        flags.append("; ".join(f))
    t["flags"] = flags
    return t.sort_values("value", ascending=False).set_index("symbol")
