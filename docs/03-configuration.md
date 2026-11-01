# 3. Configuration

Two files, both git-ignored, both created from templates:

- `config.toml` (from `config.example.toml`): behaviour and limits.
- `.env` (from `.env.example`): secrets and the live-trading switch.

`GROWWBOT_HOME` (environment variable, optional) points the CLI and skills at
the repo folder when you run them from elsewhere.

## config.toml

| key | default | meaning |
| --- | --- | --- |
| `mode` | `"paper"` | `"live"` is one of the three live gates |
| `capital` | 50000 | rupees the bot may use; live uses min(this, Groww cash) |
| `watchlist` | 15 large caps | symbols the engine scans and trades |
| `[strategy] name` | `supertrend_adx` | one of the 13 strategies ([list](06-strategies.md)) |
| `[strategy] params` | `{}` | overrides, e.g. `{ adx_min = 25, rr = 2.5 }` |
| `[risk] risk_per_trade_pct` | 0.5 | % of capital lost at the stop |
| `[risk] max_position_pct` | 20 | max % of capital in one stock |
| `[risk] max_open_positions` | 3 | |
| `[risk] max_daily_loss_pct` | 2 | trips the kill switch and flattens |
| `[risk] max_trades_per_day` | 4 | |
| `[risk] max_consecutive_losses` | 3 | halts new entries for the day |
| `[risk] min_reward_risk` | 1.5 | only when a target exists |
| `[risk] min_price` | 50 | skips penny stocks |
| `[risk] max_slippage_pct` | 0.5 | skips entries that ran away from the signal |
| `[risk] blocked_symbols` | `[]` | never enter these (F&O ban, ASM/GSM, results week) |
| `[risk] no_entries_before / after` | 09:30 / 14:30 | intraday entry window |
| `[risk] squareoff_time` | 15:10 | intraday exit time |
| `[risk] regime_filter` | true | no new longs while NIFTY < its 50-day EMA |
| `[risk] max_cost_pct_of_risk` | 25 | skip a trade whose round-trip charges exceed this % of the rupees it risks; 0 = off ([why](15-strategy-v2.md)) |
| `[risk] holidays` | `[]` | NSE holidays, `"YYYY-MM-DD"` |
| `[execution] entry_order_type` | MARKET | or LIMIT (signal price + `limit_buffer_pct`) |
| `[execution] place_broker_stop` | true | SL-M at Groww after every live fill |
| `[execution] poll_seconds` | 30 | engine loop interval |
| `[execution] slippage_pct` | 0.05 | per side, paper and backtest |
| `[execution] max_orders_per_second` | 1 | order rate cap |
| `[backtest] initial_capital` | 50000 | |
| `[backtest] days` | 730 | history for daily backtests |
| `[costs] ...` | Groww rates | override any field of `growwbot/costs.py` |

## .env

| key | purpose |
| --- | --- |
| `GROWW_API_KEY` | API key from Groww |
| `GROWW_TOTP_SECRET` | TOTP secret (TOTP flow) |
| `GROWW_API_SECRET` | secret (key+secret flow, daily approval) |
| `GROWW_ACCESS_TOKEN` | a ready token, overrides the above |
| `GROWW_ENABLE_LIVE` | must be exactly `YES_I_ACCEPT_REAL_MONEY_RISK` for live orders |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | optional alert notifications |

## Universes

`universes/*.txt` hold symbol lists (`nifty50`, `banknifty`). Add your own
file and use it with `--universe <name>` in `regime`, `screen`, `rank`,
`montecarlo`, `optimize` and `plan`.

## State (`state/`, git-ignored)

| file | contents |
| --- | --- |
| `paper_account.json` | paper cash |
| `positions_paper.json` / `positions_live.json` | bot positions, stops, last processed bars |
| `journal_paper.csv` / `journal_live.csv` | closed trades |
| `risk_day.json` | today's trades, realised P&L, losing streak |
| `KILL_SWITCH` | exists = kill switch on |
| `orders.log` | every live API call and response |
| `alerts.json`, `plans/`, `backtests/` | alerts, daily plans, backtest outputs |

Back up `state/` if you care about your journal history.
