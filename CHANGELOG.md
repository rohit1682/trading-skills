# Changelog

## Unreleased

- Fresh 30-stock holdout (doc 16): `donchian_breakout_v2`'s earlier promise
  did not replicate; no strategy is positive on every out-of-sample set.
  A v3 momentum-filter variant was tried on the design data, didn't help,
  and was dropped.
- New `strategies` command with each strategy's test status and evidence;
  `scan` and `backtest` show it; `run --live` refuses a `failed` strategy.
- Six v2 strategies (`ema_trend_v2`, `macd_momentum_v2`, `donchian_breakout_v2`,
  `rsi2_reversion_v2`, `vwap_pullback_v2`, `orb_v2`) rewritten from why v1
  lost, then tested on 30 random other stocks (2010-2020) and on 2021-2026:
  `docs/15-strategy-v2.md`. `donchian_breakout_v2` improved on every test
  set but is not statistically proven; the rest are mixed or still lose.
- New risk rule `max_cost_pct_of_risk` (default 25): skip trades whose
  round-trip Groww charges exceed that share of the rupees at risk.
- `scripts/compare_versions.py` for side-by-side tests over explicit windows
  and random stock draws; validation results (JSON) in `docs/validation-results/`.
- `docs/14-historical-validation.md`: every strategy tested on 2010-2026 NSE
  data (watchlist and NIFTY 50), with a 70/30 time split, Groww charges,
  slippage and all risk rules. Result: no strategy has a demonstrated edge out
  of sample; the intraday ones lose even before charges.
- `scripts/validate_strategies.py` (IS/OOS backtests plus t-stats, bootstrap
  intervals, before-cost runs, buy-and-hold, Monte Carlo and a look-ahead
  probe) and `scripts/fetch_data.py` (Yahoo download for it).

## 0.3.0 (2026-10-31)

- New `trade-odds` skill and `growwbot odds` command: bootstrap replays of a
  single planned trade, with time-of-day-matched sampling for intraday,
  pessimistic within-bar fills, historical precedent for the same strategy on
  that symbol, and a verdict measured against the break-even win rate.
  Adapted from the "time machine" in Jake Schincariol's day-trader-skill (MIT).
- `backtest` now reports `avg_win_r`, `avg_loss_r` and `breakeven_win_rate_pct`;
  `size` reports the break-even win rate its reward:risk implies.
- 18 skills, 60 tests.

## 0.2.0 (2026-10-27)

- 9 new skills: market-regime, daily-trading-plan, stock-screener,
  relative-strength, pivot-levels, portfolio-review, price-alerts,
  strategy-optimizer, risk-of-ruin (17 total).
- New commands: `regime`, `screen`, `rank`, `levels`, `portfolio`, `plan`,
  `alerts`, `optimize`, `montecarlo`, `install-skills`.
- Universes: NIFTY 50 and Bank NIFTY symbol lists.
- Full documentation in `docs/` (12 guides), CONTRIBUTING, SECURITY.
- Windows support: `install-skills` replaces symlinks, `tzdata` dependency,
  Task Scheduler guide.

## 0.1.0 (2026-10-27)

- `growwbot` engine: indicators, 7 strategies, risk manager, Groww cost model,
  portfolio backtester, paper and live brokers, automatic engine, CLI.
- 8 skills: groww-setup, market-scanner, technical-analysis,
  strategy-backtester, risk-manager, trade-executor, auto-trader, trade-journal.
