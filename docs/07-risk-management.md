# 7. Risk management

Profit in trading comes from a small edge repeated many times. Risk management
keeps you alive long enough for that edge (if it exists) to show up. Code:
`growwbot/risk.py`.

## Position sizing

```
qty = min( capital × risk% ÷ (entry − stop),     # loss at the stop = risk% of capital
           capital × 20% ÷ entry,                 # position cap
           available cash ÷ entry )
```

Example: Rs 50,000, 0.5 % risk = Rs 250. Entry 1,400, stop 1,372 (Rs 28/share)
→ 8 shares by risk, 7 by the 20 % cap → **7 shares**, max loss about Rs 196
plus charges.

Why 0.5 %: ten losers in a row (it happens, see `montecarlo`) cost about 5 %.
At 5 % risk the same streak costs 40 %.

## Pre-trade checks (every entry)

A trade is BLOCKED if any fails: kill switch on, day halted, blocked symbol,
price under `min_price`, stop not below entry, reward:risk under minimum,
price ran > `max_slippage_pct` past the signal, too many open positions or
trades today, losing streak reached, regime filter, outside the intraday
window, size rounds to 0, or today's realised loss + open risk + this trade's
risk would exceed the daily loss limit. **Exits are never blocked.**

## Daily circuit breakers

- **Daily loss limit** (2 %): realised + unrealised. When hit, the engine turns
  the kill switch on and exits all bot positions.
- **Consecutive losses** (3): no new entries for the rest of the day.
- **Trades per day** (4).

## Kill switch

`state/KILL_SWITCH`. While it exists, no new entries anywhere (engine, `trade`).
Existing positions keep their stops.

```bash
python -m growwbot kill --reason "news"            # stop new entries
python -m growwbot kill --flatten --live           # and exit every bot position at market
python -m growwbot unkill                          # only after you know why it tripped
```

Also: Groww's own app lets you exit positions and cancel orders manually.
Know where those buttons are before going live.

## Stops at the broker

Live entries are followed by an **SL-M sell order at Groww** at the stop, so a
crash, power cut or lost internet doesn't leave a position unprotected. The
engine:
- lets that order handle stop-outs (no double selling), and books the exit when
  the position disappears from Groww;
- exits at market itself if the broker stop was rejected;
- cancels the stop before selling at a target, square-off or exit signal, and
  checks the stop hadn't already filled;
- re-places CNC stops each morning (they're DAY orders).

Gaps still hurt: a stock can open far below the stop after results or news,
and an SL-M fills at the market price. Position caps limit the damage.

## Charges are a risk too

Run `python -m growwbot costs --buy 820 --sell 830 --qty 10 --intraday`. On
small intraday trades, charges can need 0.3 % or more just to break even.

## Behaviour rules worth adopting

- Never move a stop further away. Never average down a losing trade.
- After the daily loss limit trips, stop for the day.
- Don't raise risk to "make back" losses.
- Change strategy rules only after a review over many trades, never after one bad day.
