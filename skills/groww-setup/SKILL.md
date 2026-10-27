---
name: groww-setup
description: >-
  First-time setup and health check for the growwbot Groww trading toolkit:
  install dependencies, create config.toml and .env, connect the Groww Trade
  API (TOTP or key+secret), and verify login, cash and the live-trading gates.
  Use when the user says "set up groww", "connect my groww account", "is my
  bot configured", "doctor", "api key", or anything fails with a credentials
  error.
---

# groww-setup

Commands run from the repo root (the folder with `growwbot/`). If the skills
are installed elsewhere, `cd "$GROWWBOT_HOME"` first.

## 1. Install

```bash
python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Use Python 3.11 or 3.12. If pip fails building `clint` or `args` (old
dependencies of `growwapi`), you are probably on a too-new Python: create the
venv with 3.11/3.12.

## 2. Config and secrets

```bash
cp config.example.toml config.toml
cp .env.example .env
```

- `config.toml` holds capital, watchlist, strategy and risk limits. Walk the
  user through `capital`, `watchlist`, `[strategy] name` and `[risk]`. Keep
  `mode = "paper"`.
- `.env` holds secrets. Never print its contents back, never commit it, never
  paste keys into chat. Ask the user to fill it themselves.

## 3. Groww API access

Tell the user, step by step:
1. Groww app or web: Profile, Settings, Trading APIs (Groww Cloud API keys page).
   The Trade API needs an active subscription on Groww; check the current price
   on that page.
2. Generate a **TOTP** key (recommended for a bot, no daily approval). Put the
   API key in `GROWW_API_KEY` and the TOTP secret (the text behind the QR
   code) in `GROWW_TOTP_SECRET`.
   Or generate an **API key + secret** (`GROWW_API_SECRET`); that flow needs
   approval in the Groww app every day.
3. From April 2026 SEBI's retail-algo framework applies to API trading:
   brokers can require a registered static IP for order APIs and tag algo
   orders. Ask the user to check Groww's API page for the static-IP step and
   to register the IP of the machine that will run the bot. The bot stays at
   1 order/second, far below the 10 orders/second level that needs an
   exchange-registered algo.

## 4. Verify

```bash
python -m growwbot doctor
```

It prints the config in use, missing packages, Groww login status and cash,
whether live trading is unlocked, and the kill switch. Fix every line that is
not OK before moving on. Next step for a new user: `strategy-backtester`.

## Live trading gates (explain, do not flip them for the user)

Real orders need all three: `mode = "live"` in config.toml,
`GROWW_ENABLE_LIVE=YES_I_ACCEPT_REAL_MONEY_RISK` in .env, and `--live` on the
command. Recommend at least 2-4 weeks of paper trading with results close to
the backtest before the user turns any of them on, and only the user edits
these.
