---
name: trade-executor
description: >-
  Place one bot-managed BUY on Groww with a stop and optional target, in paper
  mode by default or live with explicit opt-in. Shows a ticket, runs the risk
  check, and only sends after the user confirms that exact ticket. The engine
  then manages the stop, target and intraday square-off. Use when the user
  says "buy", "place the trade", "enter RELIANCE", "execute", "go long".
---

# trade-executor

Run from the repo root.

```bash
# 1) Ticket only (nothing is sent):
python -m growwbot trade TCS --stop 3880 --target 4120
python -m growwbot trade SBIN --stop 812 --target 836 --intraday     # MIS
# 2) After the user confirms the exact ticket:
python -m growwbot trade TCS --stop 3880 --target 4120 --yes          # paper
python -m growwbot trade TCS --stop 3880 --target 4120 --yes --live   # REAL MONEY
```

## Procedure (do not skip steps)

1. Get a stop from the user or from `technical-analysis` / `market-scanner`.
   No stop, no trade. Long only.
2. Run the ticket command without `--yes`. Show the user: PAPER or LIVE,
   symbol, quantity, approximate price, product (CNC delivery or MIS
   intraday), stop, target, max loss in rupees, and the risk verdict.
3. If the verdict is BLOCK, stop there and explain why.
4. Ask the user to confirm this exact ticket. Only after a clear "yes" in
   the conversation, re-run with `--yes`. A yes for one ticket is not a yes
   for a different symbol, size or price, or for the next trade.
5. `--live` only if the user explicitly asked for a live order in this
   conversation **and** `python -m growwbot doctor` shows live trading enabled.
   Never edit `config.toml` mode or `.env` to unlock live trading yourself;
   tell the user what to change and let them do it.
6. After a live fill, the bot places an SL-M stop order at Groww. Tell the
   user to check it in the Groww app's Orders tab. Then the position needs the
   engine running (`auto-trader`) to manage target and square-off; MIS
   positions left open are squared off by Groww itself near the close, with a
   fee.

If an order fails, show the message from `state/orders.log` and don't retry in
a loop. Send the user to the Groww app to check what actually happened.
