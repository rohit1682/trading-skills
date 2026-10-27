---
name: risk-of-ruin
description: >-
  Monte Carlo stress test of a strategy's trade list: reshuffles past trade
  outcomes (R-multiples) thousands of times to show the range of returns,
  realistic worst drawdowns (p95/p99), longest losing streaks and the chance of
  losing money or a 30 % drawdown at the chosen risk per trade. Use when the
  user asks "how bad can it get", "drawdown", "risk of ruin", "losing streak",
  "how much should I risk per trade", "is 2 % risk too much".
---

# risk-of-ruin

Run from the repo root.

```bash
python -m growwbot montecarlo                                   # backtests the configured strategy, then simulates
python -m growwbot montecarlo --strategy rsi2_reversion --risk 1.0
python -m growwbot montecarlo --trades-csv state/backtests/<file>-trades.csv --n 200
python -m growwbot montecarlo --trades-csv state/journal_paper.csv     # needs an r_multiple column
```

`--risk` is % of equity lost on a full stop (1R). `--n` is trades per
simulated path (default: as many as in the sample, e.g. 200 ≈ a year of
active trading).

## How to talk about it

- Lead with the p95 worst drawdown and p95 losing streak: "1 in 20 years
  could look like this". People abandon systems in drawdowns they didn't
  expect; this sets the expectation.
- Compare risk levels by running 0.5, 1 and 2 %. Drawdowns grow faster than
  returns as risk rises; keep the user's own pain threshold in mind.
- If `prob_losing_money_pct` is high, the strategy has no edge on that sample.
  No risk setting fixes a negative average R.
- The simulation assumes future trades look like past trades. Regime changes
  break that assumption, so treat the output as optimistic.
