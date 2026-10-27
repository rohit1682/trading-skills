---
name: price-alerts
description: >-
  Set and watch price and RSI alerts on NSE stocks (above/below a price, daily
  RSI above/below a level), printed to the console and optionally sent to
  Telegram. Alerts never trade. Use when the user says "alert me when",
  "notify me if", "watch RELIANCE for 1400", "set an alert", "remind me when
  RSI drops below 30".
---

# price-alerts

Run from the repo root.

```bash
python -m growwbot alerts add RELIANCE above 1450 --note "breakout of range"
python -m growwbot alerts add INFY below 1480 --note "stop zone"
python -m growwbot alerts add TCS rsi_below 30
python -m growwbot alerts list
python -m growwbot alerts rm <id>
python -m growwbot alerts watch                  # checks every 60 s until all have fired (Ctrl+C to stop)
python -m growwbot alerts watch --once           # a single check, e.g. from a scheduler
```

Each alert fires once and is kept with its trigger time. Prices come from
Groww LTP when credentials exist, otherwise the last close from Yahoo
Finance (which may be delayed).

**Telegram (optional):** create a bot with @BotFather, send it a message,
get your chat id, then put `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in
`.env`. The user does this themselves; never paste tokens into chat.

Alerts are for attention, not action: when one fires, run
`technical-analysis` before trading, and size with `risk-manager`.
