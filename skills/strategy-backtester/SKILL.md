---
name: strategy-backtester
description: >-
  Backtest growwbot strategies on NSE stocks with Groww's real charges,
  slippage, next-bar fills, gap-through stops and the same risk rules the live
  bot uses; compare all strategies; check out-of-sample. Use when the user
  asks "backtest", "which strategy works best", "is this profitable", "test
  supertrend on bank stocks", "walk forward", or before turning on the
  auto-trader or changing strategy parameters.
---

# strategy-backtester

Run from the repo root.

```bash
python -m growwbot backtest                                   # configured strategy + watchlist, 2 years daily
python -m growwbot backtest --all --split 0.7                 # compare every strategy, 30 % held out
python -m growwbot backtest --strategy orb --days 59          # intraday: 5-minute candles
python -m growwbot backtest --strategy ema_trend --symbols HDFCBANK ICICIBANK SBIN AXISBANK KOTAKBANK
python -m growwbot backtest --csv-dir data/ --source csv      # your own CSVs: SYMBOL_1day.csv (ts,open,high,low,close,volume)
```

Data: Groww historical candles when credentials exist (the loader stitches
Groww's 30/90/180-day request windows), otherwise Yahoo Finance, which keeps
only ~60 days of 5-minute candles. Trade lists and equity curves are written
to `state/backtests/`.

Strategy parameters can be overridden in `config.toml`:
`[strategy] params = { adx_min = 25, rr = 2.5 }`.

## Judge the result honestly

Report these, then a verdict:

| Check | Fragile if |
| --- | --- |
| trades | under ~30: too few to tell skill from luck |
| profit_factor (after costs) | under ~1.3 |
| max_drawdown_pct | deeper than the user said they can stomach |
| out_of_sample_return_pct vs in-sample | OOS much worse, or negative: overfit |
| buy_hold_return_pct | strategy far behind simply holding: say so |
| total_costs | eating most of the gross profit (common for intraday) |

Rules for the conversation:
- Never tune parameters until the backtest looks good and then present it as
  expected performance. If you tried several settings, say how many, and
  trust only the out-of-sample number.
- Say clearly that live results are usually worse than backtests (partial
  fills, slippage spikes, outages, discipline), and that past performance does
  not predict future returns.
- Small risk per trade (0.5 %) means small absolute returns; that is the
  price of surviving losing streaks. Don't suggest raising risk to make the
  numbers bigger.
- A strategy that passes goes to paper trading (`auto-trader`), not straight to live.

## What the full history test already found (Nov 2026)

Before running anything, tell the user what docs 14 and 15 found on 2010-2026
NSE data, so they don't mistake a lucky short backtest for an edge:
- No strategy, v1 or v2, has a statistically proven edge out of sample.
  `python -m growwbot strategies` shows each one's status and evidence.
- `donchian_breakout_v2` looked promising on 5 test sets, then lost on a fresh
  holdout (doc 16); `supertrend_adx`, `ema_trend_v2` and `macd_momentum_v2` are mixed.
- `rsi2_reversion` (both versions), `macd_momentum`, `vwap_pullback` and `orb`
  (both versions) lost money; don't recommend them at small capital.
- Buying and holding the same stocks beat every strategy by a wide margin.
Details: `docs/14-historical-validation.md`, `docs/15-strategy-v2.md`, `docs/16-holdout-and-status.md`.
To re-test properly: `python scripts/validate_strategies.py` and
`python scripts/compare_versions.py` (see those docs).
