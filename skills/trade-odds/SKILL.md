---
name: trade-odds
description: >-
  Replay one planned trade thousands of times before taking it. Resamples the
  stock's own recent bars (matched to the time of day for intraday) to show
  how often the plan hits the target first, the stop first or neither, then
  compares that with the win rate the reward:risk actually needs and with
  what the same strategy really did on this symbol. Use when the user asks
  "what are the odds", "is this trade worth taking", "simulate this trade",
  "monte carlo this setup", "how often does this hit the target", "is this a
  coin flip", or after a scan and before sizing or executing.
---

# trade-odds

Run from the repo root (`cd "$GROWWBOT_HOME"` if the skills are installed elsewhere).

```bash
python -m growwbot odds RELIANCE --entry 1400 --stop 1372 --target 1456   # a plan you already have
python -m growwbot odds RELIANCE --entry 1400 --stop 1372 --rr 2          # target from a reward:risk
python -m growwbot odds TCS --strategy supertrend_adx                     # take the plan from the live signal
python -m growwbot odds SBIN --strategy orb --now 2026-10-27T10:30        # intraday, to the 15:10 square-off
python -m growwbot odds INFY --entry 1500 --stop 1462 --target 1576 --json
```

Useful flags: `--sims` (default 10,000), `--seed` (default 19), `--hold`
(bars to hold a daily trade, default 20), `--bars` (override the horizon),
`--window` (time-of-day slots either side to sample from, default 2).

## How it works

1. **The pool.** Every past bar becomes four ratios to the previous close
   (open, high, low, close). For intraday the pool is split by slot in the
   trading day, so the opening hour's volatility is not used to model the
   lunch lull.
2. **The replays.** Each path starts at the entry and draws one bar at a
   time. Inside a bar the stop is checked before the target, and a bar that
   opens below the stop fills at the open, so a gap can cost more than 1R.
   Both choices make the result pessimistic on purpose.
3. **The horizon.** Intraday runs to the square-off time in `config.toml`;
   daily runs for `--hold` bars.
4. **The history.** With `--strategy`, the same strategy is re-run over that
   symbol's real history: how often it fired, the win rate, the average R.
   That is what happened, not a simulation.
5. **The verdict.** A 2R target only needs to win 1 in 3 of the trades that
   reach a side, a 3R target 1 in 4. The verdict compares the replays with
   that break-even bar, so a 35 % hit rate can still be a good plan.

The seed makes it repeatable: same plan, same data, same seed, same numbers.

## Reporting it

Give the four percentages, the average R, the history line, then the verdict
and any notes exactly as printed, and say the seed. Then:

- If the verdict says coin flip or close to break-even, say so plainly. Do
  not dress it up or look for a reason to take the trade anyway.
- If the replays and the history disagree, the tool says so. Lead with the
  history: it is real, the replays only assume the future resembles a
  resampled past.
- A high "neither" share means the exit price decides most paths, so the
  numbers are softer than they look.
- Say once that this is built from recent bars and is not a prediction.
  Results, news, circuit limits and halts do things the sample never did,
  and a good-looking replay does not make a trade safe.

Next steps: `risk-manager` to size it, then `trade-executor`. Odds never
place an order and never override a risk BLOCK.
