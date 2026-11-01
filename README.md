# trading-skills

**Owner:** Rohit Ghosh ([@rohit1682](https://github.com/rohit1682)) · MIT licence · v0.3.0

18 Claude skills plus a Python engine (`growwbot`) for trading NSE stocks
through your **Groww** account with proven technical indicators: EMA, RSI,
MACD, ADX, Supertrend, ATR, Bollinger Bands, VWAP, Donchian channels, pivots
and CPR.

It reads the market regime, screens and ranks stocks, analyses charts,
backtests and walk-forward-tests strategies, stress-tests drawdowns, sizes
positions, places and manages trades, and can trade fully automatically
during market hours. It starts in **paper trading** and only sends real
orders after three separate opt-ins.

> **Read [DISCLAIMER.md](DISCLAIMER.md) first.** Nothing here guarantees a
> profit. SEBI found that about 7 in 10 individual intraday traders in the
> equity cash segment lost money in FY2022-23. What this toolkit gives you is
> discipline: fixed risk per trade, hard stops at the broker, a daily loss
> limit, a kill switch, and honest backtests that include Groww's charges.

## The skills

| group | skill | what it does |
| --- | --- | --- |
| Setup | [`groww-setup`](skills/groww-setup/SKILL.md) | Install, connect the Groww Trade API (TOTP or key+secret), `doctor` check |
| Research | [`market-regime`](skills/market-regime/SKILL.md) | NIFTY trend + breadth + India VIX → RISK-ON / CAUTIOUS / DEFENSIVE |
| | [`daily-trading-plan`](skills/daily-trading-plan/SKILL.md) | Pre-market plan: regime, risk budget, positions, signals with levels, alerts |
| | [`market-scanner`](skills/market-scanner/SKILL.md) | Fresh entry signals on the watchlist with stop, target and risk % |
| | [`stock-screener`](skills/stock-screener/SKILL.md) | Screen NIFTY 50 / Bank NIFTY / any list with presets or custom filters |
| | [`relative-strength`](skills/relative-strength/SKILL.md) | Momentum ranking vs NIFTY with a 1-99 RS rating |
| | [`technical-analysis`](skills/technical-analysis/SKILL.md) | Full indicator read of one stock and which strategies fire |
| | [`pivot-levels`](skills/pivot-levels/SKILL.md) | Pivots, CPR, Camarilla, swing support/resistance |
| | [`portfolio-review`](skills/portfolio-review/SKILL.md) | Groww holdings health check: trend, weight, suggested stops (read-only) |
| | [`price-alerts`](skills/price-alerts/SKILL.md) | Price/RSI alerts in the console or Telegram |
| Testing | [`trade-odds`](skills/trade-odds/SKILL.md) | Replay one planned trade 10,000 times: target first, stop first, or neither, against its break-even win rate |
| | [`strategy-backtester`](skills/strategy-backtester/SKILL.md) | Backtest with Groww charges, slippage, gap-through stops, risk rules, out-of-sample |
| | [`strategy-optimizer`](skills/strategy-optimizer/SKILL.md) | Walk-forward tuning that exposes curve-fitting |
| | [`risk-of-ruin`](skills/risk-of-ruin/SKILL.md) | Monte Carlo drawdown, losing-streak and ruin odds |
| Trading | [`risk-manager`](skills/risk-manager/SKILL.md) | Position sizing, PASS/BLOCK checks, kill switch |
| | [`trade-executor`](skills/trade-executor/SKILL.md) | One trade: ticket → risk check → your yes → order + broker stop |
| | [`auto-trader`](skills/auto-trader/SKILL.md) | The automatic engine: entries, stops, targets, square-off, loss breaker |
| | [`trade-journal`](skills/trade-journal/SKILL.md) | P&L after charges, win rate, profit factor, go-live readiness |

Example prompts for each: [docs/04-skills-guide.md](docs/04-skills-guide.md).

## Strategies

| name | timeframe | idea |
| --- | --- | --- |
| `ema_trend` | daily, CNC | EMA 9/21 cross above the 200 EMA, ADX ≥ 20, RSI 50-70 |
| `supertrend_adx` | daily, CNC | Supertrend(10,3) flips up, ADX ≥ 20, above EMA 50, volume ≥ 1.2x |
| `rsi2_reversion` | daily, CNC | Connors RSI(2) < 10 above the 200 SMA, exit above the 5 SMA |
| `macd_momentum` | daily, CNC | MACD crosses signal with EMA 50 > EMA 200 and RSI > 50 |
| `donchian_breakout` | daily, CNC | 20-day high breakout on volume, exit at the 10-day low |
| `vwap_pullback` | 5-min, MIS | Intraday pullback to VWAP/EMA 21 in an uptrend |
| `orb` | 5-min, MIS | 15-minute opening-range breakout above VWAP on volume |
| `ema_trend_v2` | daily, CNC | EMA 20/50 cross above the 200 EMA, Chandelier trailing exit |
| `macd_momentum_v2` | daily, CNC | MACD crosses up below zero in an uptrend, Chandelier trailing exit |
| `donchian_breakout_v2` | daily, CNC | Turtle 55-day breakout, exit at the 20-day low |
| `rsi2_reversion_v2` | daily, CNC | RSI(2) < 5 after a 1.5 ATR pullback |
| `vwap_pullback_v2` | 5-min, MIS | VWAP pullback, wider stop, no VWAP exit |
| `orb_v2` | 5-min, MIS | 30-minute opening range, stop at the range low |

**Tested on 2010-2026 NSE data, no strategy has a proven edge yet**, and
buying and holding beat all of them. See
[historical validation](docs/14-historical-validation.md) and
[strategy v2](docs/15-strategy-v2.md) and the
[fresh holdout](docs/16-holdout-and-status.md) before trading any of them.
`python -m growwbot strategies` shows each strategy's test status, and live
trading refuses the ones that failed.

Rules, strengths and failure modes: [docs/06-strategies.md](docs/06-strategies.md).
All are long-only and use completed candles only (a test proves no strategy
looks ahead). **Backtest them on your own symbols before trusting any.**

## Quick start (Windows PowerShell)

```powershell
cd $HOME\Personal\trading-skills
py -3.12 -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
copy config.example.toml config.toml     # capital, watchlist, strategy, risk limits
copy .env.example .env                   # Groww API key + TOTP secret (never commit)

python -m growwbot doctor                # check everything
python -m growwbot install-skills        # make the skills available to Claude Code here
python -m growwbot regime
python -m growwbot backtest --all --split 0.7
python -m growwbot run                   # automatic PAPER trading during market hours
python -m growwbot report
```

macOS/Linux and details: [docs/01-getting-started.md](docs/01-getting-started.md).
Then open the folder in Claude Code and just ask: "plan my trading day",
"backtest all strategies on bank stocks", "start paper trading", "how did the
bot do this week?".

## Safety design

- **Paper by default.** Real orders need `mode = "live"` in `config.toml` **and**
  `GROWW_ENABLE_LIVE=YES_I_ACCEPT_REAL_MONEY_RISK` in `.env` **and** `--live`.
  The skills tell Claude never to flip these for you.
- **Every entry is risk-checked:** 0.5 % of capital at risk per trade, 20 % max
  per position, 3 open positions, 4 trades a day, 2 % daily loss limit, stop
  after 3 losses in a row, minimum 1.5 reward:risk, intraday entry window,
  NIFTY regime filter, slippage guard, blocked symbols.
- **Stops live at Groww.** After each live fill the bot places an SL-M order,
  so a crash or lost connection doesn't leave a position unprotected, and it
  never sells twice.
- **Kill switch** (`python -m growwbot kill --flatten`), tripped automatically
  by the daily loss limit.
- **1 order per second max**, far below SEBI's 10/sec retail-algo threshold.
- **Secrets stay out of git** (`.env`, `config.toml`, `state/` are ignored).
- **Only positions the bot opened are touched.**

More: [docs/07-risk-management.md](docs/07-risk-management.md),
[docs/09-paper-to-live.md](docs/09-paper-to-live.md).

## Documentation

| | |
| --- | --- |
| [Getting started](docs/01-getting-started.md) | [Groww API setup](docs/02-groww-api-setup.md) |
| [Configuration](docs/03-configuration.md) | [Skills guide](docs/04-skills-guide.md) |
| [CLI reference](docs/05-cli-reference.md) | [Strategies](docs/06-strategies.md) |
| [Risk management](docs/07-risk-management.md) | [Backtesting](docs/08-backtesting.md) |
| [Paper to live](docs/09-paper-to-live.md) | [Running automatically](docs/10-automation.md) |
| [Architecture](docs/11-architecture.md) | [FAQ & troubleshooting](docs/12-faq.md) |

## Use the skills elsewhere

```bash
python -m growwbot install-skills --scope global     # copies into ~/.claude/skills
# and set GROWWBOT_HOME to this folder so the commands find the engine
```

Or as a Claude Code plugin once pushed to GitHub:

```
/plugin marketplace add rohit1682/trading-skills
/plugin install trading-skills@trading-skills
```

## Repo layout

```
growwbot/            Python engine: indicators, strategies, risk, costs, backtest,
                     analytics, alerts, broker (paper/live), engine, CLI
skills/              the 18 Claude skills (one SKILL.md each)
docs/                12 guides
universes/           symbol lists (NIFTY 50, Bank NIFTY)
tests/               pytest suite: no network, fake Groww SDK for the live path
.claude-plugin/      plugin + marketplace manifest
config.example.toml  settings template      .env.example  secrets template
```

`pip install -r requirements-dev.txt && python -m pytest` runs the tests.

## Credits and research

Ideas drawn from [tradermonty/claude-trading-skills](https://github.com/rohit1682/claude-trading-skills)
(risk-first workflows, honest backtest criteria),
[Jake Schincariol's day-trader-skill](https://github.com/jakeschincariol/day-trader-skill),
MIT (paper by default, a risk gate before the broker, never trade without a
yes, and the "time machine" idea behind `trade-odds`: time-of-day-matched
bootstrap replays judged against the break-even win rate; the code here is
our own), the
finance skills on claudemarketplaces.com, Groww's Trade API docs and pricing,
SEBI's FY23 intraday study and retail-algo framework, and the indicator
literature (Wilder, Appel, Connors, Donchian, Seykota/Turtles).

## Licence

MIT © 2026 Rohit Ghosh. See [LICENSE](LICENSE).
