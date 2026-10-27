# 12. FAQ and troubleshooting

**Will this make me money?**
Maybe not. It enforces discipline and tests ideas honestly; it can't create an
edge the market doesn't offer. Most retail intraday traders lose money (SEBI,
FY23: about 7 in 10). Start on paper and small.

**`pip install` fails building `clint` or `args`.**
Use Python 3.11 or 3.12 for the virtual environment.

**`ZoneInfoNotFoundError: Asia/Kolkata` on Windows.**
`pip install tzdata` (it's in requirements.txt for Windows).

**`groww login: FAILED`.**
Check `GROWW_API_KEY` and `GROWW_TOTP_SECRET` (no quotes or spaces), that the
PC clock is correct (TOTP codes depend on time), and that your Trade API
subscription is active. Key+secret users must approve the key in the app each day.

**Orders rejected.**
Read `state/orders.log` for the message. Common causes: insufficient margin,
stock in the F&O ban list or under surveillance, price outside the circuit
band, MIS not allowed on that stock, static IP not registered.

**"No entry signals."**
Normal. Good strategies are selective. Don't loosen rules to get trades.

**Backtest says 0 trades.**
Too little history for the indicators (need ~200 daily bars for EMA 200), the
regime filter blocking everything (try `--no-regime` to see), or the
risk-per-trade too small for the price (size rounds to 0).

**Can it short, trade F&O or options?**
No. Long-only cash equities by design. Shorting and F&O need different risk
handling; add them only with care.

**Will the bot touch shares I bought myself?**
No. It only manages positions recorded in `state/positions_*.json`.
`portfolio` reads your holdings but never trades them.

**What if my PC switches off with a live position?**
The SL-M stop at Groww still protects it for the day. Intraday positions are
squared off by Groww near the close (with a fee). Swing positions have no
broker stop from the next day until the engine runs again; place a GTT stop
in the Groww app if you'll be away.

**Data from Yahoo vs Groww differ.**
Yahoo can be delayed and occasionally wrong. Use Groww data for anything that
matters; Yahoo is only a fallback.

**How do I update the NIFTY 50 list?**
Edit `universes/nifty50.txt` after each index rebalance (March and September).

**Taxes?**
Intraday profits are speculative business income; delivery trades are short-
or long-term capital gains. Keep the journal and Groww's tax P&L; ask a tax professional.
