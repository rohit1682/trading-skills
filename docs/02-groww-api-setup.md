# 2. Groww API setup

Official docs: <https://groww.in/trade-api/docs/python-sdk>. The bot uses the
official `growwapi` SDK.

## Get credentials

1. Log in to Groww, open **Profile → Settings → Trading APIs** (Groww Cloud API Keys page).
2. Subscribe to the Trade API if needed (it's a paid plan; check the current price there).
3. Create a key. Two kinds:
   - **TOTP key (recommended for a bot).** No daily approval. Save the API key as
     `GROWW_API_KEY` and the TOTP secret (the text behind the QR code) as
     `GROWW_TOTP_SECRET` in `.env`. The bot generates the 6-digit code itself with `pyotp`.
   - **API key + secret.** Needs approval in the Groww app every day. Use
     `GROWW_API_KEY` + `GROWW_API_SECRET`.
4. Or paste a ready access token into `GROWW_ACCESS_TOKEN` (expires daily).
5. `python -m growwbot doctor` should print `groww login: OK` and your cash.

`.env` is git-ignored. Never commit it, paste it into chat, or share screenshots of it.

## SEBI retail algo framework (from 1 April 2026)

- Brokers may require API orders to come from a **registered static IP**.
  Follow Groww's instructions on the Trading APIs page to register the IP of
  the PC that runs the bot. A home connection usually has a changing IP; ask
  your ISP for a static IP or run the bot on a small cloud VM with one.
- Above **10 orders per second** an algo must be registered with the exchange.
  The bot is capped at 1 order/second (`max_orders_per_second`).
- Your own "white-box" strategy for your own account doesn't need a research
  analyst licence. Selling signals or running money for others does. Don't.
- A kill switch is expected. Use `python -m growwbot kill --flatten --live`.

Rules change; check Groww's and SEBI's current notices.

## Groww API limits the bot respects

| type | per second | per minute |
| --- | --- | --- |
| orders (place / modify / cancel) | 10 | 250 |
| live data (quote, LTP, OHLC) | 10 | 300 |
| non-trading (status, positions, holdings, margin) | 20 | 500 |

Historical candles per request: 1-5 minute bars up to 30 days, 10-30 minute
bars up to 90 days, hourly and daily up to 180 days. The loader splits longer
ranges automatically.

## Products used

- **CNC** (delivery) for daily swing strategies. Stops are DAY SL-M orders,
  re-placed each morning by the engine.
- **MIS** (intraday) for `vwap_pullback` and `orb`. The bot exits by 15:10.
  Groww auto-squares-off MIS later in the afternoon and charges for it.

Next: [Configuration](03-configuration.md).
