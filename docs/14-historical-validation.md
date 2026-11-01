# 14. Historical validation (November 2026)

Every strategy in `growwbot/strategies.py` run against real NSE history with
default parameters, a time split, Groww's charges and slippage, and every risk
rule from `config.example.toml`. Nothing was tuned. The script is
[`scripts/validate_strategies.py`](../scripts/validate_strategies.py); the data
came from [`scripts/fetch_data.py`](../scripts/fetch_data.py) (Yahoo Finance,
downloaded 1 Nov 2026).

> Follow-up: [doc 15](15-strategy-v2.md) rewrote the losing strategies and
> tested them on 30 random other stocks. The numbers below were produced
> before the `max_cost_pct_of_risk` risk rule existed; pass `--no-cost-gate`
> to `validate_strategies.py` to reproduce them.

## Verdict

**None of the seven strategies has a demonstrated edge.** Out of sample, after
costs, not one of them made money on both baskets, and none got anywhere near
buying and holding the same stocks or the NIFTY index.

| strategy | out-of-sample verdict |
| --- | --- |
| `rsi2_reversion` | **Loses money, decisively** (t ≈ -7 to -9). Charges are larger than its average win at ₹50k. |
| `macd_momentum` | **Loses money** (t ≈ -2.3 on both baskets). |
| `donchian_breakout` | **Loses money** OOS (t -1.3 on the watchlist, -2.9 on the NIFTY 50). |
| `ema_trend` | **Loses money** OOS at ₹50k (-0.25 to -0.31 R a trade), not statistically certain. |
| `supertrend_adx` | **Unproven.** The only one positive on the watchlist in every run (+0.14 to +0.37 R a trade), but on 18-33 trades, and it turned **negative** on the NIFTY 50 (-0.10 R). Too few trades to tell from luck. |
| `vwap_pullback` (intraday) | **Loses money, decisively**, on 5, 15 and 60-minute bars, even **before** charges. |
| `orb` (intraday) | **Loses money, decisively**, on all three bar sizes. |

What you *can* trust from this run:

- **The backtester is honest.** A look-ahead probe (signals recomputed on
  truncated history must match the full-history signals bar for bar) found
  **0 mismatches** for every strategy. Fills are next-bar-open, stop-first,
  gap-through-stop at the open. The code review below found no look-ahead.
- **The risk layer limits each loss, not the total.** Each trade risks 0.5 %,
  so bad weeks stay small, but a rule that loses a little on every trade still
  compounds: `rsi2_reversion` lost 55 % (watchlist) and 88 % (NIFTY 50) of the
  account over 2010-2026. Risk rules can't make a losing rule win.
- **Costs matter more than the indicator.** At ₹50k capital the average
  delivery round trip costs ₹43-51 (₹20 DP charge + GST on every sell, ₹5
  minimum brokerage), roughly 0.5-0.9 % of a typical position. That alone turns
  `rsi2_reversion` from a 51 % win rate (at ₹5 lakh) into a 31 % win rate.

## Setup

| item | value |
| --- | --- |
| Daily data | Yahoo daily bars from 2005 (indicators warm up), **trading from 2010-01-04 to 2026-10-30** |
| Split | first 70 % of bars in-sample (IS, 2010-01-04 to 2021-10-14), last 30 % out-of-sample (OOS, 2021-10-14 to 2026-10-30) |
| Baskets | the 15-stock `watchlist` in `config.example.toml`; the current NIFTY 50 (`universes/nifty50.txt`) as a second, larger basket |
| Intraday data | 5 and 15-minute bars 2026-08-06 to 2026-10-30 (all Yahoo keeps); 60-minute bars 2023-11-17 to 2026-10-30 |
| Capital | ₹50,000 (the config default); daily strategies re-run at ₹5,00,000 to show the cost effect |
| Costs | `growwbot/costs.py` (Groww brokerage 0.1 % capped ₹5-20, STT, stamp, exchange, SEBI, IPFT, GST, ₹20 DP charge) + 0.05 % slippage per side |
| Risk | `growwbot/risk.py` defaults: 0.5 % risk a trade, max 20 % a position, 3 open positions, 2 % daily loss, 4 trades a day, NIFTY-above-50-EMA regime filter on (also re-run with it off) |
| Parameters | strategy defaults, untouched |

**How to read the tables.** *Expectancy (R)* is the average net result per
trade in units of the money risked at entry. *t-stat* is that average divided by
its standard error; below 2 means "could easily be luck". *95 % CI* is a
bootstrap interval for the expectancy: if it straddles 0, the sign isn't known.
*Return before costs* is the same run with zero charges and zero slippage.
*Buy-and-hold* is an equal-weight basket of the same stocks bought at the first
open of the window, dividends included, no charges; it is flattered by
survivorship (see below), so also compare with NIFTY: **+247 % IS, +25.7 % OOS
(price only, Sharpe 0.71 / 0.40)**.

## Daily strategies: watchlist, ₹50k, regime filter on

| strategy | window | trades | win % | break-even win % | expectancy (R) | t-stat | 95% CI (R) | profit factor | return % | max DD % | Sharpe | return before costs % | buy-and-hold % (Sharpe) |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| ema_trend | IS | 101 | 38.6 | 34.8 | 0.09 | 0.73 | -0.15 to +0.35 | 1.17 | 4.21 | -5.70 | 0.19 | 15.95 | 754.77 (1.18) |
| ema_trend | OOS | 39 | 28.2 | 39.9 | -0.31 | -1.49 | -0.71 to +0.10 | 0.60 | -5.03 | -5.94 | -0.50 | 0.36 | 54.36 (0.73) |
| supertrend_adx | IS | 53 | 43.4 | 36.2 | 0.12 | 0.70 | -0.20 to +0.47 | 1.30 | 3.46 | -3.95 | 0.25 | 7.38 | 754.77 (1.18) |
| supertrend_adx | OOS | 18 | 38.9 | 32.2 | 0.16 | 0.54 | -0.39 to +0.72 | 1.32 | 1.07 | -1.63 | 0.21 | 4.94 | 54.36 (0.73) |
| rsi2_reversion | IS | 553 | 35.4 | 63.9 | -0.20 | -9.33 | -0.25 to -0.16 | 0.30 | -39.88 | -40.21 | -2.06 | 17.20 | 754.77 (1.18) |
| rsi2_reversion | OOS | 203 | 31.0 | 65.4 | -0.27 | -6.85 | -0.34 to -0.19 | 0.24 | -20.53 | -20.58 | -2.38 | -0.13 | 54.36 (0.73) |
| macd_momentum | IS | 415 | 28.4 | 38.8 | -0.19 | -3.94 | -0.28 to -0.09 | 0.58 | -32.96 | -36.31 | -1.15 | 13.95 | 754.77 (1.18) |
| macd_momentum | OOS | 138 | 27.5 | 37.6 | -0.20 | -2.33 | -0.37 to -0.04 | 0.62 | -11.66 | -12.88 | -0.97 | 4.91 | 54.36 (0.73) |
| donchian_breakout | IS | 218 | 35.3 | 32.7 | 0.08 | 0.56 | -0.19 to +0.38 | 1.07 | 5.01 | -13.68 | 0.12 | 34.31 | 754.77 (1.18) |
| donchian_breakout | OOS | 86 | 31.4 | 39.1 | -0.20 | -1.27 | -0.51 to +0.12 | 0.72 | -7.08 | -7.76 | -0.36 | 1.67 | 54.36 (0.73) |

Every strategy that looked positive in-sample (`ema_trend`, `supertrend_adx`,
`donchian_breakout`) got worse out of sample, and only `supertrend_adx` stayed
above zero. Note the gap between *return before costs* and *return*: for
`rsi2_reversion` and `macd_momentum`, the rules made a small gross profit
in-sample and charges turned it into a 33-40 % loss.

### Same thing on the NIFTY 50 (50 stocks), OOS only

| strategy | window | trades | win % | break-even win % | expectancy (R) | t-stat | 95% CI (R) | profit factor | return % | max DD % | Sharpe | return before costs % | buy-and-hold % (Sharpe) |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| ema_trend | OOS | 84 | 27.4 | 36.9 | -0.25 | -1.85 | -0.51 to +0.02 | 0.66 | -8.51 | -8.67 | -0.65 | 0.63 | 80.92 (0.89) |
| supertrend_adx | OOS | 48 | 35.4 | 40.7 | -0.10 | -0.65 | -0.40 to +0.21 | 0.83 | -1.58 | -2.27 | -0.19 | 2.65 | 80.92 (0.89) |
| rsi2_reversion | OOS | 401 | 35.4 | 65.2 | -0.23 | -8.20 | -0.29 to -0.18 | 0.30 | -32.14 | -32.19 | -2.72 | 7.79 | 80.92 (0.89) |
| macd_momentum | OOS | 237 | 28.3 | 36.4 | -0.16 | -2.34 | -0.28 to -0.02 | 0.68 | -15.89 | -16.08 | -0.96 | 7.42 | 80.92 (0.89) |
| donchian_breakout | OOS | 124 | 25.8 | 39.1 | -0.35 | -2.86 | -0.58 to -0.10 | 0.51 | -17.99 | -17.99 | -0.94 | -6.35 | 80.92 (0.89) |

With more stocks there are more trades, and the result is clearer: all five are
negative out of sample, including `supertrend_adx`.

### Watchlist at ₹5,00,000, OOS only

| strategy | window | trades | win % | break-even win % | expectancy (R) | t-stat | 95% CI (R) | profit factor | return % | max DD % | Sharpe | return before costs % | buy-and-hold % (Sharpe) |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| ema_trend | OOS | 42 | 33.3 | 36.2 | -0.07 | -0.36 | -0.47 to +0.35 | 0.88 | -1.60 | -3.88 | -0.13 | 1.26 | 54.36 (0.73) |
| supertrend_adx | OOS | 23 | 43.5 | 27.2 | 0.37 | 1.42 | -0.12 to +0.89 | 2.02 | 4.15 | -1.86 | 0.60 | 6.00 | 54.36 (0.73) |
| rsi2_reversion | OOS | 220 | 51.4 | 63.9 | -0.10 | -2.82 | -0.17 to -0.03 | 0.58 | -10.79 | -10.97 | -1.09 | 0.37 | 54.36 (0.73) |
| macd_momentum | OOS | 147 | 29.9 | 31.4 | -0.03 | -0.33 | -0.20 to +0.14 | 0.95 | -1.70 | -9.37 | -0.11 | 7.01 | 54.36 (0.73) |
| donchian_breakout | OOS | 85 | 35.3 | 32.9 | 0.06 | 0.38 | -0.26 to +0.39 | 1.10 | 2.27 | -6.16 | 0.13 | 5.48 | 54.36 (0.73) |

More capital means charges are a smaller share of each trade, so every strategy
improves. Still, only `supertrend_adx` (23 trades, t 1.4) and `donchian_breakout`
(t 0.4) end up positive, and neither is statistically distinguishable from zero.

### Watchlist, ₹50k, regime filter off, OOS only

| strategy | window | trades | win % | break-even win % | expectancy (R) | t-stat | 95% CI (R) | profit factor | return % | max DD % | Sharpe | return before costs % | buy-and-hold % (Sharpe) |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| ema_trend | OOS | 57 | 28.1 | 39.1 | -0.29 | -1.74 | -0.61 to +0.04 | 0.59 | -7.04 | -9.05 | -0.68 | -0.70 | 54.36 (0.73) |
| supertrend_adx | OOS | 33 | 42.4 | 36.3 | 0.14 | 0.61 | -0.27 to +0.57 | 1.45 | 2.66 | -2.74 | 0.40 | 5.69 | 54.36 (0.73) |
| rsi2_reversion | OOS | 325 | 30.5 | 66.2 | -0.29 | -9.32 | -0.36 to -0.23 | 0.23 | -32.86 | -32.92 | -3.01 | -3.65 | 54.36 (0.73) |
| macd_momentum | OOS | 187 | 26.7 | 36.7 | -0.21 | -2.73 | -0.36 to -0.06 | 0.64 | -15.80 | -16.47 | -1.15 | 5.57 | 54.36 (0.73) |
| donchian_breakout | OOS | 114 | 24.6 | 36.5 | -0.33 | -2.40 | -0.59 to -0.05 | 0.61 | -13.59 | -13.63 | -0.67 | -3.39 | 54.36 (0.73) |

Turning the NIFTY regime filter off adds trades and makes `rsi2_reversion`,
`macd_momentum` and `donchian_breakout` clearly worse; the other two barely
change. Keep it on.

## Intraday strategies

The intraday samples are short: Yahoo keeps only ~60 days of 5/15-minute bars,
so the OOS window is 18 trading days. The regime filter blocked **every**
intraday entry in that window (NIFTY was below its 50-day EMA), so these runs
have it **off**; with it on, both strategies took 0 OOS trades. The Sharpe
figures over such short windows are not meaningful; look at expectancy and
the t-stat.

**5-minute (as designed), regime off**

| strategy | window | trades | win % | break-even win % | expectancy (R) | t-stat | 95% CI (R) | profit factor | return % | max DD % | Sharpe | return before costs % | buy-and-hold % (Sharpe) |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| vwap_pullback | full | 226 | 15.5 | 61.7 | -1.06 | -15.93 | -1.19 to -0.93 | 0.15 | -13.81 | -13.81 | -22.80 | -0.28 | -4.86 (-1.85) |
| vwap_pullback | OOS | 69 | 21.7 | 52.7 | -0.68 | -5.55 | -0.91 to -0.44 | 0.33 | -3.14 | -3.17 | -12.92 | 1.64 | 2.78 (2.67) |
| orb | full | 121 | 14.0 | 45.8 | -0.63 | -8.34 | -0.77 to -0.48 | 0.22 | -9.13 | -9.14 | -13.12 | -1.59 | -4.86 (-1.85) |
| orb | OOS | 47 | 17.0 | 45.5 | -0.58 | -4.45 | -0.82 to -0.32 | 0.26 | -3.75 | -3.97 | -13.29 | -0.79 | 2.78 (2.67) |

**15-minute, regime off**

| strategy | window | trades | win % | break-even win % | expectancy (R) | t-stat | 95% CI (R) | profit factor | return % | max DD % | Sharpe | return before costs % | buy-and-hold % (Sharpe) |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| vwap_pullback | full | 214 | 15.4 | 56.5 | -0.73 | -13.10 | -0.83 to -0.62 | 0.17 | -14.36 | -14.36 | -21.06 | -2.10 | -4.86 (-1.85) |
| vwap_pullback | OOS | 69 | 21.7 | 53.6 | -0.51 | -5.17 | -0.69 to -0.31 | 0.32 | -3.80 | -4.03 | -12.79 | 0.16 | 2.77 (2.67) |
| orb | full | 101 | 17.8 | 51.6 | -0.66 | -7.41 | -0.83 to -0.48 | 0.23 | -7.81 | -8.11 | -12.78 | -0.83 | -4.86 (-1.85) |
| orb | OOS | 36 | 27.8 | 48.0 | -0.40 | -2.39 | -0.70 to -0.06 | 0.47 | -1.89 | -2.19 | -7.60 | 0.67 | 2.77 (2.67) |

**60-minute, ~3 years, regime on** (a different strategy in practice: the
"opening range" becomes the first hour)

| strategy | window | trades | win % | break-even win % | expectancy (R) | t-stat | 95% CI (R) | profit factor | return % | max DD % | Sharpe | return before costs % | buy-and-hold % (Sharpe) |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| vwap_pullback | IS | 1068 | 15.4 | 57.1 | -0.56 | -27.84 | -0.60 to -0.52 | 0.17 | -53.36 | -53.36 | -12.64 | -5.25 | 32.38 (1.24) |
| vwap_pullback | OOS | 246 | 12.6 | 59.4 | -0.57 | -15.11 | -0.64 to -0.49 | 0.13 | -16.43 | -16.43 | -8.95 | -1.87 | -11.26 (-0.94) |
| orb | IS | 218 | 23.4 | 52.7 | -0.37 | -8.05 | -0.46 to -0.28 | 0.26 | -13.29 | -13.29 | -4.75 | -0.04 | 32.38 (1.24) |
| orb | OOS | 40 | 30.0 | 57.3 | -0.37 | -3.08 | -0.59 to -0.14 | 0.53 | -1.65 | -1.78 | -1.63 | 1.04 | -11.26 (-0.94) |

On every bar size, both intraday strategies are roughly break-even or losing
before charges (full-period gross -0.04 % to -5 %), and charges then add a
large loss on top. `vwap_pullback` exits on the first close
below VWAP, which happens within a few bars on most trades (163 of 226 exits at
5 minutes), so it pays two sets of charges to capture a few rupees. These are
the clearest "do not trade" results in the report.

## Monte Carlo (OOS trades, reshuffled 5,000 times, 0.5 % risk a trade)

Watchlist, ₹50k:

| strategy | OOS trades | median return % | 5th–95th pct return % | median max DD % | 95th pct worst DD % | P(losing money) | losing streak median / p95 |
|---|---:|---:|---|---:|---:|---:|---|
| ema_trend | 39 | -6.09 | -11.97 to 0.7 | -7.61 | -12.57 | 93.1% | 8 / 15 |
| supertrend_adx | 18 | 1.34 | -2.67 to 6.11 | -1.88 | -3.9 | 30.4% | 4 / 9 |
| rsi2_reversion | 203 | -23.61 | -28.48 to -18.59 | -23.82 | -28.58 | 100.0% | 11 / 17 |
| macd_momentum | 138 | -13.19 | -21.18 to -4.2 | -14.8 | -22.21 | 99.0% | 12 / 19 |
| donchian_breakout | 86 | -8.98 | -18.02 to 2.47 | -11.89 | -19.38 | 90.6% | 9 / 16 |

NIFTY 50, ₹50k:

| strategy | OOS trades | median return % | 5th–95th pct return % | median max DD % | 95th pct worst DD % | P(losing money) | losing streak median / p95 |
|---|---:|---:|---|---:|---:|---:|---|
| ema_trend | 84 | -10.34 | -18.31 to -1.41 | -12.22 | -19.26 | 96.9% | 10 / 18 |
| supertrend_adx | 48 | -2.54 | -8.03 to 3.62 | -4.79 | -8.9 | 75.4% | 7 / 12 |
| rsi2_reversion | 401 | -37.32 | -43.1 to -31.24 | -37.51 | -43.22 | 100.0% | 11 / 17 |
| macd_momentum | 237 | -17.18 | -26.91 to -5.61 | -19.22 | -27.95 | 99.1% | 13 / 21 |
| donchian_breakout | 124 | -19.75 | -28.74 to -8.79 | -21.22 | -29.44 | 99.7% | 12 / 21 |

## Code review: look-ahead and other biases

Checked in `growwbot/backtest.py`, `strategies.py`, `indicators.py`, `data.py`, `risk.py`:

- **No look-ahead found.** Indicators are causal (EMA/Wilder smoothing, rolling
  windows; Donchian and relative volume use `.shift(1)`); signals are read on a
  closed bar and filled at the next open; the regime filter uses the *previous*
  NIFTY close; the opening range only uses bars before the entry window. The
  probe in `validate_strategies.py` confirms it empirically for all seven.
- **Survivorship bias (real, and it flatters these results).** Both baskets are
  *today's* large caps, tested back to 2010. Stocks that fell out of the index
  are missing. This inflates buy-and-hold most (+755 % IS for the watchlist vs
  +247 % for NIFTY), and it flatters long-only strategies too. A losing result
  on a survivor basket is, if anything, too kind.
- **Target fills get no slippage** (`close_pos(sym, p.target, ...)`), while
  stops do. Slightly optimistic; small next to the losses above.
- **Missing regime days default to "allowed"** (`regime.get(ts.date(), True)`).
  Harmless here (NIFTY data covers the whole test), but it would silently
  disable the filter if NIFTY data were missing.
- **Intraday end-of-day detection** uses knowledge of which bar is the day's
  last. It only prevents new entries on that bar and squares off there, so it
  doesn't help the results.
- **`optimize` (walk-forward) turns the regime filter off** while `backtest`
  defaults it on, so the two commands aren't comparable. Not used here.
- **Data quirks.** Yahoo's 09:15 5-minute bar often has zero volume, which
  delays VWAP by one bar. Yahoo prices are split-adjusted, not
  dividend-adjusted, for the strategies (the buy-and-hold uses the
  dividend-adjusted close). NIFTYBEES has bad bars around 2019-12-19, so it
  wasn't used as a benchmark. In the NIFTY 50 basket, TMPV (Tata Motors
  demerger, 2025-10-14) and TRENT (2026-01-01) show one-day gaps of -39 % and
  -33 % that a trade would see as stop-outs.

## How many trades before risking money

An edge is only believable when the average R is about two standard errors
above zero. Per-trade results here have a spread of roughly 1.0-1.3 R, so:

| true edge per trade | trades needed (t ≈ 2) |
| --- | --- |
| +0.10 R | ~400-700 |
| +0.20 R | ~100-170 |
| +0.30 R | ~45-75 |

`supertrend_adx` at ₹5 lakh (+0.37 R) would need about 46 OOS trades at that
rate; it had 23, and the NIFTY 50 run says the rate itself doesn't hold up.
Practical rule: **at least 100 out-of-sample trades, a positive OOS
expectancy after costs with a 95 % interval above zero, and a similar result on
a second basket**, then a few months of paper trading that agree with the
backtest, before any real money. None of the seven meets the first condition
today.

## What a backtest can't tell you

Even a strategy that passed all of the above would still face partial fills,
circuit locks, API outages, Groww's daily key approval, and you overriding the
bot. The live order path has so far been tested only against a mock Groww API.
A backtest can rule a strategy *out*; it can't make one 100 % (let alone 200 %)
safe.

## Re-running it

```bash
python scripts/fetch_data.py                       # needs Yahoo access; writes data/validation/
python scripts/validate_strategies.py --no-cost-gate --data-dir data/validation --universe watchlist --strategies ema_trend,supertrend_adx,rsi2_reversion,macd_momentum,donchian_breakout --json out.json
python scripts/validate_strategies.py --data-dir data/validation --universe nifty50 --capital 500000 --strategies supertrend_adx
python scripts/validate_strategies.py --data-dir data/validation --strategies vwap_pullback,orb --no-regime
python scripts/validate_strategies.py --data-dir data/validation --strategies vwap_pullback,orb --interval 1hour
```

Each run prints one OOS line per strategy and writes the full JSON (IS, OOS,
full period, Monte Carlo, look-ahead probe, exit reasons, risk blocks).

*Not investment advice. Past results, good or bad, don't predict future ones.*
