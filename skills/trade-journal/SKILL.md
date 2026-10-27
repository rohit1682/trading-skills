---
name: trade-journal
description: >-
  Review growwbot paper or live performance from the trade journal: net P&L
  after Groww charges, win rate, profit factor, average R, results by exit
  reason and by symbol, and comparison with the backtest. Use when the user
  asks "how did the bot do", "weekly review", "my P&L", "is paper trading
  working", "should I go live", "what went wrong".
---

# trade-journal

Run from the repo root.

```bash
python -m growwbot report            # paper journal
python -m growwbot report --live     # live journal
python -m growwbot report --json
```

The journal is `state/journal_paper.csv` / `state/journal_live.csv` (one row
per closed trade). Charges are recomputed with Groww's rates. For live
trading, Groww's contract notes are the source of truth; tell the user to
compare monthly.

## Review format

1. Headline: trades, net P&L after charges, win rate, profit factor, avg R.
2. What's working and what isn't: `by_exit_reason` (many "stop" exits with
   few "target" exits means entries are poor or stops too tight; many
   "square-off" exits means intraday moves are too small for the targets),
   `by_symbol` (drop symbols that consistently lose, but only with enough trades).
3. Compare with the backtest of the same strategy over a similar period. A
   big gap means slippage, data differences, or a regime change.
4. Go-live readiness (paper only): at least ~30 trades, profit factor above
   ~1.3 after charges, max drawdown within the user's comfort, behaviour
   matching the backtest. If not met, say "not ready" plainly.

Keep it factual. Losing weeks happen even with a working strategy; changing
rules after every losing week is how traders overfit.
