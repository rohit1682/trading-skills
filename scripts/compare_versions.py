"""Compare strategies (e.g. v1 vs v2) over explicit date windows and stock baskets.

    python scripts/compare_versions.py --data-dir data/validation \
        --strategies ema_trend,ema_trend_v2 --universe watchlist \
        --window 2010-01-01:2021-01-01 --capital 50000 --json dev.json

``--universe random:N:SEED`` draws N stocks (fixed seed) from every daily CSV in
the data dir that is not in the watchlist and has bars before 2011, so the
draw includes names that later dropped out of the NIFTY.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import validate_strategies as vs  # noqa: E402
from growwbot import backtest as bt, strategies  # noqa: E402
from growwbot.costs import CostModel  # noqa: E402
from growwbot.risk import DEFAULTS  # noqa: E402

INDEXES = {"NIFTY", "BANKNIFTY", "NIFTYBEES"}


def pick_universe(spec: str, ddir: Path, repo: Path) -> list[str]:
    if spec.startswith("random:"):
        _, n, seed = spec.split(":")
        pool = []
        for f in sorted(ddir.glob("*_1day.csv")):
            sym = f.name[: -len("_1day.csv")]
            if sym in INDEXES or sym in vs.WATCHLIST:
                continue
            first = pd.read_csv(f, nrows=1).iloc[0, 0]
            if str(first) < "2011-01-01":
                pool.append(sym)
        rng = np.random.default_rng(int(seed))
        return sorted(rng.choice(pool, size=min(int(n), len(pool)), replace=False).tolist())
    return vs.universe(spec, repo)


def one(name, data, regime, capital, start, end, risk_over, mc_sims):
    strat = strategies.get(name)
    risk = {**DEFAULTS, **risk_over}
    kw = dict(strategy=strat, risk_cfg=risk, initial_capital=capital, slippage_pct=0.05, regime=regime,
              start=start, end=end)
    res = bt.run(data, costs=CostModel(), **kw)
    m = res.metrics()
    rs = np.array([t.r_multiple for t in res.trades])
    gross = bt.run(data, costs=vs.ZERO_COSTS, **{**kw, "slippage_pct": 0.0}).metrics()
    out = {k: m[k] for k in ("trades", "win_rate_pct", "breakeven_win_rate_pct", "avg_win_r", "avg_loss_r",
                             "profit_factor", "total_costs", "net_pnl")}
    out.update(vs.curve_stats(res.equity))
    out.update(vs.r_stats(rs))
    out["gross_return_pct"] = gross["total_return_pct"]
    out["buy_hold"] = vs.curve_stats(vs.buy_hold_curve(data, start, end))
    out["blocked_by"] = dict(sorted(res.blocked.items(), key=lambda kv: -kv[1]))
    if len(rs) >= 10:
        from growwbot import analytics
        mc = analytics.monte_carlo(rs.tolist(), risk_pct=risk["risk_per_trade_pct"], sims=mc_sims)
        out["montecarlo"] = {k: mc[k] for k in ("return_pct", "max_drawdown_pct", "prob_losing_money_pct", "losing_streak")}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--strategies", required=True)
    ap.add_argument("--universe", default="watchlist")
    ap.add_argument("--window", required=True, help="START:END (END exclusive, may be empty)")
    ap.add_argument("--interval")
    ap.add_argument("--capital", type=float, default=50000)
    ap.add_argument("--no-regime", action="store_true")
    ap.add_argument("--risk", default="", help="risk overrides, e.g. max_cost_pct_of_risk=0")
    ap.add_argument("--mc-sims", type=int, default=2000)
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    repo = Path(__file__).resolve().parent.parent
    ddir = Path(a.data_dir)
    syms = pick_universe(a.universe, ddir, repo)
    s, e = a.window.split(":")
    start, end = pd.Timestamp(s), (pd.Timestamp(e) if e else None)
    risk_over = {k: float(v) for k, v in (p.split("=") for p in a.risk.split() if p)}
    regime = None if a.no_regime else bt.regime_series(vs.read_csv(ddir / "NIFTY_1day.csv"))
    results, cache = [], {}
    for name in a.strategies.split(","):
        strat = strategies.get(name)
        interval = a.interval or strat.interval
        if interval not in cache:
            cache[interval] = vs.load(ddir, syms, interval)
        if a.interval and a.interval != strat.interval:
            strategies.STRATEGIES[name] = strategies.Strategy(strat.name, strat.description, a.interval, strat.intraday,
                                                              strat.fn, strat.defaults, strat.max_hold_bars)
        r = one(name, cache[interval], regime, a.capital, start, end, risk_over, a.mc_sims)
        r.update(strategy=name, universe=a.universe, symbols=sorted(cache[interval]), window=a.window,
                 capital=a.capital, regime_filter=regime is not None, risk_overrides=risk_over, interval=interval)
        results.append(r)
        print(f"{name:22s} n={r['trades']:4d} win={r['win_rate_pct']:5} be={r['breakeven_win_rate_pct']} "
              f"expR={r['exp_r']} t={r['t_stat']} ret={r.get('total_return_pct')} dd={r.get('max_drawdown_pct')} "
              f"sh={r.get('sharpe')} gross={r['gross_return_pct']} | BH {r['buy_hold'].get('total_return_pct')}",
              file=sys.stderr, flush=True)
    if a.json:
        Path(a.json).write_text(json.dumps(results, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
