# 6. Strategies

All strategies are **long-only**, decide on a **completed candle** and act on
the **next** one, and return an entry, an exit signal, a stop and (optionally)
a target. Code: `growwbot/strategies.py`. A test proves none of them looks ahead.

None is a guaranteed winner. Trend strategies win big and lose often in
sideways markets; mean-reversion wins often and small, with occasional large
losses. Which works depends on the stocks and the market phase, so backtest
on your own list.

## Daily swing (CNC)

### `ema_trend`
- **Entry:** EMA 9 crosses above EMA 21, close above EMA 200, ADX ≥ 20, RSI(14) 50-70.
- **Stop / target:** 2 ATR below / 4 ATR above (2R).
- **Exit:** EMA 9 crosses back below EMA 21.
- **Best in:** steady uptrends. **Fails in:** choppy, range-bound markets (whipsaws).

### `supertrend_adx` (default)
- **Entry:** Supertrend(10, 3) flips up, ADX ≥ 20, close above EMA 50, volume ≥ 1.2x its 20-day average.
- **Stop:** the Supertrend line. **Target:** 2R.
- **Exit:** Supertrend flips down.
- **Best in:** trending large caps. **Fails in:** low-ADX ranges.

### `rsi2_reversion` (Larry Connors)
- **Entry:** close above the 200-day SMA and RSI(2) < 10 (a sharp dip in an uptrend).
- **Stop:** 2.5 ATR. **No target:** exits when close > 5-day SMA or RSI(2) > 70, or after 10 days.
- **Best in:** liquid index heavyweights in bull markets. **Fails in:** bear markets (dips keep dipping); the 200 SMA filter and regime filter are the defence.

### `macd_momentum`
- **Entry:** MACD line crosses above signal, close > EMA 50 > EMA 200, RSI > 50.
- **Stop / target:** 2 ATR / 4 ATR. **Exit:** MACD crosses back below signal.

### `donchian_breakout` (Turtle-style)
- **Entry:** close above the prior 20-day high, above EMA 50, volume ≥ 1.5x.
- **Stop:** 2 ATR. **No target:** exit at a close below the 10-day low (lets winners run).
- **Best in:** strong trending phases. Low win rate, large winners.

## Intraday (MIS, 5-minute)

Entries 09:30-14:30 only, exits by 15:10, never held overnight.

### `vwap_pullback`
- **Entry:** above VWAP, EMA 9 > EMA 21, the previous bar dipped to EMA 21 or VWAP, this bar closes bullish above EMA 9, RSI 45-65.
- **Stop:** below the last 3 bars' low or VWAP. **Target:** 2R. **Exit:** close back below VWAP.

### `orb` (opening-range breakout)
- **Range:** 09:15-09:30 high/low.
- **Entry:** first close above the range high before 11:00, above VWAP, relative volume ≥ 1.5. One per day.
- **Stop:** range midpoint. **Target:** 2R. **Exit:** close below VWAP.

Intraday costs matter more: a Rs 20 + Rs 20 brokerage on a Rs 10,000 trade is
0.4 % before taxes. Check `python -m growwbot costs` against your typical
target size.

## v2 versions (November 2026)

Rewrites of the strategies that lost money in the
[historical validation](14-historical-validation.md). The originals are
unchanged. Test results: [Strategy v2](15-strategy-v2.md). **None is proven
profitable**; see [doc 16](16-holdout-and-status.md) and `python -m growwbot strategies` for each one's test status.

| strategy | entry | stop / target | exit |
| --- | --- | --- | --- |
| `ema_trend_v2` | EMA 20 crosses above EMA 50, close > EMA 200, ADX ≥ 20 | 3 ATR / none | Chandelier (22-day high − 3 ATR) or close < EMA 200 |
| `macd_momentum_v2` | MACD crosses its signal **below zero**, close > EMA 50 > EMA 200 | 3 ATR / none | Chandelier or close < EMA 200 |
| `donchian_breakout_v2` | close above the prior 55-day high, above EMA 200 | 3 ATR(20) / none | close below the prior 20-day low |
| `rsi2_reversion_v2` | RSI(2) < 5, close > SMA 200, close ≥ 1.5 ATR below its 5-day high | 3 ATR / none | close > SMA 5, or 5 days |
| `vwap_pullback_v2` | as `vwap_pullback`, 09:45-13:30, once per stock per day | ≥ 1 ATR wide / 2R | stop, target or 15:10 (no VWAP exit) |
| `orb_v2` | first close above the 09:15-09:45 range before 11:30, above VWAP, RVOL ≥ 1.5 | range low / 2R | stop, target or 15:10 |

All strategies also pass the `max_cost_pct_of_risk` check: a trade whose
Groww charges would exceed 25 % of the rupees it risks is skipped.

## Market regime filter

With `regime_filter = true`, no new longs while NIFTY 50's previous close is
below its 50-day EMA. It costs some early-recovery trades and avoids most of
the damage in falling markets.

## Tuning

Override parameters in `config.toml`:

```toml
[strategy]
name = "ema_trend"
params = { adx_min = 25, stop_atr = 2.5 }
```

Only after `python -m growwbot optimize` shows the change helps **out of
sample** ([backtesting guide](08-backtesting.md)).

## Adding your own

See [Architecture](11-architecture.md#adding-a-strategy).
