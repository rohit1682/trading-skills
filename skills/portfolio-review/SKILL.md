---
name: portfolio-review
description: >-
  Review the user's Groww holdings (read-only) or a holdings CSV: P&L %,
  weight, trend vs 50/200 EMA, RSI, distance from 52-week high, an ATR/EMA
  based suggested stop, and flags for concentration, downtrends and deep
  losses without an uptrend. Use when the user asks "review my portfolio",
  "my holdings", "what should I do with my stocks", "which stocks are weak",
  "set stops on my holdings".
---

# portfolio-review

Run from the repo root.

```bash
python -m growwbot portfolio                    # reads Groww holdings (needs .env credentials; read-only call)
python -m growwbot portfolio --csv holdings.csv # columns: symbol,qty,avg_price
python -m growwbot portfolio --json
```

This never places or changes orders, including for flagged stocks.

## Write-up

1. Totals: value, number of stocks, the largest weights.
2. Concentration: any stock over 25 %, and sector clustering you can see
   (several banks or IT names are one bet).
3. Health table: trend, P&L %, distance from 52-week high, flags.
4. Stops: present `suggested_stop` as a level to consider (about 2.5 ATR
   below, or just under the 50 EMA in an uptrend) and the % risk it implies.
   If the user wants protection, explain they can place a GTT stop in the
   Groww app; the bot only manages positions it opened itself.
5. Long-term investments and trading positions follow different rules. Ask
   which holdings are long-term before suggesting technical exits for them.

Not investment advice. Don't tell the user to sell; describe what the
indicators show and the risk.
