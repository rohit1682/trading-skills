# 8. Backtesting

Code: `growwbot/backtest.py`, `growwbot/analytics.py` (walk-forward, Monte Carlo).

## How the simulator works

- Signals use full history (indicators warmed up) but are read only on
  completed bars; orders fill at the **next bar's open** plus slippage.
- If a bar touches both stop and target, the **stop wins** (pessimistic).
- A gap below the stop fills at the **open**, not the stop.
- Intraday positions close at 15:10 or the day's last bar.
- One shared account across all symbols, with **every risk rule** from live trading.
- Groww charges per order: brokerage (0.1 %, Rs 5-20), STT, stamp duty,
  exchange, SEBI and IPFT fees, GST, DP charge on delivery sells.

Not modelled: partial fills, order-book depth, circuit locks, API outages,
corporate actions in raw (unadjusted) data, and you overriding the bot.

## Commands

```bash
python -m growwbot backtest --all --split 0.7          # compare strategies with a 30 % hold-out
python -m growwbot backtest --strategy orb --days 59   # intraday
python -m growwbot optimize --strategy ema_trend       # walk-forward tuning
python -m growwbot montecarlo --strategy ema_trend     # drawdown and streak odds
python -m growwbot odds RELIANCE --strategy ema_trend  # the odds on one specific planned trade
```

`backtest` and `montecarlo` judge a strategy over many trades. `odds` judges
the single trade in front of you ([trade-odds](../skills/trade-odds/SKILL.md)).

Outputs go to `state/backtests/` (trade list + equity curve CSVs).

## Data

Groww historical candles if credentials exist, else Yahoo Finance (daily: years;
5-minute: about 60 days). For long intraday tests, export candles from Groww and
pass `--csv-dir`.

## Judging a result

| metric | what to look for |
| --- | --- |
| trades | 30+ before trusting anything; 100+ is better |
| win_rate_pct vs breakeven_win_rate_pct | the one that matters. With `avg_win_r` 2.0 and `avg_loss_r` -1.0 you only need 33 % winners, so a 40 % win rate is a real edge and a 60 % win rate on tiny winners may not be |
| profit factor (after costs) | > 1.3 is interesting, > 2 on few trades is usually luck |
| max drawdown | within what you can sit through without quitting |
| out-of-sample vs in-sample | similar = robust; much worse = overfit |
| vs buy-and-hold | a risk-limited strategy often makes less in a bull market, with far smaller drawdowns. Decide what you want |
| costs | if charges eat most of the gross profit, the edge is too thin |

## Common traps

- **Overfitting:** trying many settings and keeping the best. Use `optimize`,
  which judges settings only on data they weren't chosen on.
- **Survivorship bias:** today's NIFTY 50 list contains yesterday's winners.
  Backtesting it over many years flatters every long strategy.
- **Too-good results:** a 90 % win rate or a smooth curve usually means a bug,
  look-ahead or unrealistic fills. Be suspicious.
- **Regime dependence:** a strategy tested only in 2023-24's bull market tells
  you little about a bear market.

For a full run of every strategy on 16 years of NSE data, and what it found,
see [Historical validation](14-historical-validation.md).

Live results are almost always worse than the backtest. Paper trade before
risking money ([Paper to live](09-paper-to-live.md)).
