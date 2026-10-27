---
name: relative-strength
description: >-
  Rank stocks by relative strength (momentum) against NIFTY 50 with an
  IBD-style weighted 3/6/9/12-month return and a 1-99 RS rating, plus 1-month
  and 3-month excess return vs NIFTY. Use when the user asks "strongest
  stocks", "momentum ranking", "leaders and laggards", "which sector/stock is
  outperforming", "relative strength", or wants to pick a watchlist of leaders.
---

# relative-strength

Run from the repo root.

```bash
python -m growwbot rank                          # NIFTY 50
python -m growwbot rank --top 10
python -m growwbot rank --universe banknifty
python -m growwbot rank --universe watchlist --json
```

Score = 40 % of the last 3 months' return + 20 % each of the three quarters
before it. `rs_rating` is the percentile inside the universe you ranked (99 =
strongest), so it's relative to that list only, not to the whole market.

## Use it well

- Momentum leaders (RS 80+) that are also above their 50 EMA are the usual
  candidates for trend strategies (`ema_trend`, `supertrend_adx`,
  `donchian_breakout`).
- RS rating falling while price is still high is an early warning.
- Laggards (RS under 20) are rarely good long candidates even when "cheap".
- Momentum can reverse sharply after news or results. RS is evidence of what
  has worked, not a forecast.

Suggest a watchlist built from the top 10-15 names only if the user asks,
and only by editing `config.toml` with their OK.
