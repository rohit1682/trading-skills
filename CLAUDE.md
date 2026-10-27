# groww-trading-skills

Python engine `growwbot/` + Claude skills in `skills/` (linked into `.claude/skills/`)
for trading NSE stocks via the Groww Trade API. Run commands from the repo root
as `python -m growwbot <command>`; `python -m growwbot -h` lists them.

## Hard rules for Claude in this repo

- Real money is involved. Default to paper. Never pass `--live`, never set
  `mode = "live"`, never write `GROWW_ENABLE_LIVE` in `.env`, unless the user
  explicitly asked for that exact live action in this conversation. Unlocking
  the live gates is the user's job; tell them what to change.
- Never send an order (`trade ... --yes`) without showing the ticket and
  getting a clear yes for that exact ticket.
- Never read `.env` aloud, print secrets, or commit `.env`, `config.toml` or `state/`.
- A risk BLOCK is final. Don't loosen limits in config to let a trade through.
- Don't promise or imply guaranteed profits. Report backtests with their
  weaknesses (trade count, out-of-sample, costs, drawdown).

## Development

- `python -m pytest` must pass. Tests never touch the network or Groww.
- Indicators must not look ahead (see `tests/test_indicators.py::test_no_lookahead_in_any_strategy`).
- New strategies go in `growwbot/strategies.py` and the `STRATEGIES` registry,
  return `entry/exit/stop/target`, and get a backtest test.
- Groww SDK calls live only in `growwbot/groww_client.py` and `growwbot/broker.py`.
