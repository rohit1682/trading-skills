---
name: pivot-levels
description: >-
  Key price levels for the next session of an NSE stock or index: classic
  floor pivots (P, R1-R3, S1-S3), Central Pivot Range (CPR) with width read,
  Camarilla H3/H4/L3/L4, nearest swing support and resistance, and ATR. Use
  when the user asks "support and resistance", "pivot points", "CPR", "levels
  for tomorrow", "where to put my stop", "intraday levels".
---

# pivot-levels

Run from the repo root.

```bash
python -m growwbot levels RELIANCE
python -m growwbot levels NIFTY --json
```

Levels are computed from the last **completed** daily candle, so run it after
15:30 or before the next open.

## Reading them

- **CPR** (TC/P/BC): price opening above the CPR is a bullish bias, below is
  bearish. A narrow CPR (width under 0.25 %) often comes before a trending
  day; a wide one (over 0.6 %) before a range day.
- **Classic pivots**: R1/S1 are the first likely reaction zones; R2/S2 are
  stretched for most liquid stocks.
- **Camarilla**: H3/L3 are fade (mean-reversion) zones; a break of H4/L4 is a
  breakout signal for intraday traders.
- **Swing support/resistance**: actual turning points from the last 60 days;
  usually more meaningful than formula levels.
- **Stops**: put a stop beyond a level plus a buffer (about 0.25-0.5 ATR), not
  exactly on it, and size the trade with `risk-manager`.

Levels are reference points where other traders act, not walls. Say "likely
reaction zone", never "price will bounce here".
