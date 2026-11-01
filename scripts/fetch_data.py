"""Download NSE candles from Yahoo Finance for the strategy validation.

Run from the repo root:  python scripts/fetch_data.py
Writes CSVs to data/validation/ (git-ignored) plus data/validation-data.zip.
Needs only: pip install yfinance pandas
"""
import sys, time, zipfile
from pathlib import Path
import pandas as pd
import yfinance as yf

OUT = Path(__file__).resolve().parent.parent / "data" / "validation"
OUT.mkdir(parents=True, exist_ok=True)
WATCH = ["RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS", "SBIN", "AXISBANK", "LT", "ITC", "BHARTIARTL",
         "KOTAKBANK", "HINDUNILVR", "MARUTI", "SUNPHARMA", "TITAN"]
NIFTY50 = """ADANIENT ADANIPORTS APOLLOHOSP ASIANPAINT AXISBANK BAJAJ-AUTO BAJAJFINSV BAJFINANCE BEL BHARTIARTL CIPLA
COALINDIA DRREDDY EICHERMOT ETERNAL GRASIM HCLTECH HDFCBANK HDFCLIFE HINDALCO HINDUNILVR ICICIBANK INDIGO INFY ITC
JIOFIN JSWSTEEL KOTAKBANK LT M&M MARUTI MAXHEALTH NESTLEIND NTPC ONGC POWERGRID RELIANCE SBILIFE SBIN SHRIRAMFIN
SUNPHARMA TATACONSUM TATASTEEL TCS TECHM TITAN TMPV TRENT ULTRACEMCO WIPRO""".split()
EXTRA = ["NIFTYBEES"]
# Out-of-basket pool for docs/15 (includes names that later left the NIFTY or collapsed).
POOL = """BHEL GAIL DLF IDEA YESBANK PNB SUZLON JPASSOCIAT RCOM RPOWER RELINFRA IDFC CAIRN RANBAXY SIEMENS ABB ACC
AMBUJACEM BPCL IOC HINDPETRO TATAPOWER VEDL NMDC SAIL BANKBARODA CANBK UNIONBANK LUPIN AUROPHARMA BIOCON ZEEL DISHTV
UNITECH HDIL GMRAIRPORT ADANIPOWER SAMMAANCAP INDUSINDBK BAJAJHLDNG HEROMOTOCO UNITDSPR DABUR GODREJCP MARICO COLPAL
PIDILITIND BERGEPAINT HAVELLS VOLTAS CUMMINSIND BOSCHLTD MRF EXIDEIND ASHOKLEY TVSMOTOR MOTHERSON APOLLOTYRE CESC
TORNTPOWER PFC RECLTD LICHSGFIN MUTHOOTFIN CHOLAFIN FEDERALBNK IDFCFIRSTB GLENMARK ZYDUSLIFE DIVISLAB TORNTPHARM
JUBLFOOD PAGEIND UPL TATACHEM TATACOMM JSWENERGY NHPC OIL PETRONET IGL CONCOR BEML BHARATFORG HINDZINC NATIONALUM
JINDALSTEL MANAPPURAM""".split()
INDEX = {"NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK"}


def save(name, ticker, interval, **kw):
    for attempt in range(3):
        try:
            df = yf.download(ticker, interval=interval, auto_adjust=False, progress=False, threads=False, **kw)
            break
        except Exception as e:  # noqa
            print("  retry", name, interval, e); time.sleep(3)
    else:
        return
    if df is None or df.empty:
        print(f"  EMPTY {name} {interval}"); return
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)
    idx = df.index
    if idx.tz is not None:
        idx = idx.tz_convert("Asia/Kolkata").tz_localize(None)
    df.index = pd.DatetimeIndex(idx, name="ts")
    cols = [c for c in ["open", "high", "low", "close", "adj close", "volume"] if c in df.columns]
    tag = {"1d": "1day", "5m": "5minute", "15m": "15minute", "60m": "1hour"}[interval]
    df[cols].to_csv(OUT / f"{name}_{tag}.csv")
    print(f"  {name:12s} {tag:9s} {len(df):6d} bars {df.index[0]} -> {df.index[-1]}")


syms = sorted(set(WATCH + NIFTY50 + EXTRA + POOL))
print("daily since 2005 ...")
for s in syms:
    save(s, f"{s}.NS", "1d", start="2005-01-01")
for n, t in INDEX.items():
    save(n, t, "1d", start="2005-01-01")
print("intraday (Yahoo keeps ~60 days of 5m/15m, ~730 days of 60m) ...")
for s in WATCH + EXTRA:
    save(s, f"{s}.NS", "5m", period="59d")
    save(s, f"{s}.NS", "15m", period="59d")
    save(s, f"{s}.NS", "60m", period="729d")
save("NIFTY", "^NSEI", "5m", period="59d")
z = OUT.parent / "validation-data.zip"
with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
    for f in sorted(OUT.glob("*.csv")):
        zf.write(f, f.name)
print("wrote", z, round(z.stat().st_size / 1e6, 1), "MB")
