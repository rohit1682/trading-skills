"""Honest historical validation of every growwbot strategy.

Runs each strategy through the normal backtester (next-bar fills, Groww costs,
slippage, every risk rule) on a basket of CSV candles, with a time split into
in-sample (IS) and out-of-sample (OOS) windows, and adds what the plain
``backtest`` command doesn't print:

  * expectancy in R with a t-statistic and a bootstrap 95 % interval,
  * the number of trades the observed edge would need to be statistically real,
  * the same run with zero costs and zero slippage (how much the charges eat),
  * equal-weight buy-and-hold of the same basket and of NIFTY over the same windows,
  * a Monte Carlo of the OOS trades,
  * a look-ahead probe: signals computed on truncated history must equal the
    signals computed on full history, bar for bar.

Usage (CSV files named <SYMBOL>_<interval>.csv, e.g. from scripts/fetch_data.py):

    python scripts/validate_strategies.py --data-dir data/validation --universe watchlist --capital 50000
    python scripts/validate_strategies.py --data-dir data/validation --universe nifty50 --json out.json

Parameters are the strategy defaults. Nothing here is tuned.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from growwbot import analytics, backtest as bt, strategies  # noqa: E402
from growwbot.costs import CostModel  # noqa: E402
from growwbot.risk import DEFAULTS  # noqa: E402

WATCHLIST = ["RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS", "SBIN", "AXISBANK", "LT", "ITC", "BHARTIARTL",
             "KOTAKBANK", "HINDUNILVR", "MARUTI", "SUNPHARMA", "TITAN"]
ZERO_COSTS = CostModel(**{k: 0.0 for k in CostModel.__dataclass_fields__})


def read_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.lower().strip() for c in df.columns]
    ts = next(c for c in df.columns if c in ("ts", "date", "datetime", "timestamp"))
    df.index = pd.DatetimeIndex(pd.to_datetime(df.pop(ts)), name="ts")
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df.dropna(subset=["open", "high", "low", "close"])
    # Yahoo sometimes prints zero-range placeholder bars on holidays: drop them.
    df = df[~((df["high"] == df["low"]) & (df["volume"].fillna(0) == 0))]
    return df


def load(data_dir: Path, symbols: list[str], interval: str) -> dict[str, pd.DataFrame]:
    out = {}
    for s in symbols:
        p = data_dir / f"{s}_{interval}.csv"
        if p.exists():
            df = read_csv(p)
            if len(df) > 50:
                out[s] = df
    return out


def universe(name: str, repo: Path) -> list[str]:
    if name == "watchlist":
        return WATCHLIST
    if name == "nifty50":
        return [l.strip() for l in (repo / "universes" / "nifty50.txt").read_text().splitlines()
                if l.strip() and not l.startswith("#")]
    return [s.strip().upper() for s in name.split(",")]


# ----------------------------------------------------------------------------- statistics

def r_stats(rs: np.ndarray, seed: int = 7) -> dict:
    n = len(rs)
    if n == 0:
        return {"exp_r": None, "t_stat": None, "ci95_r": None, "trades_needed_t2": None}
    mean = float(rs.mean())
    sd = float(rs.std(ddof=1)) if n > 1 else float("nan")
    t = mean / (sd / math.sqrt(n)) if n > 1 and sd > 0 else float("nan")
    rng = np.random.default_rng(seed)
    boots = rng.choice(rs, size=(5000, n), replace=True).mean(axis=1) if n > 1 else np.array([mean])
    lo, hi = np.percentile(boots, [2.5, 97.5])
    # trades needed for t = 2 at this mean and spread (only meaningful if the mean is positive)
    need = math.ceil((2 * sd / mean) ** 2) if mean > 0 and sd > 0 else None
    return {"exp_r": round(mean, 3), "sd_r": round(sd, 2) if not math.isnan(sd) else None,
            "t_stat": round(t, 2) if not math.isnan(t) else None,
            "ci95_r": [round(float(lo), 3), round(float(hi), 3)], "trades_needed_t2": need}


def curve_stats(eq: pd.Series) -> dict:
    eq = eq.dropna()
    if len(eq) < 3:
        return {}
    daily = eq.resample("1D").last().dropna()
    rets = daily.pct_change().dropna()
    years = max((daily.index[-1] - daily.index[0]).days / 365.25, 1e-9)
    total = float(daily.iloc[-1] / daily.iloc[0] - 1)
    cagr = (1 + total) ** (1 / years) - 1 if years >= 0.25 and total > -1 else float("nan")
    sharpe = float(rets.mean() / rets.std() * math.sqrt(252)) if rets.std() > 0 else float("nan")
    dd = float((daily / daily.cummax() - 1).min())
    r = lambda x: None if x is None or (isinstance(x, float) and math.isnan(x)) else round(x, 2)
    return {"total_return_pct": r(100 * total), "cagr_pct": r(100 * cagr), "max_drawdown_pct": r(100 * dd),
            "sharpe": r(sharpe)}


def buy_hold_curve(data: dict[str, pd.DataFrame], start, end) -> pd.Series:
    """Equal-weight, buy at the first open in the window, hold (no rebalancing).
    Uses Yahoo's dividend-adjusted close when present, so dividends count. No costs."""
    legs = []
    for df in data.values():
        w = df[df.index >= start]
        if end is not None:
            w = w[w.index < end]
        if len(w) < 2:
            continue
        px = w["adj close"] if "adj close" in w.columns else w["close"]
        # scale the adjusted series so the first open is the entry price
        factor = (px / w["close"]).iloc[0]
        legs.append(px / (w["open"].iloc[0] * factor))
    if not legs:
        return pd.Series(dtype=float)
    m = pd.concat(legs, axis=1).ffill()
    # symbols listed after the window starts enter at 1.0 on their first day (cash until then)
    return m.fillna(1.0).mean(axis=1)


def time_in_market(res: bt.Result, timeline: pd.DatetimeIndex) -> float:
    if not res.trades or len(timeline) == 0:
        return 0.0
    days = set()
    for t in res.trades:
        days.update(pd.date_range(pd.Timestamp(t.entry_time).normalize(), pd.Timestamp(t.exit_time).normalize()).date)
    tl = set(timeline.normalize().date)
    return round(100 * len(days & tl) / len(tl), 1)


# ----------------------------------------------------------------------------- look-ahead probe

def lookahead_probe(df: pd.DataFrame, strat, cuts: int = 12, seed: int = 1) -> dict:
    """Signals on df[:k] must match signals on the full df for every bar < k."""
    full = strat.signals(df)
    rng = np.random.default_rng(seed)
    lo = min(len(df) - 2, 260)
    ks = sorted(set(rng.integers(lo, len(df) - 1, size=cuts).tolist()))
    mismatches = 0
    for k in ks:
        part = strat.signals(df.iloc[:k])
        a, b = part, full.iloc[:k]
        for col in ("entry", "exit"):
            mismatches += int((a[col].values != b[col].values).sum())
        for col in ("stop", "target"):
            x, y = a[col].to_numpy(float), b[col].to_numpy(float)
            both = ~(np.isnan(x) & np.isnan(y))
            mismatches += int((~np.isclose(x[both], y[both], rtol=1e-9, atol=1e-9)).sum())
    return {"cuts_checked": len(ks), "mismatched_values": mismatches}


# ----------------------------------------------------------------------------- one strategy

def run_strategy(name: str, data: dict, regime, capital: float, split: float, start, mc_sims: int) -> dict:
    strat = strategies.get(name)
    risk = dict(DEFAULTS)
    kw = dict(strategy=strat, risk_cfg=risk, initial_capital=capital, slippage_pct=0.05, regime=regime)
    timeline = pd.DatetimeIndex(sorted(set().union(*[df.index for df in data.values()])))
    timeline = timeline[timeline >= start]
    cut = timeline[int(len(timeline) * split)]
    windows = {"full": (start, None), "IS": (start, cut), "OOS": (cut, None)}
    out = {"strategy": name, "interval": strat.interval, "symbols": len(data),
           "start": str(timeline[0].date()), "cut": str(cut.date()), "end": str(timeline[-1].date())}
    for label, (s, e) in windows.items():
        res = bt.run(data, start=s, end=e, costs=CostModel(), **kw)
        m = res.metrics()
        rs = np.array([t.r_multiple for t in res.trades])
        gross = bt.run(data, start=s, end=e, **{**kw, "slippage_pct": 0.0}, costs=ZERO_COSTS).metrics()
        bh = curve_stats(buy_hold_curve(data, s, e))
        tl = timeline[timeline >= s]
        if e is not None:
            tl = tl[tl < e]
        out[label] = {
            **{k: m[k] for k in ("trades", "win_rate_pct", "breakeven_win_rate_pct", "avg_win_r", "avg_loss_r",
                                 "expectancy_per_trade", "profit_factor", "total_costs", "net_pnl",
                                 "signals_blocked_by_risk")},
            **curve_stats(res.equity),
            **r_stats(rs),
            "time_in_market_pct": time_in_market(res, tl),
            "gross_return_pct": gross["total_return_pct"], "gross_trades": gross["trades"],
            "buy_hold": bh,
            "blocked_by": dict(sorted(res.blocked.items(), key=lambda kv: -kv[1])),
            "exit_reasons": pd.Series([t.reason for t in res.trades]).value_counts().to_dict() if res.trades else {},
        }
        if label == "OOS" and len(rs) >= 10:
            out["montecarlo_oos"] = analytics.monte_carlo(rs.tolist(), risk_pct=risk["risk_per_trade_pct"], sims=mc_sims)
        if label == "full" and len(rs) >= 10:
            out["montecarlo_full"] = analytics.monte_carlo(rs.tolist(), risk_pct=risk["risk_per_trade_pct"], sims=mc_sims)
    sym = next(iter(data))
    out["lookahead_probe"] = lookahead_probe(data[sym], strat)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--universe", default="watchlist", help="watchlist | nifty50 | comma list")
    ap.add_argument("--strategies", default="all")
    ap.add_argument("--interval", help="override the strategy's interval (e.g. 15minute)")
    ap.add_argument("--capital", type=float, default=50000)
    ap.add_argument("--split", type=float, default=0.7)
    ap.add_argument("--start", default="2010-01-01", help="first tradable date (earlier bars only warm up indicators)")
    ap.add_argument("--no-regime", action="store_true")
    ap.add_argument("--mc-sims", type=int, default=5000)
    ap.add_argument("--json", help="write results here")
    a = ap.parse_args(argv)

    repo = Path(__file__).resolve().parent.parent
    ddir = Path(a.data_dir)
    names = list(strategies.STRATEGIES) if a.strategies == "all" else a.strategies.split(",")
    syms = universe(a.universe, repo)
    regime = None
    if not a.no_regime and (ddir / "NIFTY_1day.csv").exists():
        regime = bt.regime_series(read_csv(ddir / "NIFTY_1day.csv"))
    results, cache = [], {}
    for name in names:
        strat = strategies.get(name)
        interval = a.interval or strat.interval
        if a.interval:
            strat = strategies.Strategy(strat.name, strat.description, interval, strat.intraday, strat.fn,
                                        strat.defaults, strat.max_hold_bars)
            strategies.STRATEGIES[name] = strat
        if interval not in cache:
            cache[interval] = load(ddir, syms, interval)
        data = cache[interval]
        if not data:
            print(f"[skip] {name}: no {interval} CSVs in {ddir}", file=sys.stderr)
            continue
        start = pd.Timestamp(a.start) if not strat.intraday else min(df.index[0] for df in data.values())
        print(f"[run] {name} on {len(data)} symbols, {interval}", file=sys.stderr, flush=True)
        r = run_strategy(name, data, regime, a.capital, a.split, start, a.mc_sims)
        r.update(universe=a.universe, capital=a.capital, regime_filter=regime is not None)
        results.append(r)
        o = r["OOS"]
        print(f"      OOS trades {o['trades']}, win {o['win_rate_pct']}% vs breakeven {o['breakeven_win_rate_pct']}%, "
              f"exp {o['exp_r']}R (t {o['t_stat']}), return {o.get('total_return_pct')}% vs B&H "
              f"{o['buy_hold'].get('total_return_pct')}%", file=sys.stderr, flush=True)
    if a.json:
        Path(a.json).write_text(json.dumps(results, indent=1, default=str))
    else:
        print(json.dumps(results, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
