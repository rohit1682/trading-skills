---
name: market-scanner
description: >-
  Scan the NSE watchlist for fresh entry signals from the growwbot strategies
  (EMA trend, Supertrend+ADX, RSI(2) pullback, MACD momentum, Donchian
  breakout, VWAP pullback, opening-range breakout) on the latest completed
  candle, with stop, target and risk %. Use when the user asks "what should I
  buy today", "scan my watchlist", "any setups", "find trades", "screen
  stocks", or before running the auto-trader by hand.
---

# market-scanner

Run from the repo root.

```bash
python -m growwbot scan                         # configured strategy, configured watchlist
python -m growwbot scan --all                   # every strategy
python -m growwbot scan --strategy donchian_breakout_v2 --symbols RELIANCE INFY TCS
python -m growwbot strategies                    # which strategies passed/failed the historical test
python -m growwbot scan --json                  # machine-readable
```

Data comes from Groww's historical candles when credentials exist, otherwise
Yahoo Finance (`.NS`). Only completed candles are used: a daily signal is from
yesterday's close and is acted on at today's open; an intraday signal is from
the last closed 5-minute bar.

## How to present the result

1. A table: symbol, strategy, tested status, close, stop, target, risk % (distance to stop).
   Flag signals from strategies whose status is `failed`: they lost money in
   the 2010-2026 test and are shown for reference only.
2. For the top 1-3 rows, run `python -m growwbot analyze SYMBOL` and give a
   two-line read: trend (EMA stack, Supertrend), momentum (RSI, MACD),
   volatility (ATR %), volume (RVOL).
3. Flag anything that weakens a setup: results or a board meeting this week,
   price within 3 % of a 52-week high into resistance, ATR % above ~4 (stop
   would be wide), RVOL under 1.
4. Next step: `risk-manager` to size it, then `trade-executor`.

"No signals today" is a correct and common answer. Never stretch a near-miss
into a trade. Never call a setup a sure thing: these rules win some and lose
some; the edge, if any, only shows across many trades.
