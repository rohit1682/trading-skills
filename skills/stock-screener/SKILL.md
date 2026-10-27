---
name: stock-screener
description: >-
  Screen NIFTY 50, Bank NIFTY, the watchlist or any symbol list with technical
  filters: trend leaders, oversold in an uptrend, breakout watch (Bollinger
  squeeze near 20-day high), volume surge, Supertrend up, near 52-week high,
  below 200 EMA, or a custom expression like "rsi14 < 30 and close > ema200".
  Use when the user asks "find stocks", "screen for", "which stocks are
  oversold", "stocks near 52 week high", "momentum stocks", "build a watchlist".
---

# stock-screener

Run from the repo root.

```bash
python -m growwbot screen trend_leaders                 # NIFTY 50 by default
python -m growwbot screen oversold_uptrend --universe banknifty
python -m growwbot screen "rsi14 < 30 and close > ema200" --universe watchlist
python -m growwbot screen breakout_watch --universe RELIANCE INFY TCS SBIN
```

| preset | filter |
| --- | --- |
| `trend_leaders` | close > EMA50 > EMA200, RSI 50-70, ADX ≥ 20, within 10 % of the 52-week high |
| `oversold_uptrend` | above the 200 SMA with RSI(14) < 35 or RSI(2) < 10 |
| `breakout_watch` | within 3 % of the 20-day high, Bollinger width in its lowest 25 % of 6 months, above EMA50 |
| `volume_surge` | relative volume ≥ 2 on an up day |
| `supertrend_up` | Supertrend up, above EMA200, ADX ≥ 20 |
| `near_52w_high` | within 5 % of the 52-week high, above EMA50 |
| `below_200ema` | under the 200 EMA (what to avoid, or exit candidates) |

Custom expressions can use: `close, ema9, ema21, ema50, ema200, sma200,
rsi14, rsi2, macd_hist, adx, st_dir, atr14, atr_pct, rvol, change_pct,
from_high_pct, from_20d_high_pct, bb_width_rank`.

Universes live in `universes/*.txt` (one symbol per line). NIFTY 50
membership changes each March and September; remind the user to keep the
file current.

## Present

The table, then the 3-5 most interesting names with one line each on why.
Point out that a screen is a shortlist: next steps are `technical-analysis`
on each and `strategy-backtester` before trading the idea. To keep good names,
offer to add them to `watchlist` in config.toml (the user confirms first).
