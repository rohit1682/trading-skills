# 9. Paper to live: the checklist

Go through every box. If one fails, stay on paper.

## Before paper trading

- [ ] `python -m pytest` passes and `python -m growwbot doctor` is clean
- [ ] Strategy chosen from a backtest with 30+ trades and an acceptable out-of-sample result
- [ ] `montecarlo` p95 drawdown is something you can live with
- [ ] Watchlist of liquid stocks (no penny, F&O-ban or ASM/GSM names)
- [ ] NSE holidays in `[risk] holidays`

## Paper trading (at least 2-4 weeks)

- [ ] Engine runs every trading day (see [automation](10-automation.md))
- [ ] `report` weekly: 20-30+ trades, results in line with the backtest
- [ ] You checked several trades by hand against the chart: entries, stops, exits make sense
- [ ] You tried the kill switch and `flatten` in paper mode

## Account and setup

- [ ] Groww Trade API active; TOTP login works in `doctor`
- [ ] Static IP registered with Groww if required (SEBI framework)
- [ ] The PC/VM running the bot has stable power and internet, won't sleep, correct IST clock
- [ ] You know how to exit positions and cancel orders in the Groww app

## Going live

- [ ] Small `capital` first (e.g. Rs 10,000-25,000), `risk_per_trade_pct` ≤ 0.5
- [ ] You set `mode = "live"` in `config.toml` **yourself**
- [ ] You set `GROWW_ENABLE_LIVE=YES_I_ACCEPT_REAL_MONEY_RISK` in `.env` **yourself**
- [ ] `doctor` shows "live trading: ENABLED when you pass --live"
- [ ] Start with `python -m growwbot run --live` and watch the first session
- [ ] After the first fill, confirm the SL-M stop in Groww's Orders tab

## First month live

- [ ] Daily: Groww positions/orders match `positions --live`; read `state/orders.log` for errors
- [ ] Weekly: `report --live` vs paper and backtest
- [ ] Monthly: reconcile with Groww's contract notes and P&L statement
- [ ] Increase capital only after a full month that matches expectations, and in small steps

## Going back to paper

Any time: set `mode = "paper"` or clear `GROWW_ENABLE_LIVE`, and run without
`--live`. Open live positions keep their Groww stops; manage or exit them in the app.
