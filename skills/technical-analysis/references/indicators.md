# Indicator reference (as implemented in `growwbot/indicators.py`)

All indicators use completed candles only. Wilder smoothing (RSI, ATR, ADX)
is seeded with a simple average, matching TradingView and StockCharts; the
test suite checks RSI against StockCharts' published example.

| Indicator | Settings | How the strategies use it |
| --- | --- | --- |
| EMA | 9, 21, 50, 200 | Trend direction and stack (9 > 21 > 50 > 200 is a clean uptrend). EMA 9/21 cross triggers `ema_trend`; EMA50 > EMA200 gates `macd_momentum`. |
| SMA 200 | 200 | Long-term trend filter for `rsi2_reversion` (only buy dips above it). |
| RSI | 14 (Wilder) | 50-70 = healthy momentum; > 70 stretched; < 30 oversold. `ema_trend` wants 50-70. |
| RSI(2) | 2 | Connors' short-term oversold gauge: < 10 is a deep dip; > 70 exit. |
| MACD | 12/26/9 | Line crossing above signal = momentum turning up. Histogram slope shows acceleration. |
| ADX / +DI / -DI | 14 | Trend strength, not direction. < 20 choppy (trend systems whipsaw), 20-40 trending. |
| Supertrend | ATR 10, x3 | Trailing volatility band; flip to UP triggers `supertrend_adx`, its line is the stop. |
| ATR | 14 (Wilder) | Volatility in rupees; stops are placed 2-2.5 ATR below entry for swing trades. |
| Bollinger Bands | 20, 2σ | Context: closes outside the bands are stretched; squeeze = low volatility before a move. |
| VWAP | session, resets daily | Intraday fair price. Longs only above VWAP (`vwap_pullback`, `orb`); a close back below it exits. |
| Donchian | 20 / 10 | 20-bar high breakout entry, 10-bar low exit (`donchian_breakout`). |
| Relative volume | volume / 20-bar avg | Confirms breakouts (≥ 1.2-1.5). |

## Market regime filter

With `regime_filter = true`, new longs are only allowed while NIFTY 50's
previous daily close is above its 50-day EMA. Long-only systems lose most of
their money in falling markets; this filter sits out the worst of them.

## Known limitations

- Indicators lag. Every one of these will give false signals in sideways markets.
- Gaps: a stock can open far below the stop (results, news). The backtest
  fills such gaps at the open, not at the stop, and so does the market.
- Circuit limits: a stock locked at its lower circuit cannot be sold. Avoid
  illiquid names and stocks in the F&O ban list or ASM/GSM surveillance.
