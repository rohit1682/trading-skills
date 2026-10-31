# Changelog

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
