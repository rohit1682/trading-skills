# 11. Architecture

```
skills/*/SKILL.md          what Claude does and which commands it runs
        │
        ▼
growwbot/cli.py            argparse commands (python -m growwbot ...)
   │        │         │
   │        │         └── analytics.py   regime, screener, RS, pivots, Monte Carlo, walk-forward, portfolio
   │        │             alerts.py      price/RSI alerts (+ Telegram)
   │        └── backtest.py              portfolio simulator ─┐
   │                                                          │ same rules
   └── engine.py   live/paper loop ─── risk.py ◄──────────────┘
          │            │                 costs.py (Groww charges)
          │            └── strategies.py ── indicators.py
          ├── broker.py   PaperBroker | GrowwBroker (live gates)
          └── data.py     candles: Groww → Yahoo → CSV
                    groww_client.py   the only module that calls the growwapi SDK
config.py   config.toml + .env + state/ paths
```

Design rules:
- **One set of rules** for backtest, paper and live: same strategies, same
  `RiskManager`, same cost model.
- **No look-ahead:** strategies only see completed bars; a test enforces it.
- **The SDK is isolated** in `groww_client.py` / `broker.py`; tests use a fake SDK.
- **Live is opt-in three times** (`broker.make_broker`).
- **State is plain files** in `state/` (JSON/CSV), easy to inspect and back up.

## Adding a strategy

1. Write a function in `growwbot/strategies.py` that takes a candle DataFrame
   and parameters and returns a DataFrame with `entry`, `exit`, `stop`, `target`
   (use `np.nan` for no target). Use only past and current bars.
2. Register it in `STRATEGIES` with a name, description, interval (`1day`,
   `5minute`, ...), `intraday` flag and optional `max_hold_bars`.
3. Add a default grid in `analytics.DEFAULT_GRIDS`.
4. `python -m pytest`: the look-ahead and stop-below-close tests run on every
   registered strategy automatically.
5. Backtest, walk-forward, paper trade. In that order.

## Tests

```bash
python -m pytest            # ~45 tests, no network
```

`tests/test_live_broker.py` drives the live engine against a fake Groww SDK to
check order sequencing (entry, broker stop, cancel-then-sell, reconcile).
