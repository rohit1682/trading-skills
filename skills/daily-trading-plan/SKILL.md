---
name: daily-trading-plan
description: >-
  Build the pre-market trading plan for the day as a Markdown note: market
  regime and risk multiplier, risk budget and limits, open bot positions with
  stops, today's strategy signals with pivot levels, and pending alerts.
  Saved to state/plans/. Use when the user says "plan my day", "morning
  routine", "pre-market", "what's the plan today", "trading checklist".
---

# daily-trading-plan

Run from the repo root, ideally between 08:45 and 09:10 IST (or the evening before).

```bash
python -m growwbot plan
python -m growwbot plan --universe nifty50      # regime breadth over NIFTY 50 instead of the watchlist
```

Then add what the tool can't see, by asking the user or checking the news:

1. **Events**: results, board meetings, dividends/splits (ex-dates move
   prices), RBI policy, budget day, US CPI/Fed nights, F&O expiry days.
2. **Surveillance**: stocks in the F&O ban list or under ASM/GSM shouldn't be
   traded by the bot; offer to add them to `blocked_symbols` (user confirms).
3. **Global cues**: GIFT Nifty and overnight US/Asia moves, as context only.
4. **Personal state**: if the user is tired, angry about yesterday, or chasing
   losses, the best plan is a smaller size or no trading.

Finish with a short checklist: engine started in the right mode? kill switch
off on purpose? holidays in config? Then hand over to `auto-trader` or
`trade-executor`.
