---
name: strategy-optimizer
description: >-
  Walk-forward parameter optimisation for growwbot strategies: tries a grid of
  settings on past data, then judges the winners only on later data they never
  saw, and compares against the default settings to expose curve-fitting. Use
  when the user asks "optimise", "best parameters", "tune the strategy", "what
  ADX/ATR setting works best", "improve the backtest".
---

# strategy-optimizer

Run from the repo root.

```bash
python -m growwbot optimize --strategy supertrend_adx                 # default grid, 4 folds, watchlist
python -m growwbot optimize --strategy ema_trend --grid "adx_min=15,20,25 stop_atr=1.5,2,2.5" --folds 5
python -m growwbot optimize --strategy orb --days 59                  # intraday (5-minute data)
python -m growwbot optimize --strategy rsi2_reversion --universe nifty50 --json
```

Anchored walk-forward: for each fold it optimises on all data before the
test window, then trades the window with the chosen settings. Only the test
windows count. Default grids are in `growwbot/analytics.py` (`DEFAULT_GRIDS`).

## Rules

- Report `oos_return_pct_compounded` next to
  `default_params_oos_return_pct_compounded`, the number of out-of-sample
  trades, and whether parameters were stable across folds. Quote the
  `verdict` line.
- Adopt new parameters only if they beat the defaults out of sample, with 30+
  OOS trades, and the chosen values are similar across folds. Otherwise
  recommend keeping the defaults.
- Bigger grids find better-looking in-sample results by chance. Keep grids
  small (under ~50 combinations) and say how many were tried.
- If the user adopts new values, they go in `config.toml` under
  `[strategy] params = {...}` (user confirms), then back to paper trading.
