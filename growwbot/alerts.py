"""Price and indicator alerts, stored in state/alerts.json.

Conditions: ``above`` / ``below`` a price, and ``rsi_above`` / ``rsi_below``
on daily RSI(14). Notifications always print; they also go to Telegram when
TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are set in .env. Alerts never trade.
"""

from __future__ import annotations

import json
import os
import secrets
import time as _time
import urllib.parse
import urllib.request
from datetime import datetime

from . import config

CONDITIONS = ("above", "below", "rsi_above", "rsi_below")


def _path():
    return config.state_dir() / "alerts.json"


def load() -> list[dict]:
    p = _path()
    return json.loads(p.read_text()) if p.exists() else []


def save(alerts: list[dict]) -> None:
    _path().write_text(json.dumps(alerts, indent=2))


def add(symbol: str, condition: str, value: float, note: str = "") -> dict:
    if condition not in CONDITIONS:
        raise ValueError(f"condition must be one of {CONDITIONS}")
    a = {"id": secrets.token_hex(3), "symbol": symbol.upper(), "condition": condition, "value": float(value),
         "note": note, "created": datetime.now().isoformat(timespec="seconds"), "triggered": None}
    alerts = load()
    alerts.append(a)
    save(alerts)
    return a


def remove(alert_id: str) -> bool:
    alerts = load()
    keep = [a for a in alerts if a["id"] != alert_id]
    save(keep)
    return len(keep) != len(alerts)


def notify(text: str) -> None:
    print(text, flush=True)
    config.load_dotenv()
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat:
        try:
            body = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
            urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=body, timeout=10)
        except Exception as e:  # never let a notification failure stop the watcher
            print(f"[warn] Telegram send failed: {e}")


def evaluate(alerts: list[dict], prices: dict[str, float], rsis: dict[str, float]) -> list[dict]:
    """Mark and return alerts that fire now. Each alert fires once."""
    fired = []
    for a in alerts:
        if a["triggered"]:
            continue
        px, r = prices.get(a["symbol"]), rsis.get(a["symbol"])
        hit = (
            (a["condition"] == "above" and px is not None and px >= a["value"])
            or (a["condition"] == "below" and px is not None and px <= a["value"])
            or (a["condition"] == "rsi_above" and r is not None and r >= a["value"])
            or (a["condition"] == "rsi_below" and r is not None and r <= a["value"])
        )
        if hit:
            a["triggered"] = datetime.now().isoformat(timespec="seconds")
            a["at_price"] = px
            fired.append(a)
    return fired


def watch(get_prices, get_rsis, interval_s: float = 60.0, once: bool = False) -> None:
    rsis = get_rsis([a["symbol"] for a in load() if a["condition"].startswith("rsi")])
    while True:
        alerts = load()
        pending = [a for a in alerts if not a["triggered"]]
        if not pending:
            print("No pending alerts.")
            return
        prices = get_prices(sorted({a["symbol"] for a in pending}))
        for a in evaluate(alerts, prices, rsis):
            notify(f"ALERT {a['symbol']} {a['condition']} {a['value']} (price {a.get('at_price')}) {a['note']}".strip())
        save(alerts)
        if once:
            return
        _time.sleep(interval_s)
