# 16. Fresh holdout, a v3 attempt, and strategy status (November 2026)

After [doc 15](15-strategy-v2.md), the ask was to make the strategies better
again. Every extra round of "try a change, look at the result" on the same
data raises the odds of fooling ourselves, so this round started by locking
away **30 more random stocks that no test had touched** (holdout B, drawn
with seed 11 from the same 110-stock pool, disjoint from doc 15's draw A):

ACC, AMBUJACEM, ASHOKLEY, BAJAJ-AUTO, BANKBARODA, BERGEPAINT, COALINDIA,
DIVISLAB, DRREDDY, EXIDEIND, GODREJCP, GRASIM, HAVELLS, HCLTECH, HEROMOTOCO,
HINDZINC, INDUSINDBK, IOC, NMDC, NTPC, RCOM, SUZLON, TATAPOWER, TATASTEEL,
TMPV, UNIONBANK, UPL, VOLTAS, WIPRO, ZEEL.

(RCOM, SUZLON and ZEEL collapsed during the period, so survivorship bias is
lower here than in the earlier baskets.)

## Verdict

- **The v3 idea didn't help, so it isn't shipped.** v3 added a
  momentum-quality filter (6-month return > 0, within 15 % of the 52-week
  high) to the three v2 trend strategies. On the data already used in docs
  14-15 it was no better than v2, and usually slightly worse. It was dropped
  before touching the holdout.
- **`donchian_breakout_v2`'s promise did not replicate.** It was positive on
  all five earlier test sets, but on the fresh holdout it lost: -0.05 R a
  trade in 2010-2020 and **-0.31 R (t -1.9) in 2021-2026** at ₹50k.
- **No strategy is positive on every test.** Across all out-of-sample sets
  at ₹50k (table below), the best record is 4 of 7 (`supertrend_adx`). Its
  holdout 2021-2026 result (+0.40 R, t 2.1) is the only one of 55 results with t above +2.
  With that many tries, one t above 2 is roughly what luck alone
  produces, and the same strategy lost on the NIFTY 50 and on draw A for
  the same years.
- **Some losers are confirmed beyond doubt:** `macd_momentum` lost on 7 of 7
  sets and `rsi2_reversion` lost on all 12 (both versions), often with
  t below -4.

**So the honest answer is still: nothing here has an edge you should put
money on.** What did get better is the tooling, so the bot can't quietly
trade a strategy that has failed (below).

## Every out-of-sample result at ₹50k

Expectancy in R per trade, after all charges (t-stat in brackets). The first
two columns are doc 14's 70/30 split and were run before the
`max_cost_pct_of_risk` rule existed; the rest have it on.

| strategy | Watchlist OOS 2021-26 | NIFTY 50 OOS 2021-26 | Random-30 A, 2010-20 | Random-30 A, 2021-26 | Watchlist, 2021-26 | Holdout-30 B, 2010-20 | Holdout-30 B, 2021-26 | positive |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ema_trend | -0.31 (-1.5) | -0.25 (-1.9) | +0.18 (+1.6) | -0.17 (-1.1) | -0.26 (-1.2) | +0.10 (+0.9) | -0.24 (-1.8) | 2/7 |
| ema_trend_v2 | – | – | +0.14 (+1.0) | +0.43 (+1.1) | -0.12 (-0.9) | -0.22 (-2.2) | +0.08 (+0.4) | 3/5 |
| macd_momentum | -0.20 (-2.3) | -0.16 (-2.3) | -0.16 (-3.4) | -0.07 (-1.1) | -0.21 (-2.6) | -0.17 (-3.5) | -0.16 (-2.5) | 0/7 |
| macd_momentum_v2 | – | – | -0.01 (-0.1) | +0.13 (+0.7) | -0.10 (-0.7) | +0.16 (+1.2) | -0.16 (-0.8) | 2/5 |
| donchian_breakout | -0.20 (-1.3) | -0.35 (-2.9) | +0.00 (+0.0) | +0.03 (+0.1) | -0.04 (-0.3) | -0.24 (-2.3) | -0.03 (-0.2) | 2/7 |
| donchian_breakout_v2 | – | – | +0.25 (+1.1) | +0.80 (+1.5) | +0.07 (+0.2) | -0.05 (-0.4) | -0.31 (-1.9) | 3/5 |
| rsi2_reversion | -0.27 (-6.8) | -0.23 (-8.2) | -0.12 (-6.1) | -0.18 (-6.5) | -0.18 (-5.4) | -0.14 (-6.7) | -0.25 (-8.1) | 0/7 |
| rsi2_reversion_v2 | – | – | -0.12 (-5.2) | -0.14 (-4.8) | -0.14 (-3.9) | -0.12 (-5.9) | -0.16 (-4.7) | 0/5 |
| supertrend_adx | +0.16 (+0.5) | -0.10 (-0.7) | +0.02 (+0.1) | -0.11 (-0.6) | +0.32 (+1.1) | -0.03 (-0.2) | +0.40 (+2.1) | 4/7 |

Buy-and-hold of holdout B returned +403 % over 2010-2020 and +149 % over
2021-2026, and NIFTY +167 % and +64 %, against single-digit returns or losses
for every strategy.

Full ₹50k and ₹5 lakh tables: `docs/validation-results/v3_hold_*.json`.

## What changed in the code

- **`python -m growwbot strategies`** lists every strategy with its test status
  (`failed` / `unproven`) and the evidence. No strategy is `validated`.
- **`run --live` refuses a strategy whose status is `failed`.** Paper mode
  still runs it, with a warning. The status comes from `STATUS` in
  `growwbot/strategies.py` and should only change after a new out-of-sample
  test.
- `scan` shows each signal's status; `backtest` prints it.
- The `auto-trader`, `market-scanner` and `strategy-backtester` skills tell
  the user the status before acting.
- `scripts/compare_versions.py --universe random:N:SEED:EXCLUDE_SEED` draws a
  fresh basket that doesn't overlap an earlier draw.

## If you want to keep looking for an edge

More rule tweaks on the same stocks will mostly find noise. Things that
would change the picture:

1. **More trades per test.** Run the trend strategies on the NIFTY 200 or 500
   (more stocks, same rules) so one test has 500+ trades instead of 50-130.
2. **A different kind of strategy.** All of these are single-stock
   technical entries. Monthly-rebalanced momentum or low-volatility
   portfolios have much stronger published evidence in Indian equities, and
   trade less often, which also suits Groww's fixed charges.
3. **More capital per trade.** At ₹50k, delivery charges alone are 0.5-0.9 %
   a round trip. Nearly every strategy did better at ₹5 lakh.

Until one of these produces a strategy that is positive on several baskets
with a t-stat comfortably above 2, an index fund has beaten everything in
this repo.

*Not investment advice. Past results, good or bad, don't predict future ones.*
