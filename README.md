# groww-trading-skills

Claude skills plus a small Python engine (`growwbot`) for trading NSE stocks
through your **Groww** account with well-known technical indicators: EMA,
RSI, MACD, ADX, Supertrend, ATR, Bollinger Bands, VWAP and Donchian channels.

It scans, analyses, backtests, sizes, places and manages trades, and can run
fully automatically during market hours. It starts in **paper trading** and
only sends real orders after three separate opt-ins.

> **Read [DISCLAIMER.md](DISCLAIMER.md) first.** Nothing here guarantees a
> profit. Indicators are not predictions. SEBI found that 7 in 10 individual
> intraday traders in the equity cash segment lost money in FY2022-23. What
> this toolkit can do is enforce discipline: fixed risk per trade, hard stops,
> a daily loss limit, a kill switch, and honest backtests that include Groww's
> charges.

## The skills

| skill | what it does |
| --- | --- |
| [`groww-setup`](skills/groww-setup/SKILL.md) | Install, connect the Groww Trade API (TOTP or key+secret), `doctor` health check |
| [`market-scanner`](skills/market-scanner/SKILL.md) | Scan the watchlist for fresh entry signals with stop, target and risk % |
| [`technical-analysis`](skills/technical-analysis/SKILL.md) | Full indicator read of one stock, and which strategies fire on it |
| [`strategy-backtester`](skills/strategy-backtester/SKILL.md) | Backtest with Groww charges, slippage, gap-through stops, risk rules; out-of-sample split |
| [`risk-manager`](skills/risk-manager/SKILL.md) | Position sizing, PASS/BLOCK pre-trade checks, kill switch |
| [`trade-executor`](skills/trade-executor/SKILL.md) | One trade: ticket, risk check, your explicit yes, then paper or live order + broker stop |
| [`auto-trader`](skills/auto-trader/SKILL.md) | The automatic engine: signals, entries, stops, targets, square-off, daily loss breaker |
| [`trade-journal`](skills/trade-journal/SKILL.md) | P&L after charges, win rate, profit factor, by-symbol and by-exit review |

## Strategies

| name | timeframe | idea |
| --- | --- | --- |
| `ema_trend` | daily, CNC | EMA 9/21 cross above the 200 EMA, ADX ≥ 20, RSI 50-70; stop 2 ATR, target 4 ATR |
| `supertrend_adx` | daily, CNC | Supertrend(10,3) flips up, ADX ≥ 20, above EMA50, volume ≥ 1.2x; stop on the Supertrend line, 2R target |
| `rsi2_reversion` | daily, CNC | Connors RSI(2) < 10 above the 200 SMA; exit above the 5 SMA; 10-day time stop |
| `macd_momentum` | daily, CNC | MACD crosses signal with EMA50 > EMA200 and RSI > 50 |
| `donchian_breakout` | daily, CNC | 20-day high breakout on 1.5x volume, exit at the 10-day low |
| `vwap_pullback` | 5-min, MIS | Intraday uptrend (above VWAP, EMA9 > EMA21), dip to EMA21/VWAP, bullish close; 2R target |
| `orb` | 5-min, MIS | 15-minute opening-range breakout above VWAP on 1.5x volume; stop at the range midpoint |

All are long-only and use completed candles only (a test checks that no
strategy looks ahead). An optional market-regime filter blocks new longs
while NIFTY 50 is below its 50-day EMA. **Backtest them on your own symbols
before trusting any of them**: which one (if any) works depends on the
stocks and the market phase.

## Quick start

```bash
git clone <your repo url> groww-trading-skills && cd groww-trading-skills
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.toml config.toml      # capital, watchlist, strategy, risk limits
cp .env.example .env                    # Groww API key + TOTP secret (never commit)

python -m growwbot doctor               # check everything
python -m growwbot backtest --all --split 0.7
python -m growwbot scan
python -m growwbot analyze RELIANCE
python -m growwbot run                  # automatic PAPER trading during market hours
python -m growwbot report               # how did it do
```

Or just open the folder in Claude Code and ask: "set up my Groww bot",
"backtest all strategies on bank stocks", "scan for setups", "start paper
trading", "how did the bot do this week". The skills are linked into
`.claude/skills/`, so Claude Code picks them up automatically.

### Use the skills in other projects

```bash
# As a plugin, from your pushed GitHub repo:
/plugin marketplace add <your-github-user>/groww-trading-skills
/plugin install groww-trading-skills@groww-trading-skills
```

or copy `skills/*` into `~/.claude/skills/`. Either way, set
`GROWWBOT_HOME=/path/to/groww-trading-skills` so the commands find the engine,
config and state.

## Safety design

- **Paper by default.** Real orders need `mode = "live"` in `config.toml` **and**
  `GROWW_ENABLE_LIVE=YES_I_ACCEPT_REAL_MONEY_RISK` in `.env` **and** `--live`
  on the command. The skills tell Claude never to flip these for you.
- **Every entry is risk-checked**: 0.5 % of capital at risk per trade, 20 %
  max per position, 3 open positions, 4 trades a day, 2 % daily loss limit,
  stop after 3 losses in a row, minimum 1.5 reward:risk, 09:30-14:30 entry
  window for intraday, minimum price, slippage guard, blocked symbols.
- **Broker-side stops.** After each live fill the bot places an SL-M order at
  Groww, so a crash or lost connection doesn't leave the position unprotected.
  It checks whether that stop already filled before it ever sends its own
  sell, so it doesn't sell twice.
- **Kill switch.** `python -m growwbot kill [--flatten]`. Hitting the daily
  loss limit engages it automatically and flattens bot positions.
- **Intraday square-off** at 15:10, before Groww's own auto square-off.
- **Rate limit.** At most 1 order per second, far below SEBI's 10 orders/second
  retail-algo threshold and Groww's API limits.
- **Secrets stay out of git.** `.env`, `config.toml` and `state/` are ignored.
- **The bot only touches positions it opened.**

## Groww API notes

- SDK: [`growwapi`](https://groww.in/trade-api/docs/python-sdk) (official). Auth by
  TOTP (no daily approval) or API key + secret (daily approval).
- The Trade API is a paid Groww subscription; check the current price on Groww's Trading APIs page.
- SEBI's retail algo framework applies from April 2026: register a static IP
  with Groww if they ask for one, and keep the order rate low (the bot does).
- Historical candles: 1-5 min up to 30 days per request, 10-30 min up to 90
  days, hourly/daily up to 180 days; the loader stitches requests together.
- CNC stops are placed as DAY SL-M orders, so the engine re-places them each
  morning while it runs. If the engine isn't running on a trading day, a
  swing position has no broker-side stop that day. Run the engine every
  trading day while you hold swing positions, or add a GTT stop in the Groww app.

## Repo layout

```
growwbot/            Python engine (indicators, strategies, risk, costs, backtest, broker, engine, CLI)
skills/              the 8 Claude skills (SKILL.md each)
.claude/skills/      symlinks so Claude Code loads the skills in this repo
.claude-plugin/      plugin + marketplace manifest
tests/               pytest suite (indicators, risk, costs, backtest, engine, live path with a fake Groww SDK)
config.example.toml  settings template
.env.example         secrets template
```

Run the tests with `pip install -r requirements-dev.txt && python -m pytest`.

## Credits and research

Ideas and structure drawn from
[tradermonty/claude-trading-skills](https://github.com/rohit1682/claude-trading-skills)
(risk-first workflows, honest backtest criteria),
[day-trader-skill](https://github.com/rohit1682/day-trader-skill) (paper by
default, risk gate before the broker, never trade without a yes), the
finance skills on claudemarketplaces.com, Groww's Trade API docs and pricing
page, SEBI's FY23 intraday study, and the classic indicator literature
(Wilder, Appel, Connors, Donchian).

MIT licensed. See [LICENSE](LICENSE).
