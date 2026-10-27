# 5. CLI reference

`python -m growwbot [--config PATH] <command> [options]`. Every command
accepts `--json`. Commands that can touch real orders take `--live` and refuse
it unless all three live gates are on.

## Setup

| command | does |
| --- | --- |
| `doctor` | config in use, missing packages, Groww login + cash, live gates, kill switch |
| `install-skills [--scope project\|global]` | copy `skills/` into `.claude/skills` or `~/.claude/skills` |

## Research (read-only)

Common options: `--source auto|groww|yfinance|csv`, `--csv-dir DIR` (files named `SYMBOL_1day.csv`),
`--universe nifty50|banknifty|watchlist|<file>|SYM1 SYM2 ...`.

| command | does |
| --- | --- |
| `regime` | NIFTY trend + breadth + India VIX score and posture |
| `screen PRESET_OR_QUERY` | technical screen ([presets](../skills/stock-screener/SKILL.md)) |
| `rank [--top N]` | relative-strength ranking vs NIFTY |
| `analyze SYMBOL [--interval 1day\|15minute\|5minute]` | full indicator snapshot + which strategies fire |
| `levels SYMBOL` | pivots, CPR, Camarilla, swing support/resistance |
| `scan [--strategy NAME \| --all] [--symbols ...]` | entry signals on the latest completed candle |
| `portfolio [--csv FILE]` | holdings review (Groww read-only, or CSV `symbol,qty,avg_price`) |
| `plan` | pre-market Markdown plan, saved in `state/plans/` |
| `alerts add SYMBOL above\|below\|rsi_above\|rsi_below VALUE [--note]` | add an alert |
| `alerts list` / `alerts rm ID` / `alerts watch [--once] [--interval S]` | manage / run alerts |

## Testing

| command | does |
| --- | --- |
| `backtest [--strategy NAME \| --all] [--symbols ...] [--days N] [--split 0.7] [--capital X] [--no-regime]` | portfolio backtest with charges and risk rules |
| `optimize --strategy NAME [--grid "k=a,b k2=c,d"] [--folds 4] [--days N]` | walk-forward optimisation |
| `montecarlo [--trades-csv FILE \| --strategy NAME] [--risk PCT] [--n TRADES] [--sims N]` | drawdown / streak odds |
| `costs --buy P [--sell P] --qty N [--intraday]` | Groww charges and breakeven move |

## Trading

| command | does |
| --- | --- |
| `size SYMBOL --entry P --stop P [--target P] [--intraday]` | quantity + PASS/BLOCK (exit code 2 on BLOCK) |
| `trade SYMBOL --stop P [--target P] [--qty N] [--price P] [--intraday] [--yes] [--live]` | ticket; sends only with `--yes` |
| `run [--live] [--once]` | the automatic engine, market hours only |
| `positions [--live]` | bot positions, cash, today's risk state (+ Groww positions and open orders when live) |
| `flatten [--live]` | exit all bot positions now |
| `kill [--flatten] [--reason TEXT] [--live]` / `unkill` | kill switch |
| `report [--live]` | journal performance after charges |
| `paper-reset [--capital X]` | reset paper cash; old journal kept as `.bak` |

## Exit codes

0 ok, 1 error, 2 risk BLOCK, 3 live trading refused (a gate is off).
