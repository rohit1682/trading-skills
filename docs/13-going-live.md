# 13. Going live: step by step

This is the practical, in-order walkthrough for moving from paper to real
orders on Groww. [Paper to live](09-paper-to-live.md) is the short checklist;
this page explains each step and what "done" looks like.

> **Nothing here is switched on for you.** The repo ships with the live gate
> closed (`mode = "paper"`, no `GROWW_ENABLE_LIVE`). Every step that opens it is
> one you do by hand. If any step fails, stay on paper.

> **Untested against real orders.** The live broker (`growwbot/broker.py`,
> `GrowwBroker`) has only been exercised with a fake SDK in the tests. Your first
> live order is also the first real test of that code. That is why Step 8 is a
> single one-share order you watch end to end.

---

## Step 1. Activate the Groww Trade API subscription

The Trade API is a paid plan (about Rs 499/month at the time of writing; check
the current price). Without it, login and the cash/margin calls work, but
market data (LTP, quotes, candles) returns **"Access forbidden for this
request"**, and orders will not go through either.

1. In the Groww app or website, open **Profile → Settings → Trading APIs**
   (<https://groww.in/user/profile/trading-apis>) and subscribe.
2. Wait for it to show as active, then run:

   ```
   python -m growwbot doctor
   python -m growwbot analyze RELIANCE --source groww
   ```

**Done when:** `doctor` shows `groww login: OK` and `analyze ... --source groww`
prints indicators instead of "Access forbidden".

Why this matters for live trading: in live mode the engine takes prices from
Groww LTP. If that fails it silently falls back to the last Yahoo Finance
1-minute candle, which can be stale. Do not trade live on the fallback.

## Step 2. Sort out daily login (key + secret vs TOTP)

Your current key is the **API key + secret** type. It has to be **approved in
the Groww app every day**; the approval resets at about 5 AM IST. Until you
approve it, every call (including order calls) fails to log in.

Pick one:

- **Keep key + secret.** Each trading morning, before 09:15: open the Groww app,
  approve the API key, then run `python -m growwbot doctor`. If you schedule the
  engine (see [automation](10-automation.md)), it will fail on any morning you
  forget, so check the log.
- **Switch to a TOTP key (recommended for an unattended bot).** On
  <https://groww.in/trade-api/api-keys>, open the dropdown next to
  **Generate API Key → Generate TOTP token**. The QR secret is shown **once**;
  copy the text secret (base32: only A-Z and 2-7). In `.env`:

  ```
  GROWW_API_KEY=<the new TOTP key>
  GROWW_TOTP_SECRET=<the base32 secret>
  GROWW_API_SECRET=
  ```

  The bot then makes the 6-digit code itself with `pyotp`; no daily approval.

**Done when:** `doctor` shows `groww login: OK` on a fresh morning without you
touching the app (TOTP), or right after you approve it (key + secret).

Never paste `.env` contents or screenshots of it into a chat or commit.

## Step 3. Register a static IP

Under SEBI's retail-algo framework, Groww only accepts API **orders** from a
registered static IP. Without it, orders are rejected even if everything else
works.

1. Decide where the bot will run:
   - **Your PC at home.** Most home broadband IPs change. Ask your ISP for a
     static IP (typically Rs 300-1,000/month extra).
   - **A small cloud VM** with a fixed public IP (a few dollars a month). The
     bot, `.env` and `config.toml` then live on the VM.
2. Find the machine's public IP. On Windows PowerShell:
   `Invoke-RestMethod https://ifconfig.me` (macOS/Linux: `curl https://ifconfig.me`).
   Run it twice on different days; if it changes, it is not static.
3. On <https://groww.in/trade-api/api-keys>, click **Add static IP**, enter it as
   the **Primary** IP (optionally a backup as **Secondary**), and click **Update**.

**Done when:** Groww shows the IP as whitelisted and it matches what
`ifconfig.me` reports from the machine that runs the bot. The real proof is
the test order in Step 8.

Corporate VPNs and office networks change your outgoing IP. Run the bot off the
VPN, from the registered connection.

## Step 4. Fund the account

The account showed about Rs 1 in cash. The bot uses the **smaller** of
`capital` in `config.toml` and the cash Groww reports
(`cnc_balance_available`), so with no cash it will size every trade to zero.

How much: start with **Rs 10,000-25,000** that you can afford to lose entirely.
Small trades pay proportionally more in charges. Groww's minimum brokerage is
Rs 5 per order, and a delivery sell adds about Rs 20 in DP charges, so:

| test | round-trip charges (approx.) |
| --- | --- |
| 1 share at Rs 300, intraday (MIS) | ~Rs 12 |
| 1 share at Rs 300, delivery (CNC) | ~Rs 36 |
| Rs 5,000 position, delivery | ~Rs 40 (0.8 %) |

Check any trade with `python -m growwbot costs --buy 300 --sell 300 --qty 1 --intraday`.

1. Add funds in the Groww app (UPI / net banking).
2. Run `python -m growwbot doctor`.

**Done when:** `groww cash:` shows the amount you added.

## Step 5. Finish the pre-flight checks (still on paper)

Do not skip these because the account is now ready. Each one has a command.

**Backtest with an out-of-sample split**

```
python -m growwbot backtest --strategy supertrend_adx --split 0.7
```

- At least 30 trades in total.
- The out-of-sample part (last 30 %) still makes money after charges.
- Win rate is above the break-even win rate for its average win and loss
  (v0.3.0+ prints this in the backtest summary).

**Monte Carlo drawdown**

```
python -m growwbot montecarlo --strategy supertrend_adx
```

The p95 drawdown is a loss you could sit through without switching the bot off.

**Paper trading: 2-4 weeks minimum**

```
python -m growwbot run            # every trading day (paper)
python -m growwbot report         # weekly
```

- 20-30+ paper trades.
- `report` win rate, average R and profit factor are roughly in line with the backtest.
- You have checked several trades against the chart by hand.
- You have tried `kill`, `unkill` and `flatten` in paper mode.

**Position sizing and limits.** Set these in `config.toml` `[risk]` for the
first live month (the defaults are already conservative):

| setting | first month live | what it means with Rs 10,000 |
| --- | --- | --- |
| `capital` | 10000 | the bot never uses more than this |
| `risk_per_trade_pct` | 0.5 (or lower) | max Rs 50 lost if a stop is hit |
| `max_position_pct` | 20 | no position above Rs 2,000 |
| `max_open_positions` | 2-3 | |
| `max_daily_loss_pct` | 2.0 | at -Rs 200 for the day the bot flattens and trips the kill switch |
| `max_trades_per_day` | 2-4 | |
| `max_consecutive_losses` | 3 | stops new entries for the day |

Preview what one trade would look like:

```
python -m growwbot size RELIANCE --entry 1400 --stop 1372 --target 1456
```

It prints the quantity, rupee loss at the stop, charges, and PASS/BLOCK.

**Done when:** every box in [Paper to live](09-paper-to-live.md) up to
"Account and setup" is ticked.

## Step 6. Understand the live gate

Live orders need **all three** of these at once. Anything less gives you the
paper broker, which never calls Groww's order APIs
(`growwbot/broker.py`, `live_blockers()` and `make_broker()`):

| # | where | value needed | default |
| --- | --- | --- | --- |
| 1 | `config.toml` | `mode = "live"` | `"paper"` |
| 2 | `.env` | `GROWW_ENABLE_LIVE=YES_I_ACCEPT_REAL_MONEY_RISK` (exact text) | not set |
| 3 | the command | `--live` flag | not passed |

How it behaves:

- Without `--live`, the paper broker is used, whatever the config says.
- With `--live` but missing 1 or 2, the command **refuses and exits**, listing
  what is missing. It does not fall back to paper silently.
- `python -m growwbot doctor` prints `live trading: OFF (...)` with the missing
  items, or `ENABLED when you pass --live` when 1 and 2 are set.
- `trade` additionally needs `--yes`; without it, it prints the order ticket
  and sends nothing.

Do **not** change the code (`LIVE_ACK` in `growwbot/config.py` or
`live_blockers()`) to make this easier. The gate is the only thing between a
typo and a real order.

## Step 7. Open the gate (you do this, by hand)

Only after Steps 1-5 are done.

1. In `config.toml` (your own copy, git-ignored):

   ```toml
   mode = "live"
   capital = 10000
   ```

2. In `.env` (git-ignored), add the line exactly:

   ```
   GROWW_ENABLE_LIVE=YES_I_ACCEPT_REAL_MONEY_RISK
   ```

3. Make sure the kill switch is off and nothing old is lying around:

   ```
   python -m growwbot doctor
   python -m growwbot positions --live
   ```

**Done when:** `doctor` says `live trading: ENABLED when you pass --live`,
`kill switch: off`, and `positions --live` shows no bot positions and matches
the Groww app.

## Step 8. One tiny order, watched end to end

Do this on a normal trading day between 09:30 and 14:30 IST, with the Groww app
open. Use a liquid stock priced Rs 100-500 so one share is cheap. Intraday
(MIS) keeps charges to about Rs 12 and the bot closes it the same day.

1. **Print the ticket (sends nothing):**

   ```
   python -m growwbot trade ITC --qty 1 --stop <about 2% below price> --intraday --live
   ```

   Check: it says `TICKET [LIVE (REAL MONEY)] BUY 1 ITC`, the risk check says
   `PASS`, and the max loss is a few rupees.

2. **Send it:** run the same command with `--yes` added.

3. **Verify the fill**, all three places:
   - The Groww app **Orders** tab: a BUY for 1 share, status Executed, plus an
     open **SL-M SELL** at your stop price.
   - `python -m growwbot positions --live`: the bot position, `groww_positions`
     showing 1 share, and the SL-M in `groww_open_orders`.
   - `state/orders.log`: `place_order`, `place_order_resp`, `fill` (with
     `groww_order_id`, status and average price) and `place_stop_resp`. Any
     `*_error` line means stop and read it.

4. **Exit it:**

   ```
   python -m growwbot flatten --live
   ```

   Check in the Groww app that the position is closed and the SL-M order was
   cancelled. If the SL-M is still open, cancel it in the app.

5. **Compare costs:** the next day, check the contract note in Groww against
   `python -m growwbot costs --buy <fill> --sell <exit> --qty 1 --intraday`.

**If something goes wrong:**

| symptom | likely cause |
| --- | --- |
| login error | key not approved today (Step 2) |
| order rejected mentioning IP | static IP not registered, or you're on a VPN (Step 3) |
| "Access forbidden" | Trade API subscription not active (Step 1) |
| qty 0 / BLOCK | not enough cash, outside entry hours, or price under `min_price` |
| `[WARN] broker stop ... NOT placed` | close the position in the app now, then read `orders.log` |

To stop everything at any point: `python -m growwbot kill --flatten --live`, or
exit positions and cancel orders directly in the Groww app.

## Step 9. Let the engine trade, still small

After one clean round trip:

```
python -m growwbot run --live
```

- Watch the whole first session. Then at least the open and close of the first
  week.
- Daily: Groww positions/orders match `positions --live`; read `state/orders.log`.
- Weekly: `python -m growwbot report --live` against paper and the backtest.
- Monthly: reconcile with Groww's contract notes and P&L statement.
- Raise `capital` only after a full month that matches expectations, and in
  small steps.

## Going back to paper

Any of these closes the gate: set `mode = "paper"`, delete the
`GROWW_ENABLE_LIVE` line, or just run without `--live`. Open live positions
keep their Groww SL-M stops; manage or exit them in the app.

Next: [FAQ and troubleshooting](12-faq.md). See also the [DISCLAIMER](../DISCLAIMER.md).
