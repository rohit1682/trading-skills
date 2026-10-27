---
name: market-regime
description: >-
  Read the Indian market's regime before trading: NIFTY 50 trend (EMA 50/200,
  ADX), breadth across NIFTY 50 stocks (% above 50/200 EMA, new 20-day highs
  vs lows) and India VIX, scored 0-100 into RISK-ON, CAUTIOUS or DEFENSIVE
  with a suggested risk multiplier. Use when the user asks "how is the market",
  "should I trade today", "is it a bull or bear market", "market mood",
  "exposure", or at the start of a trading day.
---

# market-regime

Run from the repo root (`cd "$GROWWBOT_HOME"` if the skill is installed elsewhere).

```bash
python -m growwbot regime                       # NIFTY 50 universe
python -m growwbot regime --universe banknifty  # any file in universes/
python -m growwbot regime --json
```

## Scoring (100 max)

| points | condition |
| --- | --- |
| 20 | NIFTY above its 50-day EMA |
| 20 | 50 EMA above 200 EMA |
| 20 | at least half the universe above its 50 EMA |
| 15 | at least half above its 200 EMA |
| 15 | India VIX under 16 (8 points if VIX data is missing) |
| 10 | ADX ≥ 20 with +DI above -DI |

70+ = RISK-ON (normal size), 40-69 = CAUTIOUS (half risk, fewer positions),
under 40 = DEFENSIVE (no new swing longs).

## Report

Lead with the posture and score, then the 2-3 reasons that moved it most,
then what it means for today: the suggested risk multiplier and whether the
bot's `regime_filter` (NIFTY vs its 50 EMA) currently allows new longs.
Mention new highs vs new lows as a breadth read. Don't forecast where the
market goes next; the regime describes the present.
