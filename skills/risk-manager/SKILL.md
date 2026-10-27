---
name: risk-manager
description: >-
  Position sizing and pre-trade risk checks for Groww trades, plus the kill
  switch. Sizes so a stop-out loses a fixed % of capital, and blocks trades
  that break limits: max open positions, daily loss limit, trades per day,
  consecutive losses, reward:risk, entry window, NIFTY regime, blocked
  symbols. Use when the user asks "how many shares", "position size", "is
  this trade safe", "risk check", "stop everything", "kill switch", "I'm
  losing too much", or before any order.
---

# risk-manager

Run from the repo root.

```bash
python -m growwbot size INFY --entry 1500 --stop 1462 --target 1580            # swing (CNC)
python -m growwbot size SBIN --entry 820 --stop 812 --target 836 --intraday    # MIS: adds the 09:30-14:30 window
python -m growwbot costs --buy 820 --sell 836 --qty 30 --intraday              # Groww charges + breakeven move
python -m growwbot positions                                                   # open bot positions, today's P&L and trade count
python -m growwbot kill --reason "news shock"                                  # no new entries
python -m growwbot kill --flatten [--live]                                     # no new entries AND exit all bot positions
python -m growwbot unkill
```

Exit code 0 = PASS, 2 = BLOCK. A BLOCK is final for that trade: report the
reasons, don't look for a way around them, and don't edit config limits to
make one trade pass.

## The rules (config.toml `[risk]`, defaults)

| rule | default | why |
| --- | --- | --- |
| risk_per_trade_pct | 0.5 | 10 losers in a row cost ~5 %, not half the account |
| max_position_pct | 20 | no single stock dominates |
| max_open_positions | 3 | correlated positions add up |
| max_daily_loss_pct | 2 | hit it and the kill switch engages and bot positions are flattened |
| max_trades_per_day | 4 | stops over-trading |
| max_consecutive_losses | 3 | stop for the day after three losers in a row |
| min_reward_risk | 1.5 | the target must be worth the risk |
| entry window (MIS) | 09:30-14:30 | skip the opening auction chaos and late entries |
| squareoff_time (MIS) | 15:10 | flatten before Groww's auto square-off (which charges a fee) |
| regime_filter | true | no new longs while NIFTY is below its 50-day EMA |

Sizing: `qty = min(capital x risk% / (entry - stop), capital x 20% / entry, cash / entry)`.
Charges matter: on small trades Groww's Rs 5 minimum brokerage plus STT can
need a 0.2-0.3 % move just to break even. Show `costs` output for small trades.

When the user is in a losing streak or upset, recommend the kill switch and a
break, not a bigger position to win it back.
