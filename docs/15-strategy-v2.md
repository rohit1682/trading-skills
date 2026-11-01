# 15. Strategy v2: fixing the losers, then testing on stocks they never saw (November 2026)

[Doc 14](14-historical-validation.md) found that six of the seven strategies
lost money out of sample. This round tried to fix them, and then tested the
fixes on **30 randomly drawn stocks** the fixes were not designed on, over
2010-2020 and again over 2021-2026.

## Verdict

- **`donchian_breakout_v2` is the one real improvement, but it isn't proven.**
  It made money on all six test sets (+0.07 to +0.80 R a trade), yet every
  t-stat is under 2 (0.2 to 1.75), and on the watchlist at ₹50k it was flat.
- **`ema_trend_v2` and `macd_momentum_v2` are mixed.** Each beat v1 on some
  test sets and lost money on at least one.
- **`rsi2_reversion_v2` still loses money** at ₹50k on every test set.
  Mean reversion on delivery makes too little per trade to pay Groww's
  charges at this account size.
- **The intraday v2s (`vwap_pullback_v2`, `orb_v2`) still lose**, and so do
  v1 intraday strategies. Retire intraday trading at this capital.
- **Nothing came close to buying and holding.** The 30 random stocks
  returned +1,220 % from 2010 to 2020 and NIFTY returned +167 %. The best
  strategy made +16 % (₹50k) to +28 % (₹5 lakh). Even a working version of
  these rules, at 0.5 % risk a trade, is a low-return, low-drawdown overlay,
  not a way to beat the index.

**Bottom line for real money:** still no. The most promising candidate,
`donchian_breakout_v2`, would need about 130-480 out-of-sample trades
(depending on the test set) at its observed edge before it could be told
apart from luck; each test set gave it 70-130. Paper trade
it if you want to watch it, but don't fund it yet.

## Method (how this avoids fooling ourselves)

1. **Design set: the 15-stock watchlist, 2010-2020.** Each change was
   chosen from *why* v1 lost (charges, cut-short winners, churn), checked
   once on this set, then **frozen**. No parameter search, and no second
   round after seeing the test results.
2. **Test 1 (your ask): 30 random other stocks, 2010-2020.** Drawn with a
   fixed seed (`random:30:2026` in `scripts/compare_versions.py`) from 110
   NSE stocks with history before 2011, excluding the watchlist. The pool
   includes names that later fell out of the NIFTY or collapsed (RPOWER,
   SUZLON, YESBANK, RCOM, UNITECH and others), to reduce survivorship bias.
   Drawn: ADANIENT, APOLLOHOSP, ASIANPAINT, BAJAJFINSV, BAJFINANCE, BEL, BEML,
   COLPAL, CUMMINSIND, DABUR, GAIL, IGL, JINDALSTEL, JSWENERGY, MANAPPURAM,
   MARICO, MOTHERSON, NATIONALUM, NESTLEIND, NHPC, OIL, PAGEIND, PETRONET,
   RECLTD, RPOWER, SHRIRAMFIN, TATACOMM, TORNTPHARM, TVSMOTOR, VEDL.
3. **Test 2: 2021-2026**, years none of the designs saw, on the same 30
   stocks and on the watchlist.
4. Same simulator as doc 14: next-bar-open fills, Groww charges, 0.05 %
   slippage, all risk rules on, NIFTY regime filter on, strategy defaults.
   Capital ₹50,000 (your config) and ₹5,00,000.
5. Corporate-action glitches in the Yahoo data (ADANIENT 2015-06-03 +220 %,
   VEDL 2026-04-30 -63 %, MOTHERSON 2022-01-14 +35 %): checked, no trade in
   any reported strategy was open across them.

"Paper trading" here means the backtester replaying each day in order with
the same rules the live engine uses; it is not a live paper account.

## What changed

| v1 | why it lost (doc 14) | v2 change |
| --- | --- | --- |
| all | at ₹50k, delivery charges (₹20 DP + ₹5 minimum brokerage, plus GST) were often 30-60 % of the money at risk | new risk rule `max_cost_pct_of_risk = 25`: skip a trade whose round-trip charges exceed 25 % of the rupees it risks |
| `ema_trend` | 9/21 cross-back exit and a fixed 4 ATR target cut winners short; many short trades | `ema_trend_v2`: slower 20/50 cross, no target, Chandelier trailing exit (22-day high − 3 ATR) or close under the 200 EMA |
| `macd_momentum` | entered late in moves, exited on the first MACD wobble | `macd_momentum_v2`: only crosses from **below zero** (end of a pullback), no target, Chandelier exit |
| `donchian_breakout` | 20/10 channels traded twice as often for the same trends | `donchian_breakout_v2`: classic Turtle 55/20, above the 200 EMA, no volume filter, 3 ATR initial stop |
| `rsi2_reversion` | many tiny wins smaller than the charges | `rsi2_reversion_v2`: RSI(2) < 5 and only after a ≥ 1.5 ATR pullback, so the expected bounce is bigger; 5-bar time stop |
| `vwap_pullback` | the "close below VWAP" exit fired within a few bars on most trades | `vwap_pullback_v2`: no VWAP exit, stop at least 1 ATR wide, one entry per stock per day |
| `orb` | stop at mid-range, VWAP exit | `orb_v2`: 30-minute range, stop at the range low, 2R target, no VWAP exit |

The v1 strategies are unchanged and still available.

## Test 1: 30 random other stocks, 2010-2020

**₹50,000**

| strategy | trades | win % | break-even win % | expectancy (R) | t-stat | return % | max DD % | Sharpe | before costs % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ema_trend | 139 | 38.8 | 31.7 | 0.18 | 1.64 | 12.42 | -5.23 | 0.52 | 28.53 |
| ema_trend_v2 | 84 | 44.0 | 35.4 | 0.14 | 1.04 | 5.94 | -5.13 | 0.28 | 14.51 |
| macd_momentum | 420 | 26.9 | 35.5 | -0.16 | -3.43 | -27.40 | -28.80 | -0.97 | 9.30 |
| macd_momentum_v2 | 113 | 35.4 | 36.1 | -0.01 | -0.12 | -0.44 | -7.30 | -0.01 | 10.40 |
| donchian_breakout | 228 | 30.3 | 30.2 | 0.00 | 0.03 | 0.18 | -14.82 | 0.03 | 21.06 |
| donchian_breakout_v2 | 132 | 34.1 | 27.0 | 0.25 | 1.07 | 16.36 | -10.63 | 0.42 | 25.32 |
| rsi2_reversion | 608 | 46.4 | 63.8 | -0.12 | -6.12 | -30.14 | -32.79 | -1.62 | 34.00 |
| rsi2_reversion_v2 | 326 | 42.6 | 62.7 | -0.12 | -5.21 | -16.45 | -16.77 | -1.31 | 13.03 |
| supertrend_adx | 78 | 38.5 | 37.5 | 0.02 | 0.15 | 0.85 | -5.01 | 0.06 | 8.24 |

Buy-and-hold of the same stocks over the same window: 1220.26 % (max DD -42.97 %, Sharpe 1.31).

**₹5,00,000**

| strategy | trades | win % | break-even win % | expectancy (R) | t-stat | return % | max DD % | Sharpe | before costs % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ema_trend | 146 | 39.7 | 28.7 | 0.28 | 2.54 | 21.42 | -4.94 | 0.80 | 29.32 |
| ema_trend_v2 | 88 | 47.7 | 33.5 | 0.26 | 1.95 | 11.83 | -4.17 | 0.52 | 15.31 |
| macd_momentum | 449 | 31.2 | 31.2 | 0.00 | 0.01 | -1.24 | -14.98 | -0.02 | 17.69 |
| macd_momentum_v2 | 118 | 39.8 | 32.3 | 0.11 | 1.21 | 6.57 | -6.23 | 0.32 | 10.51 |
| donchian_breakout | 237 | 31.6 | 29.5 | 0.07 | 0.50 | 6.57 | -12.33 | 0.15 | 14.87 |
| donchian_breakout_v2 | 127 | 35.4 | 23.6 | 0.42 | 1.75 | 27.65 | -9.14 | 0.65 | 30.96 |
| rsi2_reversion | 691 | 63.2 | 60.4 | 0.02 | 0.94 | 6.43 | -5.29 | 0.28 | 36.46 |
| rsi2_reversion_v2 | 349 | 60.5 | 58.1 | 0.01 | 0.59 | 2.12 | -5.40 | 0.16 | 14.01 |
| supertrend_adx | 81 | 40.7 | 32.8 | 0.15 | 1.21 | 6.24 | -3.68 | 0.37 | 8.98 |

Buy-and-hold of the same stocks over the same window: 1220.26 % (max DD -42.97 %, Sharpe 1.31).

## Test 2a: the same 30 stocks, 2021 to Oct 2026

**₹50,000**

| strategy | trades | win % | break-even win % | expectancy (R) | t-stat | return % | max DD % | Sharpe | before costs % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ema_trend | 76 | 31.6 | 38.2 | -0.17 | -1.15 | -5.41 | -12.31 | -0.38 | 3.19 |
| ema_trend_v2 | 49 | 34.7 | 22.7 | 0.43 | 1.09 | 9.44 | -5.15 | 0.76 | 16.54 |
| macd_momentum | 249 | 30.1 | 33.1 | -0.07 | -1.14 | -7.54 | -13.37 | -0.39 | 25.47 |
| macd_momentum_v2 | 55 | 30.9 | 25.1 | 0.13 | 0.68 | 3.59 | -4.48 | 0.33 | 8.83 |
| donchian_breakout | 115 | 29.6 | 28.7 | 0.03 | 0.14 | 0.59 | -9.51 | 0.05 | 10.33 |
| donchian_breakout_v2 | 70 | 38.6 | 21.2 | 0.80 | 1.49 | 21.62 | -5.13 | 0.89 | 31.86 |
| rsi2_reversion | 330 | 39.7 | 65.4 | -0.18 | -6.49 | -24.01 | -24.13 | -2.00 | 9.32 |
| rsi2_reversion_v2 | 196 | 41.8 | 66.1 | -0.14 | -4.76 | -11.67 | -12.01 | -1.54 | 3.58 |
| supertrend_adx | 41 | 36.6 | 41.9 | -0.11 | -0.64 | -1.60 | -4.48 | -0.18 | 2.27 |

Buy-and-hold of the same stocks over the same window: 293.97 % (max DD -26.58 %, Sharpe 1.26).

**₹5,00,000**

| strategy | trades | win % | break-even win % | expectancy (R) | t-stat | return % | max DD % | Sharpe | before costs % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ema_trend | 83 | 34.9 | 34.5 | 0.01 | 0.07 | 0.15 | -9.93 | 0.02 | 4.81 |
| ema_trend_v2 | 54 | 37.0 | 18.8 | 0.65 | 1.69 | 17.16 | -5.72 | 1.01 | 18.94 |
| macd_momentum | 272 | 36.4 | 31.4 | 0.09 | 1.46 | 12.62 | -6.87 | 0.58 | 29.32 |
| macd_momentum_v2 | 64 | 31.2 | 24.5 | 0.14 | 0.81 | 4.58 | -4.79 | 0.37 | 6.56 |
| donchian_breakout | 113 | 32.7 | 23.1 | 0.37 | 1.49 | 21.78 | -8.26 | 0.65 | 10.78 |
| donchian_breakout_v2 | 75 | 37.3 | 20.3 | 0.65 | 1.40 | 24.21 | -6.93 | 0.90 | 34.14 |
| rsi2_reversion | 394 | 58.9 | 61.8 | -0.03 | -1.01 | -5.00 | -6.18 | -0.33 | 9.73 |
| rsi2_reversion_v2 | 228 | 59.6 | 62.8 | -0.02 | -0.84 | -2.60 | -4.65 | -0.28 | 3.70 |
| supertrend_adx | 43 | 37.2 | 34.2 | 0.06 | 0.37 | 1.27 | -4.31 | 0.14 | 2.35 |

Buy-and-hold of the same stocks over the same window: 293.97 % (max DD -26.58 %, Sharpe 1.26).

## Test 2b: the watchlist, 2021 to Oct 2026

**₹50,000**

| strategy | trades | win % | break-even win % | expectancy (R) | t-stat | return % | max DD % | Sharpe | before costs % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ema_trend | 30 | 30.0 | 41.1 | -0.26 | -1.18 | -3.69 | -4.57 | -0.39 | 0.46 |
| ema_trend_v2 | 36 | 30.6 | 38.8 | -0.12 | -0.87 | -2.25 | -3.43 | -0.27 | 1.31 |
| macd_momentum | 128 | 26.6 | 37.6 | -0.21 | -2.62 | -11.58 | -13.65 | -0.92 | 11.34 |
| macd_momentum_v2 | 40 | 32.5 | 39.4 | -0.10 | -0.66 | -1.61 | -5.54 | -0.23 | 4.28 |
| donchian_breakout | 94 | 37.2 | 38.9 | -0.04 | -0.28 | -1.56 | -8.59 | -0.06 | 6.03 |
| donchian_breakout_v2 | 68 | 32.4 | 29.0 | 0.07 | 0.23 | 2.14 | -6.13 | 0.12 | 11.16 |
| rsi2_reversion | 209 | 36.4 | 63.4 | -0.18 | -5.38 | -15.86 | -16.00 | -1.76 | 4.56 |
| rsi2_reversion_v2 | 113 | 35.4 | 60.9 | -0.14 | -3.85 | -6.60 | -7.14 | -1.20 | 4.53 |
| supertrend_adx | 19 | 47.4 | 32.8 | 0.32 | 1.12 | 2.35 | -1.61 | 0.38 | 6.10 |

Buy-and-hold of the same stocks over the same window: 110.12 % (max DD -14.73 %, Sharpe 1.02).

**₹5,00,000**

| strategy | trades | win % | break-even win % | expectancy (R) | t-stat | return % | max DD % | Sharpe | before costs % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ema_trend | 47 | 34.0 | 36.7 | -0.07 | -0.35 | -1.61 | -3.88 | -0.11 | 1.33 |
| ema_trend_v2 | 45 | 31.1 | 30.4 | 0.01 | 0.09 | 0.21 | -2.77 | 0.03 | 2.02 |
| macd_momentum | 179 | 34.1 | 32.7 | 0.03 | 0.34 | 2.33 | -9.14 | 0.15 | 13.55 |
| macd_momentum_v2 | 45 | 46.7 | 34.3 | 0.15 | 1.18 | 3.26 | -2.58 | 0.37 | 6.60 |
| donchian_breakout | 105 | 39.0 | 35.6 | 0.08 | 0.57 | 3.91 | -6.15 | 0.17 | 9.23 |
| donchian_breakout_v2 | 70 | 31.4 | 25.4 | 0.22 | 0.76 | 7.67 | -6.19 | 0.36 | 10.63 |
| rsi2_reversion | 283 | 55.1 | 62.6 | -0.06 | -1.85 | -7.86 | -10.67 | -0.65 | 6.69 |
| rsi2_reversion_v2 | 152 | 58.6 | 58.4 | -0.00 | -0.09 | -0.23 | -3.20 | -0.03 | 6.26 |
| supertrend_adx | 27 | 44.4 | 27.1 | 0.38 | 1.61 | 5.02 | -1.85 | 0.62 | 7.02 |

Buy-and-hold of the same stocks over the same window: 110.12 % (max DD -14.73 %, Sharpe 1.02).

### Reading these

- **`donchian_breakout_v2`** was positive on all 6 test tables
  (+0.07 to +0.80 R a trade), weakest on the watchlist at ₹50k (+0.07 R,
  t 0.2). Its gains come from a few very large winners
  (COLPAL +29 R in 2023-24, ADANIENT +13 R, TVSMOTOR +13 R), which is
  normal for trend following and is also why the t-stats stay low: miss
  two of those trades and the result is flat.
- **`ema_trend_v2`** beat v1 in 2021-2026 but lost to v1 on the random
  2010-2020 stocks. Mixed: no clear improvement.
- **`macd_momentum_v2`** removed most of v1's losses at ₹50k (v1 lost
  27 % on the random stocks, v2 broke even), but it isn't clearly
  profitable, and at ₹5 lakh in 2021-2026 v1 actually did better.
- **`rsi2_reversion_v2`** lost less than v1 but still lost at ₹50k on every
  test set (t -3.9 to -5.2). At ₹5 lakh it is break-even.
- **`supertrend_adx`** (unchanged) was near zero on the random stocks in
  2010-2020 and mixed in 2021-2026 (negative on the random stocks, positive
  on the watchlist), on 19-81 trades.

## Intraday v2

Yahoo keeps only ~60 days of 5-minute bars, so intraday can't be tested on
2010-2020. Design set: 5-minute bars Aug-Sep 2026 and 60-minute bars
Nov 2023-Dec 2025. Test set: 5-minute October 2026 (regime filter off, or
there would be no trades) and 60-minute Dec 2025-Oct 2026.

**Test, 60-minute bars, ₹50,000**

| strategy | trades | win % | break-even win % | expectancy (R) | t-stat | return % | max DD % | Sharpe | before costs % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| vwap_pullback | 77 | 15.6 | 63.8 | -0.33 | -8.44 | -5.75 | -5.79 | -5.10 | -1.87 |
| vwap_pullback_v2 | 64 | 17.2 | 64.9 | -0.36 | -6.57 | -5.14 | -5.18 | -4.53 | -2.13 |
| orb | 20 | 45.0 | 45.6 | -0.01 | -0.05 | 0.31 | -0.46 | 0.41 | 1.04 |
| orb_v2 | 46 | 32.6 | 61.6 | -0.22 | -3.14 | -2.67 | -2.72 | -2.20 | -0.06 |

Buy-and-hold of the same stocks over the same window: -11.26 % (max DD -16.27 %, Sharpe -0.94).

**Test, 60-minute bars, ₹5,00,000**

| strategy | trades | win % | break-even win % | expectancy (R) | t-stat | return % | max DD % | Sharpe | before costs % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| vwap_pullback | 249 | 21.3 | 51.3 | -0.30 | -8.73 | -10.56 | -10.56 | -6.64 | -2.28 |
| vwap_pullback_v2 | 224 | 28.1 | 58.3 | -0.28 | -7.35 | -9.90 | -9.93 | -5.72 | -2.46 |
| orb | 44 | 31.8 | 46.4 | -0.18 | -1.73 | -0.25 | -1.00 | -0.21 | 1.33 |
| orb_v2 | 76 | 35.5 | 58.4 | -0.20 | -3.47 | -2.56 | -2.99 | -1.95 | 0.03 |

Buy-and-hold of the same stocks over the same window: -11.26 % (max DD -16.27 %, Sharpe -0.94).

**Test, 5-minute bars, October 2026, ₹50,000** (the new cost rule blocks
most 5-minute trades at this size: their stops are too tight for the fees)

| strategy | trades | win % | break-even win % | expectancy (R) | t-stat | return % | max DD % | Sharpe | before costs % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| vwap_pullback | 5 | 0.0 | 100.0 | -0.70 | -8.05 | -0.81 | -0.81 | -7.79 | 1.41 |
| vwap_pullback_v2 | 3 | 33.3 | 96.5 | -0.72 | -1.87 | -0.54 | -0.55 | -5.30 | 0.54 |
| orb | 17 | 17.6 | 37.0 | -0.31 | -1.77 | -1.41 | -1.75 | -6.69 | -0.59 |
| orb_v2 | 39 | 35.9 | 61.8 | -0.26 | -2.56 | -2.38 | -2.86 | -6.41 | 1.01 |

Buy-and-hold of the same stocks over the same window: 2.76 % (max DD -2.07 %, Sharpe 2.66).

Both intraday strategies lose in both versions after charges; before
charges they are within about 2 % of zero, so there is no edge for the
charges to eat.

## The new cost rule on its own

Design set (watchlist 2010-2020, ₹50k), with and without
`max_cost_pct_of_risk`:

| strategy | return % with the rule | without |
| --- | ---: | ---: |
| ema_trend | 1.25 | 3.98 |
| ema_trend_v2 | 2.76 | 3.14 |
| macd_momentum | -27.57 | -32.38 |
| macd_momentum_v2 | 2.59 | 7.23 |
| donchian_breakout | -6.83 | 4.91 |
| donchian_breakout_v2 | -2.25 | -0.83 |
| rsi2_reversion | -30.47 | -38.00 |
| rsi2_reversion_v2 | -15.64 | -16.85 |
| supertrend_adx | 2.96 | 3.16 |

It cut the losses of the high-turnover losers (`macd_momentum`,
`rsi2_reversion`) but also removed some winning trades from `ema_trend` and
`donchian_breakout`. It is kept on by default because its purpose is
protection: a trade whose fees eat a quarter of its risk needs an unusually
large edge just to break even. Set it to 0 to turn it off.

## What would make one of these fundable

Same bar as doc 14: at least 100 out-of-sample trades with expectancy whose
95 % interval is above zero after costs, on two different baskets, then a few
months of live paper trading that matches. At `donchian_breakout_v2`'s pace
(about 12 trades a year on 30 stocks) that is years of data, so the
realistic next step is to widen the universe (e.g. NIFTY 200) for more
trades, not to keep adjusting the rules.

## Re-running

```bash
python scripts/fetch_data.py            # watchlist, NIFTY 50, intraday -> data/validation/
# (the 84-stock pool was fetched the same way; symbols are listed in scripts/fetch_data.py)
python scripts/compare_versions.py --data-dir data/validation --universe random:30:2026 \
    --window 2010-01-01:2021-01-01 --capital 50000 \
    --strategies ema_trend,ema_trend_v2,donchian_breakout,donchian_breakout_v2
python -m growwbot backtest --strategy donchian_breakout_v2 --split 0.7
```

Raw results (JSON) are in `docs/validation-results/`.

*Not investment advice. Past results, good or bad, don't predict future ones.*
