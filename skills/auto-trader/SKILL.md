---
name: auto-trader
description: >-
  Run the growwbot engine that trades automatically during NSE market hours:
  scans the watchlist on every new candle, sizes and checks each signal,
  enters, places broker-side stops, manages targets, exit signals, time
  stops, intraday square-off and the daily loss breaker. Paper by default;
  live only with three explicit opt-ins. Use when the user says "start the
  bot", "trade automatically", "run paper trading", "go live", "schedule the
  bot", "stop the bot".
---

# auto-trader

Run from the repo root.

```bash
python -m growwbot run              # PAPER: simulated fills, real prices
python -m growwbot run --once       # one pass, for testing
python -m growwbot run --live       # LIVE, only if all three gates are on
python -m growwbot positions [--live]
python -m growwbot kill --flatten [--live]
```

The engine runs 09:15-15:30 IST on weekdays and stops after the close. Add
exchange holidays to `[risk] holidays = ["2026-11-10", ...]` (check NSE's
holiday list each year). To run it every trading day, schedule it for 09:05
with Windows Task Scheduler or cron: step-by-step in `docs/10-automation.md`.
The computer must stay on and online.

## What it does on each step

1. Live: reconciles with Groww; a position that disappeared was closed by its
   broker-side stop and is journaled.
2. Exits: stop, target, intraday square-off at 15:10, strategy exit signal,
   time stop. A broker-side SL-M protects live positions even if the bot crashes.
3. Daily loss limit: engages the kill switch and flattens bot positions.
4. Entries: on each newly completed candle (daily strategies decide once a
   day at 09:20 from yesterday's close), checks risk and enters.

Only positions the bot opened are touched. Positions from the Groww app are ignored.

## The path to live (tell the user this, every time they ask to go live)

1. Backtest passes (`strategy-backtester`), including out-of-sample.
2. Paper trade at least 2-4 weeks (`run`, then `trade-journal`) and compare
   with the backtest. If paper is clearly worse, stop and find out why.
3. Go live with a small `capital` (for example Rs 10,000-25,000) and keep
   `risk_per_trade_pct` at 0.5 or below.
4. The user, not Claude, sets `mode = "live"` in config.toml and
   `GROWW_ENABLE_LIVE=YES_I_ACCEPT_REAL_MONEY_RISK` in .env, then starts
   `run --live` themselves or tells you explicitly to start it.
5. Watch the first days: Groww app Orders and Positions, `state/orders.log`.

Never start `run --live` on your own initiative, never as a "test", and
never unlock the gates. Profit is not guaranteed; SEBI found 7 in 10
individual intraday traders lost money in FY2022-23. Say so if the user
expects guaranteed income.
