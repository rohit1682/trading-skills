---
name: technical-analysis
description: >-
  Indicator-based read of one NSE stock: EMA 9/21/50/200 stack, RSI(14) and
  RSI(2), MACD, ADX, Supertrend, ATR, Bollinger Bands, VWAP (intraday),
  relative volume, distance from the 52-week high, and which growwbot
  strategies fire on it now. Use when the user asks "analyse RELIANCE", "is
  INFY bullish", "technical view on", "what do the indicators say", "should I
  buy X" (as analysis, not advice).
---

# technical-analysis

Run from the repo root.

```bash
python -m growwbot analyze RELIANCE                       # daily
python -m growwbot analyze RELIANCE --interval 15minute   # intraday view (adds VWAP)
python -m growwbot analyze RELIANCE --json
```

Read [references/indicators.md](references/indicators.md) for what each
number means and the thresholds used.

## Write-up format

- **Trend**: price vs EMA50/EMA200, EMA stack order, Supertrend direction,
  ADX (under 20 = no trend, 20-40 trending, above 40 strong/extended).
- **Momentum**: RSI(14) zone, MACD vs signal and histogram slope.
- **Volatility & risk**: ATR and ATR % of price; a sensible stop is 1.5-3 ATR
  away; say what that means in rupees per share.
- **Volume**: RVOL above 1.5 confirms a breakout; under 1 is a weak move.
- **Signals**: list `entry_signals` (strategy, stop, target) or say none.
- **Verdict**: one of "constructive", "neutral", "weak", with the two
  indicators that drive it. Not "buy" or "sell" orders, and no price
  predictions.

Indicators describe the past; they lag and they disagree. When they conflict,
say so plainly instead of picking the bullish one.
