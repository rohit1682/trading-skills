# 4. Skills guide

17 skills in four groups. Each folder in `skills/` has a `SKILL.md` that tells
Claude when to use it and which commands to run. Install with
`python -m growwbot install-skills`.

## Setup

| skill | ask things like |
| --- | --- |
| `groww-setup` | "set up my Groww bot", "run doctor", "connect my API key" |

## Research (read-only, never trade)

| skill | ask things like |
| --- | --- |
| `market-regime` | "how's the market today?", "should I be trading?" |
| `daily-trading-plan` | "plan my trading day", "pre-market checklist" |
| `market-scanner` | "any setups on my watchlist?", "scan with all strategies" |
| `stock-screener` | "NIFTY 50 stocks near 52-week highs", "oversold in an uptrend" |
| `relative-strength` | "top 10 momentum stocks", "leaders vs laggards in banks" |
| `technical-analysis` | "analyse HDFCBANK", "what do the indicators say on TCS?" |
| `pivot-levels` | "CPR and pivots for NIFTY tomorrow", "support for INFY" |
| `portfolio-review` | "review my Groww holdings", "which holdings are weak?" |
| `price-alerts` | "alert me if RELIANCE crosses 1450" |

## Strategy testing

| skill | ask things like |
| --- | --- |
| `strategy-backtester` | "backtest all strategies on bank stocks with out-of-sample" |
| `strategy-optimizer` | "tune supertrend_adx with walk-forward" |
| `risk-of-ruin` | "how bad can drawdowns get at 1 % risk?" |

## Trading

| skill | ask things like |
| --- | --- |
| `risk-manager` | "size a trade in SBIN, entry 820 stop 810", "kill switch on" |
| `trade-executor` | "buy TCS with stop 3880 target 4120" (shows a ticket, waits for your yes) |
| `auto-trader` | "start paper trading", "what's the bot holding?", "stop the bot" |
| `trade-journal` | "how did the bot do this week?", "am I ready to go live?" |

## A typical day

1. Morning: `daily-trading-plan` (includes the regime).
2. Start the engine (`auto-trader`), paper or live.
3. During the day: `price-alerts`, `auto-trader` for status.
4. Evening: `trade-journal`, and `pivot-levels` for tomorrow.
5. Weekend: `relative-strength` / `stock-screener` to refresh the watchlist,
   `strategy-backtester` if anything changed.

## What the skills will not do

- Place a live order or start live trading unless you explicitly ask for that
  exact action, and the three live gates are on.
- Flip the live gates for you, or loosen risk limits to let a trade through.
- Promise profits or say a stock "will" go up.
