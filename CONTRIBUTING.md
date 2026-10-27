# Contributing

This is Rohit Ghosh's personal trading toolkit. Issues and pull requests are
welcome, but trading-safety rules come first.

## Ground rules

- Paper trading stays the default. Never weaken the three live gates in
  `growwbot/broker.py` or the risk checks in `growwbot/risk.py`.
- No look-ahead: strategies may only use completed bars. The test suite
  checks every registered strategy.
- No secrets in code, tests, issues or logs.
- Groww SDK calls only in `growwbot/groww_client.py` and `growwbot/broker.py`.
- Tests never touch the network or Groww; use the fakes in `tests/`.

## Workflow

```bash
pip install -r requirements-dev.txt
python -m pytest
```

1. Branch from `main`.
2. Add or update tests with the change.
3. For a new strategy follow [docs/11-architecture.md](docs/11-architecture.md#adding-a-strategy)
   and include backtest results (with out-of-sample) in the PR description.
4. For a new skill add `skills/<name>/SKILL.md` with `name` and `description`
   frontmatter, list it in README and `docs/04-skills-guide.md`.
5. Update `CHANGELOG.md`.
