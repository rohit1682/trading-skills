"""Command line: ``python -m growwbot <command>``. Run ``python -m growwbot -h`` for the list."""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime

import pandas as pd

from . import backtest as bt
from . import broker as brk
from . import alerts, analytics, config, data, indicators, odds as odds_mod, risk, strategies
from .costs import CostModel
from .engine import Engine, now_ist

DISCLAIMER = ("Not financial advice. Backtests and paper results do not guarantee live profits; "
              "most intraday traders lose money (SEBI, FY23: 7 in 10).")


def _print(obj, as_json: bool) -> None:
    if as_json:
        print(json.dumps(obj, indent=2, default=str))
    elif isinstance(obj, dict):
        w = max((len(str(k)) for k in obj), default=0)
        for k, v in obj.items():
            print(f"  {str(k).ljust(w)}  {v}")
    else:
        print(obj)


# ----------------------------------------------------------------------------- doctor

def cmd_doctor(args, cfg):
    ok = True
    print(f"config:        {cfg.path}")
    print(f"mode:          {cfg.mode}   capital: Rs {cfg.capital:,.0f}   strategy: {cfg.strategy.get('name')}")
    print(f"watchlist:     {len(cfg.watchlist)} symbols")
    for mod in ("pandas", "numpy", "growwapi", "pyotp", "yfinance"):
        try:
            __import__(mod)
            print(f"python pkg:    {mod} OK")
        except ImportError:
            print(f"python pkg:    {mod} MISSING (pip install -r requirements.txt)")
            ok = ok and mod not in ("pandas", "numpy")
    from .groww_client import Groww, has_credentials

    if has_credentials():
        try:
            prof = Groww().call("get_user_profile")
            print(f"groww login:   OK ({(prof or {}).get('ucc', 'profile fetched')})")
            print(f"groww cash:    Rs {Groww().cash_available():,.2f}")
        except Exception as e:
            ok = False
            print(f"groww login:   FAILED: {e}")
    else:
        print("groww login:   no credentials in .env (paper mode will use yfinance prices)")
    missing = brk.live_blockers(cfg, live_flag=True)
    print("live trading:  " + ("ENABLED when you pass --live" if not missing else "OFF (" + "; ".join(missing) + ")"))
    print("kill switch:   " + ("ON" if risk.kill_switch_active() else "off"))
    return 0 if ok else 1


# ----------------------------------------------------------------------------- analysis

def snapshot(symbol: str, interval: str, source: str = "auto") -> dict:
    df = data.load(symbol, interval, days=400 if not data.is_intraday(interval) else 20, source=source)
    df = data.completed_bars(df, interval, now_ist())
    x = indicators.add_all(df, intraday=data.is_intraday(interval)).iloc[-1]
    c = float(x["close"])
    trend = "up" if c > x["ema50"] > x["ema200"] else "down" if c < x["ema50"] < x["ema200"] else "mixed"
    snap = {
        "symbol": symbol, "interval": interval, "bar": str(df.index[-1]), "close": round(c, 2),
        "trend": trend,
        "ema9/21/50/200": [round(float(x[k]), 2) for k in ("ema9", "ema21", "ema50", "ema200")],
        "rsi14": round(float(x["rsi14"]), 1), "rsi2": round(float(x["rsi2"]), 1),
        "macd/signal/hist": [round(float(x[k]), 2) for k in ("macd", "macd_signal", "macd_hist")],
        "adx": round(float(x["adx"]), 1),
        "supertrend": f"{'UP' if x['st_dir'] == 1 else 'DOWN'} @ {float(x['supertrend']):.2f}",
        "atr14": round(float(x["atr14"]), 2), "atr_pct": round(100 * float(x["atr14"]) / c, 2),
        "bollinger": [round(float(x[k]), 2) for k in ("bb_lower", "bb_mid", "bb_upper")],
        "rvol": round(float(x["rvol"]), 2) if not math.isnan(x["rvol"]) else None,
        "52w_high_dist_pct": round(100 * (c / float(df["high"].tail(250).max()) - 1), 1),
    }
    if "vwap" in x:
        snap["vwap"] = round(float(x["vwap"]), 2)
    fired = []
    for s in strategies.STRATEGIES.values():
        if s.interval != interval:
            continue
        sig = s.signals(df).iloc[-1]
        if bool(sig["entry"]):
            fired.append({"strategy": s.name, "stop": round(float(sig["stop"]), 2),
                          "target": None if math.isnan(sig["target"]) else round(float(sig["target"]), 2)})
    snap["entry_signals"] = fired
    return snap


def cmd_analyze(args, cfg):
    _print(snapshot(args.symbol.upper(), args.interval, args.source), args.json)
    if not args.json:
        print("\n" + DISCLAIMER)


def cmd_scan(args, cfg):
    names = list(strategies.STRATEGIES) if args.all else [args.strategy or cfg.strategy["name"]]
    symbols = [s.upper() for s in (args.symbols or cfg.watchlist)]
    rows, cache = [], {}
    for name in names:
        strat = strategies.get(name)
        for sym in symbols:
            key = (sym, strat.interval)
            try:
                if key not in cache:
                    days = 400 if not strat.intraday else 20
                    cache[key] = data.completed_bars(data.load(sym, strat.interval, days, args.source), strat.interval, now_ist())
                df = cache[key]
                sig = strat.signals(df, **(cfg.strategy.get("params", {}) if name == cfg.strategy["name"] else {})).iloc[-1]
            except Exception as e:
                print(f"[warn] {sym}: {e}", file=sys.stderr)
                continue
            if bool(sig["entry"]):
                c = float(df["close"].iloc[-1])
                stop = float(sig["stop"])
                tgt = None if math.isnan(sig["target"]) else round(float(sig["target"]), 2)
                rows.append({"symbol": sym, "strategy": name, "tested": strategies.status(name)[0],
                             "bar": str(df.index[-1]), "close": round(c, 2),
                             "stop": round(stop, 2), "target": tgt, "risk_pct": round(100 * (c - stop) / c, 2),
                             "rsi14": round(float(indicators.rsi(df["close"]).iloc[-1]), 1)})
    rows.sort(key=lambda r: r["risk_pct"])
    if args.json:
        _print(rows, True)
        return
    if not rows:
        print("No entry signals on the latest completed bar. (No signal is a valid answer: don't force trades.)")
        return
    print(pd.DataFrame(rows).to_string(index=False))
    print("\nNext: `python -m growwbot size SYMBOL --entry PRICE --stop STOP` to size one. " + DISCLAIMER)


# ----------------------------------------------------------------------------- backtest

def _load_universe(symbols, interval, days, source, csv_dir=None):
    out = {}
    for s in symbols:
        try:
            csv = f"{csv_dir}/{s}_{interval}.csv" if csv_dir else None
            out[s] = data.load(s, interval, days, source, csv=csv)
        except Exception as e:
            print(f"[warn] {s}: {e}", file=sys.stderr)
    return out


def cmd_backtest(args, cfg):
    names = list(strategies.STRATEGIES) if args.all else [args.strategy or cfg.strategy["name"]]
    symbols = [s.upper() for s in (args.symbols or cfg.watchlist)]
    capital = float(args.capital or cfg.backtest.get("initial_capital", cfg.capital))
    slip = float((cfg.execution or {}).get("slippage_pct", 0.05))
    costs = CostModel.from_dict(cfg.costs)
    summary, cache = [], {}
    regime = None
    if cfg.risk.get("regime_filter", True) and not args.no_regime:
        try:
            regime = bt.regime_series(data.load("NIFTY", "1day", int(args.days or cfg.backtest.get("days", 730)) + 120,
                                                args.source, csv=f"{args.csv_dir}/NIFTY_1day.csv" if args.csv_dir else None))
        except Exception as e:
            print(f"[warn] regime filter off for this backtest (no NIFTY data): {e}", file=sys.stderr)
    for name in names:
        strat = strategies.get(name)
        days = int(args.days or (cfg.backtest.get("days", 730) if not strat.intraday else 59))
        key = strat.interval
        if key not in cache:
            cache[key] = _load_universe(symbols, strat.interval, days, args.source, args.csv_dir)
        universe = cache[key]
        if not universe:
            print("No data loaded.")
            return 1
        params = cfg.strategy.get("params", {}) if name == cfg.strategy["name"] else {}
        kw = dict(strategy=strat, params=params, risk_cfg=cfg.risk, initial_capital=capital,
                  slippage_pct=slip, costs=costs, regime=regime)
        res = bt.run(universe, **kw)
        m = res.metrics()
        bh = bt.buy_and_hold(universe, capital)
        row = {"strategy": name, **m, "buy_hold_return_pct": bh.get("total_return_pct")}
        if args.split:
            cut = bt.cut_point(universe, args.split)
            ins = bt.run(universe, **kw, end=cut).metrics()
            oos = bt.run(universe, **kw, start=cut).metrics()
            row["in_sample_return_pct"] = ins["total_return_pct"]
            row["out_of_sample_return_pct"] = oos["total_return_pct"]
            row["out_of_sample_trades"] = oos["trades"]
            row["out_of_sample_pf"] = oos["profit_factor"]
        summary.append(row)
        out_dir = config.state_dir() / "backtests"
        out_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        if res.trades:
            res.trades_df().to_csv(out_dir / f"{name}-{stamp}-trades.csv", index=False)
        res.equity.to_csv(out_dir / f"{name}-{stamp}-equity.csv", header=["equity"])
        if not args.json and not args.all:
            st, why = strategies.status(name)
            print(f"\n== {name}: {strat.description}")
            print(f"   historical test status: {st.upper()} ({why})")
            print(f"   {len(universe)} symbols, interval {strat.interval}, capital Rs {capital:,.0f}, costs + {slip}% slippage")
            _print(row, False)
            print(f"   trades -> {out_dir}/{name}-{stamp}-trades.csv")
    if args.json:
        _print(summary, True)
    elif args.all:
        cols = ["strategy", "trades", "win_rate_pct", "total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe",
                "profit_factor", "total_costs", "buy_hold_return_pct"]
        if args.split:
            cols += ["out_of_sample_return_pct", "out_of_sample_pf"]
        print(pd.DataFrame(summary)[cols].to_string(index=False))
    if not args.json:
        print("\nRead this honestly: fewer than ~30 trades is noise; a profit factor under ~1.3 after costs is fragile;"
              " if out-of-sample is much worse than in-sample, the rules are overfit. Compare win_rate_pct with"
              " breakeven_win_rate_pct: a 35% win rate is fine if the winners are big enough. " + DISCLAIMER)
    return 0


# ----------------------------------------------------------------------------- risk / orders

def cmd_size(args, cfg):
    rm = risk.RiskManager(cfg.risk, capital=cfg.capital, persist=True, costs=CostModel.from_dict(cfg.costs))
    eng_positions = Engine(cfg, brk.PaperBroker(cfg) if not args.live else brk.make_broker(cfg, True), log=lambda *_: None).positions
    dec = rm.check_entry(args.symbol.upper(), args.entry, args.stop, args.target, args.now or now_ist(),
                         len(eng_positions), args.intraday, cash=cfg.capital,
                         open_risk=sum(p["qty"] * max(0, p["entry"] - p["stop"]) for p in eng_positions.values()))
    qty = rm.size(args.entry, args.stop, cfg.capital)
    c = CostModel.from_dict(cfg.costs)
    rt = c.round_trip(args.entry, args.stop, max(qty, 1), args.intraday)
    out = {
        "verdict": "PASS" if dec.ok else "BLOCK",
        "reasons": dec.reasons or ["all checks passed"],
        "qty": qty, "position_value": round(qty * args.entry, 2),
        "loss_at_stop_before_charges": round(qty * (args.entry - args.stop), 2),
        "round_trip_charges_at_stop": rt,
        "reward_risk": round((args.target - args.entry) / (args.entry - args.stop), 2) if args.target and args.entry > args.stop else None,
        "risk_budget": round(cfg.capital * rm.cfg["risk_per_trade_pct"] / 100, 2),
    }
    if out["reward_risk"]:
        out["breakeven_win_rate_pct"] = round(100 / (1 + out["reward_risk"]), 1)
    _print(out, args.json)
    return 0 if dec.ok else 2


def cmd_trade(args, cfg):
    broker = brk.make_broker(cfg, args.live)
    eng = Engine(cfg, broker)
    sym = args.symbol.upper()
    now = now_ist()
    price = args.price or eng.prices([sym]).get(sym)
    if not price:
        print("No price available; pass --price.")
        return 1
    if sym in eng.positions:
        print(f"Already holding {sym} via the bot.")
        return 1
    dec = eng.rm.check_entry(sym, price, args.stop, args.target, now, len(eng.positions), args.intraday,
                             cash=min(broker.cash(), cfg.capital), open_risk=eng.open_risk())
    qty = min(args.qty, dec.qty) if args.qty else dec.qty
    mode = "LIVE (REAL MONEY)" if broker.live else "PAPER"
    print(f"TICKET [{mode}] BUY {qty} {sym} @ ~{price:.2f} {'MIS (intraday)' if args.intraday else 'CNC (delivery)'}")
    print(f"  stop {args.stop:.2f}  target {args.target if args.target else '-'}  max loss ~Rs {qty * (price - args.stop):,.0f}")
    print(f"  risk check: {dec}")
    if not dec.ok:
        return 2
    if not args.yes:
        print("\nNot sent. Re-run with --yes after you have confirmed this exact ticket.")
        return 0
    ok = eng.open(sym, qty, price, args.stop, args.target, now, args.intraday, "manual")
    return 0 if ok else 1


def cmd_strategies(args, cfg):
    rows = [{"strategy": n, "interval": s.interval, "product": s.product, "tested": strategies.status(n)[0],
             "evidence": strategies.status(n)[1], "description": s.description}
            for n, s in strategies.STRATEGIES.items()]
    if args.json:
        _print(rows, True)
        return
    print(pd.DataFrame(rows)[["strategy", "interval", "tested", "evidence"]].to_string(index=False))
    print("\nNo strategy has a proven edge yet. Details: docs/14-historical-validation.md, docs/15-strategy-v2.md, "
          "docs/16-strategy-v3.md. " + DISCLAIMER)


def cmd_run(args, cfg):
    name = cfg.strategy["name"]
    st, why = strategies.status(name)
    if st == "failed":
        msg = f"Strategy '{name}' FAILED the historical test ({why})."
        if args.live:
            print(msg + " Refusing to trade it with real money. Pick another in config.toml "
                  "(`python -m growwbot strategies`).")
            return 1
        print("[warn] " + msg + " Paper trading it anyway.", file=sys.stderr)
    elif st != "validated":
        print(f"[note] Strategy '{name}' is {st.upper()} in the historical test: {why}.", file=sys.stderr)
    broker = brk.make_broker(cfg, args.live)
    if broker.live:
        print("*** LIVE TRADING: real orders will be sent to Groww. Ctrl+C stops the engine; "
              "`python -m growwbot kill --flatten --live` exits everything. ***")
    Engine(cfg, broker).run(once=args.once, holidays=cfg.risk.get("holidays", []))


def cmd_positions(args, cfg):
    broker = brk.make_broker(cfg, args.live)
    eng = Engine(cfg, broker, log=lambda *_: None)
    out = {"mode": eng.mode, "cash": round(broker.cash(), 2), "bot_positions": eng.positions,
           "today": eng.rm.day.__dict__, "kill_switch": risk.kill_switch_active()}
    if broker.live:
        out["groww_positions"] = broker.broker_positions()
        out["groww_open_orders"] = broker.open_orders()
    _print(out, True)


def cmd_flatten(args, cfg):
    eng = Engine(cfg, brk.make_broker(cfg, args.live))
    eng.flatten(now_ist(), "manual flatten")
    print(f"Flattened bot positions ({eng.mode}). Positions you opened yourself in the Groww app are untouched.")


def cmd_kill(args, cfg):
    risk.engage_kill_switch(args.reason or "manual")
    print("KILL SWITCH ON: the engine will open no new trades until `python -m growwbot unkill`.")
    if args.flatten:
        cmd_flatten(args, cfg)


def cmd_unkill(args, cfg):
    print("Kill switch released." if risk.release_kill_switch() else "Kill switch was not on.")


def cmd_report(args, cfg):
    mode = "live" if args.live else "paper"
    path = config.state_dir() / f"journal_{mode}.csv"
    if not path.exists():
        print(f"No {mode} trades journaled yet ({path}).")
        return
    df = pd.read_csv(path)
    c = CostModel.from_dict(cfg.costs)
    df["charges"] = [c.round_trip(r.entry, r.exit, int(r.qty), r["product"] == "MIS") for _, r in df.iterrows()]
    df["pnl_net"] = df["pnl_gross"] - df["charges"]
    wins = df[df.pnl_net > 0]
    losses = df[df.pnl_net <= 0]
    out = {
        "mode": mode, "trades": len(df), "win_rate_pct": round(100 * len(wins) / len(df), 1),
        "net_pnl": round(df.pnl_net.sum(), 2), "charges": round(df.charges.sum(), 2),
        "avg_win": round(wins.pnl_net.mean(), 2) if len(wins) else 0, "avg_loss": round(losses.pnl_net.mean(), 2) if len(losses) else 0,
        "profit_factor": round(wins.pnl_net.sum() / -losses.pnl_net.sum(), 2) if len(losses) and losses.pnl_net.sum() < 0 else None,
        "avg_r": round(df.r_multiple.mean(), 2),
        "by_exit_reason": df.groupby("reason").pnl_net.agg(["count", "sum"]).round(2).to_dict("index"),
        "by_symbol": df.groupby("symbol").pnl_net.sum().round(2).sort_values().to_dict(),
    }
    _print(out, args.json)


def cmd_costs(args, cfg):
    c = CostModel.from_dict(cfg.costs)
    buy = c.order_cost("BUY", args.buy, args.qty, args.intraday)
    sell = c.order_cost("SELL", args.sell or args.buy, args.qty, args.intraday)
    gross = args.qty * ((args.sell or args.buy) - args.buy)
    _print({"buy_charges": buy, "sell_charges": sell, "total_charges": round(buy + sell, 2), "gross_pnl": round(gross, 2),
            "net_pnl": round(gross - buy - sell, 2),
            "breakeven_move_pct": round(100 * (buy + sell) / (args.buy * args.qty), 3)}, args.json)


def cmd_paper_reset(args, cfg):
    brk.PaperBroker(cfg).reset(args.capital or cfg.capital)
    for name in ("positions_paper.json", "journal_paper.csv"):
        p = config.state_dir() / name
        if p.exists():
            p.rename(p.with_suffix(p.suffix + f".{datetime.now():%Y%m%d%H%M%S}.bak"))
    print("Paper account reset (old journal kept as a .bak file).")


# ----------------------------------------------------------------------------- research (read-only)

def _daily(symbols, args, days=400):
    frames = _load_universe(symbols, "1day", days, args.source, getattr(args, "csv_dir", None))
    return {k: data.completed_bars(v, "1day", now_ist()) for k, v in frames.items() if len(v)}


def _one_daily(symbol, args, days=400):
    return _daily([symbol], args, days).get(symbol)


def _prices(symbols, source="auto"):
    from .groww_client import Groww, has_credentials

    if has_credentials() and source in ("auto", "groww"):
        try:
            return Groww().ltp(symbols)
        except Exception as e:
            print(f"[warn] Groww LTP failed ({e}); using last daily close", file=sys.stderr)
    out = {}
    for s in symbols:
        try:
            out[s] = float(data.load(s, "1day", 10, source)["close"].iloc[-1])
        except Exception as e:
            print(f"[warn] {s}: {e}", file=sys.stderr)
    return out


def cmd_regime(args, cfg):
    syms = analytics.universe(args.universe, cfg)
    nifty = _one_daily("NIFTY", args)
    if nifty is None:
        print("No NIFTY data.")
        return 1
    vix = None
    try:
        vix = _one_daily("INDIAVIX", args, 30)
    except Exception:
        pass
    out = analytics.market_regime(nifty, _daily(syms, args), vix)
    _print(out, args.json)


def cmd_screen(args, cfg):
    syms = analytics.universe(args.universe, cfg)
    table = analytics.screen(_daily(syms, args), args.expr)
    if args.json:
        _print(table.reset_index().to_dict("records") if not table.empty else [], True)
    elif table.empty:
        print(f"No stocks in {len(syms)} match: {analytics.PRESETS.get(args.expr, args.expr)}")
    else:
        print(table.to_string())
        print(f"\n{len(table)} of {len(syms)} match. A screen is a shortlist, not a buy list: run `analyze` on each.")


def cmd_rank(args, cfg):
    syms = analytics.universe(args.universe, cfg)
    t = analytics.relative_strength(_daily(syms, args, 400), _one_daily("NIFTY", args, 400))
    t = t.head(args.top) if args.top else t
    _print(t.reset_index().to_dict("records"), True) if args.json else print(t.to_string())


def cmd_levels(args, cfg):
    df = _one_daily(args.symbol.upper(), args, 120)
    if df is None:
        print("No data.")
        return 1
    _print(analytics.pivot_levels(df), args.json)


def cmd_montecarlo(args, cfg):
    if args.trades_csv:
        t = pd.read_csv(args.trades_csv)
        r = t["r_multiple"].tolist()
    else:
        strat = strategies.get(args.strategy or cfg.strategy["name"])
        universe_ = _load_universe(analytics.universe(args.universe, cfg), strat.interval,
                                   59 if strat.intraday else int(cfg.backtest.get("days", 730)), args.source)
        res = bt.run(universe_, strat, risk_cfg=cfg.risk, initial_capital=cfg.capital, costs=CostModel.from_dict(cfg.costs))
        r = [t.r_multiple for t in res.trades]
    risk_pct = args.risk or float(cfg.risk.get("risk_per_trade_pct", 0.5))
    try:
        out = analytics.monte_carlo(r, risk_pct=risk_pct, n_trades=args.n, sims=args.sims)
    except ValueError as e:
        print(e)
        return 1
    _print(out, args.json)
    if not args.json:
        print("\nPlan for the p95 drawdown and losing streak, not the median: that is what you will live through.")


def cmd_optimize(args, cfg):
    strat = strategies.get(args.strategy or cfg.strategy["name"])
    days = args.days or (59 if strat.intraday else int(cfg.backtest.get("days", 730)))
    universe_ = _load_universe(analytics.universe(args.universe, cfg), strat.interval, days, args.source, args.csv_dir)
    grid = analytics.parse_grid(args.grid, strat.name)
    out = analytics.walk_forward(universe_, strat, grid, folds=args.folds,
                                 run_kwargs=dict(risk_cfg={**cfg.risk, "regime_filter": False}, initial_capital=cfg.capital,
                                                 costs=CostModel.from_dict(cfg.costs)))
    if args.json:
        _print(out, True)
        return
    print(f"Walk-forward for {strat.name}: {out['combinations_tested']} parameter sets, {len(out['folds'])} folds")
    print(pd.DataFrame(out["folds"])[["test_start", "best_params", "test_return_pct", "test_trades", "test_pf"]].to_string(index=False))
    for k in ("oos_return_pct_compounded", "default_params_oos_return_pct_compounded", "params_stable_across_folds", "verdict"):
        print(f"  {k}: {out[k]}")


def cmd_alerts(args, cfg):
    if args.action == "add":
        a = alerts.add(args.symbol, args.condition, args.value, args.note or "")
        print(f"Added alert {a['id']}: {a['symbol']} {a['condition']} {a['value']}")
    elif args.action == "rm":
        print("Removed." if alerts.remove(args.symbol) else "No alert with that id.")
    elif args.action == "list":
        rows = alerts.load()
        print(pd.DataFrame(rows).to_string(index=False) if rows else "No alerts.")
    elif args.action == "watch":
        def rsis(syms):
            out = {}
            for s in set(syms):
                df = _one_daily(s, args, 120)
                if df is not None:
                    out[s] = float(indicators.rsi(df["close"]).iloc[-1])
            return out
        alerts.watch(lambda syms: _prices(syms, args.source), rsis, interval_s=args.interval, once=args.once)


def cmd_portfolio(args, cfg):
    if args.csv:
        h = pd.read_csv(args.csv)
        h.columns = [c.lower() for c in h.columns]
        holdings = [{"symbol": r.symbol.upper(), "qty": float(r.qty), "avg_price": float(r.avg_price)} for r in h.itertuples()]
    else:
        from .groww_client import Groww, has_credentials

        if not has_credentials():
            print("No Groww credentials: pass --csv holdings.csv (columns symbol,qty,avg_price).")
            return 1
        raw = (Groww().call("get_holdings_for_user") or {}).get("holdings", [])
        holdings = [{"symbol": x["trading_symbol"], "qty": float(x["quantity"]), "avg_price": float(x["average_price"])}
                    for x in raw if float(x.get("quantity") or 0) > 0]
    t = analytics.portfolio_review(holdings, _daily([x["symbol"] for x in holdings], args))
    if args.json:
        _print(t.reset_index().to_dict("records"), True)
    else:
        print(t.to_string() if not t.empty else "No holdings with enough price history.")
        print("\nRead-only review. Suggested stops are ATR/EMA based levels to consider, not orders.")


def cmd_plan(args, cfg):
    """Pre-market plan in Markdown: regime, open positions, signals with levels, risk budget."""
    lines = [f"# Trading plan for {now_ist():%A %d %b %Y}", ""]
    syms = analytics.universe(args.universe, cfg)
    nifty = _one_daily("NIFTY", args)
    if nifty is not None:
        try:
            vix = _one_daily("INDIAVIX", args, 30)
        except Exception:
            vix = None
        reg = analytics.market_regime(nifty, _daily(syms, args), vix)
        lines += ["## Market regime", f"**{reg['posture']}** (score {reg['score']}/100)", ""]
        lines += [f"- {r}" for r in reg["reasons"]] + [""]
    else:
        reg = {"suggested_risk_multiplier": 1.0}
        lines += ["## Market regime", "NIFTY data unavailable.", ""]
    rm_ = risk.RiskManager(cfg.risk, capital=cfg.capital, persist=True, costs=CostModel.from_dict(cfg.costs))
    budget = cfg.capital * rm_.cfg["risk_per_trade_pct"] / 100 * reg["suggested_risk_multiplier"]
    lines += ["## Risk budget",
              f"- Capital Rs {cfg.capital:,.0f}; risk per trade Rs {budget:,.0f} after the regime multiplier",
              f"- Daily loss limit Rs {rm_.daily_loss_limit():,.0f}; max {rm_.cfg['max_trades_per_day']} trades, "
              f"{rm_.cfg['max_open_positions']} open positions",
              f"- Kill switch: {'ON' if risk.kill_switch_active() else 'off'}", ""]
    pos_path = config.state_dir() / f"positions_{'live' if cfg.mode == 'live' else 'paper'}.json"
    pos = json.loads(pos_path.read_text())["positions"] if pos_path.exists() else {}
    lines += ["## Open bot positions"] + ([f"- {s}: {p['qty']} @ {p['entry']:.2f}, stop {p['stop']:.2f}" for s, p in pos.items()] or ["- none"]) + [""]
    strat = strategies.get(cfg.strategy["name"])
    lines += [f"## Signals ({strat.name})"]
    found = 0
    for sym in cfg.watchlist:
        try:
            csv = f"{args.csv_dir}/{sym}_{strat.interval}.csv" if args.csv_dir else None
            raw = data.load(sym, strat.interval, 400 if not strat.intraday else 20, args.source, csv=csv)
            df = data.completed_bars(raw, strat.interval, now_ist())
            sig = strat.signals(df, **cfg.strategy.get("params", {})).iloc[-1]
        except Exception:
            continue
        if bool(sig["entry"]):
            found += 1
            lv = analytics.pivot_levels(_one_daily(sym, args, 120))
            tgt = "" if math.isnan(sig["target"]) else f", target {sig['target']:.2f}"
            lines.append(f"- **{sym}** close {df['close'].iloc[-1]:.2f}, stop {sig['stop']:.2f}{tgt}; "
                         f"pivot {lv['classic']['P']}, R1 {lv['classic']['R1']}, S1 {lv['classic']['S1']}")
    if not found:
        lines.append("- No entry signals. Sitting out is a position.")
    pending = [a for a in alerts.load() if not a["triggered"]]
    lines += ["", "## Alerts"] + ([f"- {a['symbol']} {a['condition']} {a['value']} {a['note']}" for a in pending] or ["- none"])
    lines += ["", "_Not financial advice. Check news, results dates and F&O ban list before acting._"]
    text = "\n".join(lines)
    out = config.state_dir() / "plans"
    out.mkdir(exist_ok=True)
    path = out / f"{now_ist():%Y-%m-%d}.md"
    path.write_text(text)
    print(text + f"\n\n(saved to {path})")


def cmd_install_skills(args, cfg):
    """Copy skills/ into ./.claude/skills (this repo) or ~/.claude/skills (--global). Works on Windows too."""
    import shutil
    from pathlib import Path

    src = config.home() / "skills"
    dest = (Path.home() if args.scope == "global" else config.home()) / ".claude" / "skills"
    dest.mkdir(parents=True, exist_ok=True)
    names = sorted(p.name for p in src.iterdir() if (p / "SKILL.md").exists())
    for name in names:
        shutil.copytree(src / name, dest / name, dirs_exist_ok=True)
    print(f"Installed {len(names)} skills into {dest}")
    if args.scope == "global":
        print(f"Set GROWWBOT_HOME={config.home()} so the skills find the engine from any folder.")
    print("Re-run after `git pull` to pick up skill updates.")



def cmd_odds(args, cfg):
    """Replay one planned trade against the stock's own recent bars."""
    sym = args.symbol.upper()
    strat = strategies.get(args.strategy) if args.strategy else None
    interval = args.interval or (strat.interval if strat else "1day")
    intraday = data.is_intraday(interval)
    days = args.days or (59 if intraday else 730)
    csv = f"{args.csv_dir}/{sym}_{interval}.csv" if args.csv_dir else None
    df = data.completed_bars(data.load(sym, interval, days, args.source, csv=csv), interval, now_ist())
    if len(df) < 60:
        print(f"Not enough {interval} history for {sym} ({len(df)} bars).")
        return 1

    entry, stop, target = args.entry, args.stop, args.target
    if strat and (entry is None or stop is None):
        sig = strat.signals(df, **(cfg.strategy.get("params", {}) if strat.name == cfg.strategy["name"] else {})).iloc[-1]
        if not bool(sig["entry"]) and entry is None:
            print(f"{strat.name} has no entry signal on {sym}'s last completed bar "
                  f"({df.index[-1]}). Pass --entry/--stop to price a trade anyway.")
            return 1
        entry = entry if entry is not None else float(df["close"].iloc[-1])
        stop = stop if stop is not None else float(sig["stop"])
        if target is None and not math.isnan(float(sig["target"])):
            target = float(sig["target"])
    if entry is None or stop is None:
        print("Need --entry and --stop (or --strategy to take them from the latest signal).")
        return 1
    if target is None:
        target = entry + args.rr * (entry - stop)

    now = args.now or now_ist()
    bars = args.bars or odds_mod.bars_remaining(
        interval, now, str(cfg.risk.get("squareoff_time", "15:10")), args.hold)
    start_slot = 0
    if intraday:
        today = df[df.index.date == df.index[-1].date()]
        start_slot = len(today)
    pools = odds_mod.build_pools(df, intraday, window=args.window)
    out = odds_mod.replay(pools, entry, stop, target, bars, sims=args.sims, seed=args.seed,
                          start_slot=start_slot)
    out["symbol"] = sym
    out["interval"] = interval
    out["history_bars"] = len(df)
    if strat:
        out["precedent"] = odds_mod.precedent(
            sym, df, strat, cfg.strategy.get("params", {}) if strat.name == cfg.strategy["name"] else {},
            cfg.risk, CostModel.from_dict(cfg.costs), capital=cfg.capital)
        odds_mod.reconcile(out, out["precedent"])

    if args.json:
        _print(out, True)
        return
    horizon = f"{bars} bars to {cfg.risk.get('squareoff_time', '15:10')}" if intraday else f"{bars} bars held"
    print(f"{sym} {interval}: buy {out['entry']}, stop {out['stop']}, target {out['target']} "
          f"({out['reward_risk']}R, Rs {out['risk_per_share']}/share at risk)")
    print(f"{out['sims']:,} replays from {out['history_bars']} of its own bars, {horizon}, seed {out['seed']}")
    for k, label in (("target_first_pct", "target first"), ("stop_first_pct", "stop first"),
                     ("neither_pct", "neither"), ("green_pct", "green at the end")):
        print(f"  {label:<18} {out[k]:>5} %")
    pe = out["exit_price"]
    print(f"  exit or final px  median {pe['median']}, 90% between {pe['p5']} and {pe['p95']}")
    print(f"  average R          {out['avg_r']:+}")
    if out.get("precedent"):
        p = out["precedent"]
        if p["trades"]:
            print(f"History: {strat.name} fired {p['trades']} times on {sym} ({p['first']} to {p['last']}): "
                  f"{p['win_rate_pct']}% winners, average {p['avg_r']:+}R, best {p['best_r']}R, worst {p['worst_r']}R.")
        else:
            print(f"History: {p['note']}")
    print(f"\n{out['verdict']}")
    for n in out.get("notes", []):
        print(f"  {n}")
    print("\nBuilt from recent bars, not a prediction: results, news and circuit limits do things "
          "the sample never did. " + DISCLAIMER)


# ----------------------------------------------------------------------------- parser

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="growwbot", description="Indicator-based trading for NSE stocks via Groww. Paper by default.")
    p.add_argument("--config", help="path to config.toml")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_):
        sp = sub.add_parser(name, help=help_)
        sp.set_defaults(fn=fn)
        sp.add_argument("--json", action="store_true")
        return sp

    add("doctor", cmd_doctor, "check setup, credentials and live-trading gates")
    sp = add("analyze", cmd_analyze, "indicator snapshot for one symbol")
    sp.add_argument("symbol"); sp.add_argument("--interval", default="1day"); sp.add_argument("--source", default="auto")
    sp = add("scan", cmd_scan, "find entry signals across the watchlist")
    sp.add_argument("--strategy"); sp.add_argument("--all", action="store_true"); sp.add_argument("--symbols", nargs="*")
    sp.add_argument("--source", default="auto")
    sp = add("backtest", cmd_backtest, "backtest a strategy with costs and risk rules")
    sp.add_argument("--strategy"); sp.add_argument("--all", action="store_true"); sp.add_argument("--symbols", nargs="*")
    sp.add_argument("--days", type=int); sp.add_argument("--capital", type=float)
    sp.add_argument("--split", type=float, help="in-sample fraction, e.g. 0.7, for an out-of-sample check")
    sp.add_argument("--source", default="auto"); sp.add_argument("--csv-dir"); sp.add_argument("--no-regime", action="store_true")
    sp = add("size", cmd_size, "position size + risk verdict for a planned trade")
    sp.add_argument("symbol"); sp.add_argument("--entry", type=float, required=True); sp.add_argument("--stop", type=float, required=True)
    sp.add_argument("--target", type=float); sp.add_argument("--intraday", action="store_true"); sp.add_argument("--live", action="store_true")
    sp.add_argument("--now", type=datetime.fromisoformat)
    sp = add("trade", cmd_trade, "place one bot-managed BUY (prints a ticket; needs --yes to send)")
    sp.add_argument("symbol"); sp.add_argument("--stop", type=float, required=True); sp.add_argument("--target", type=float)
    sp.add_argument("--qty", type=int); sp.add_argument("--price", type=float); sp.add_argument("--intraday", action="store_true")
    sp.add_argument("--live", action="store_true"); sp.add_argument("--yes", action="store_true")
    add("strategies", cmd_strategies, "list strategies and their historical-test status")
    sp = add("run", cmd_run, "run the automated engine during market hours")
    sp.add_argument("--live", action="store_true"); sp.add_argument("--once", action="store_true")
    sp = add("positions", cmd_positions, "show bot positions, cash, today's risk state")
    sp.add_argument("--live", action="store_true")
    sp = add("flatten", cmd_flatten, "exit every bot-managed position now")
    sp.add_argument("--live", action="store_true")
    sp = add("kill", cmd_kill, "engage the kill switch (no new entries)")
    sp.add_argument("--flatten", action="store_true"); sp.add_argument("--reason"); sp.add_argument("--live", action="store_true")
    add("unkill", cmd_unkill, "release the kill switch")
    sp = add("report", cmd_report, "performance report from the trade journal")
    sp.add_argument("--live", action="store_true")
    sp = add("costs", cmd_costs, "Groww charges for a trade")
    sp.add_argument("--buy", type=float, required=True); sp.add_argument("--sell", type=float)
    sp.add_argument("--qty", type=int, required=True); sp.add_argument("--intraday", action="store_true")
    sp = add("paper-reset", cmd_paper_reset, "reset the paper account")
    sp.add_argument("--capital", type=float)

    sp = add("install-skills", cmd_install_skills, "copy the Claude skills into .claude/skills (project) or ~/.claude/skills")
    sp.add_argument("--scope", choices=["project", "global"], default="project")

    # research (read-only)
    def research(name, fn, help_):
        sp = add(name, fn, help_)
        sp.add_argument("--source", default="auto")
        sp.add_argument("--csv-dir")
        return sp

    sp = research("regime", cmd_regime, "market regime: NIFTY trend, breadth, India VIX -> exposure posture")
    sp.add_argument("--universe", nargs="*", default=["nifty50"])
    sp = research("screen", cmd_screen, f"technical screen; presets: {', '.join(analytics.PRESETS)} or a query")
    sp.add_argument("expr"); sp.add_argument("--universe", nargs="*", default=["nifty50"])
    sp = research("rank", cmd_rank, "relative-strength (momentum) ranking vs NIFTY")
    sp.add_argument("--universe", nargs="*", default=["nifty50"]); sp.add_argument("--top", type=int)
    sp = research("levels", cmd_levels, "pivot points, CPR, Camarilla and swing levels for the next session")
    sp.add_argument("symbol")
    sp = research("montecarlo", cmd_montecarlo, "drawdown / losing-streak odds from a trade list")
    sp.add_argument("--trades-csv"); sp.add_argument("--strategy"); sp.add_argument("--universe", nargs="*", default=["watchlist"])
    sp.add_argument("--risk", type=float); sp.add_argument("--n", type=int); sp.add_argument("--sims", type=int, default=5000)
    sp = research("odds", cmd_odds, "replay one planned trade thousands of times before you take it")
    sp.add_argument("symbol"); sp.add_argument("--entry", type=float); sp.add_argument("--stop", type=float)
    sp.add_argument("--target", type=float); sp.add_argument("--rr", type=float, default=2.0)
    sp.add_argument("--strategy"); sp.add_argument("--interval"); sp.add_argument("--days", type=int)
    sp.add_argument("--bars", type=int, help="bars to simulate (default: to square-off intraday, else --hold)")
    sp.add_argument("--hold", type=int, default=20, help="holding horizon in bars for daily strategies")
    sp.add_argument("--sims", type=int, default=10000); sp.add_argument("--seed", type=int, default=19)
    sp.add_argument("--window", type=int, default=2, help="time-of-day slots either side to sample from")
    sp.add_argument("--now", type=datetime.fromisoformat)
    sp = research("optimize", cmd_optimize, "walk-forward parameter search, judged out of sample")
    sp.add_argument("--strategy"); sp.add_argument("--grid"); sp.add_argument("--folds", type=int, default=4)
    sp.add_argument("--universe", nargs="*", default=["watchlist"]); sp.add_argument("--days", type=int)
    sp = research("alerts", cmd_alerts, "price/RSI alerts: add | list | rm | watch")
    sp.add_argument("action", choices=["add", "list", "rm", "watch"])
    sp.add_argument("symbol", nargs="?", help="symbol (add) or alert id (rm)")
    sp.add_argument("condition", nargs="?", choices=list(alerts.CONDITIONS)); sp.add_argument("value", nargs="?", type=float)
    sp.add_argument("--note"); sp.add_argument("--interval", type=float, default=60); sp.add_argument("--once", action="store_true")
    sp = research("portfolio", cmd_portfolio, "review Groww holdings (read-only) or a holdings CSV")
    sp.add_argument("--csv")
    sp = research("plan", cmd_plan, "pre-market plan in Markdown (saved to state/plans/)")
    sp.add_argument("--universe", nargs="*", default=["watchlist"])
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    cfg = config.load(args.config)
    try:
        return int(args.fn(args, cfg) or 0)
    except brk.LiveTradingNotAllowed as e:
        print(e.code if isinstance(e.code, str) else e)
        return 3
