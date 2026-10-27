"""Thin wrapper around the official ``growwapi`` Python SDK.

Only this module talks to Groww. It handles login (TOTP, key+secret, or a
pasted access token), a simple order-rate limiter, and retries on rate-limit
errors. SDK reference: https://groww.in/trade-api/docs/python-sdk
"""

from __future__ import annotations

import os
import threading
import time as _time

from . import config


class GrowwUnavailable(RuntimeError):
    pass


def _import_sdk():
    try:
        from growwapi import GrowwAPI  # noqa: WPS433
    except ImportError as e:  # pragma: no cover - depends on environment
        raise GrowwUnavailable("growwapi is not installed. Run: pip install -r requirements.txt") from e
    return GrowwAPI


def access_token() -> str:
    """Resolve an access token from .env, in order: pasted token, TOTP, key+secret."""
    config.load_dotenv()
    token = os.environ.get("GROWW_ACCESS_TOKEN")
    if token:
        return token
    api_key = os.environ.get("GROWW_API_KEY")
    if not api_key:
        raise GrowwUnavailable("No Groww credentials. Fill GROWW_API_KEY (+ TOTP secret or API secret) in .env")
    GrowwAPI = _import_sdk()
    totp_secret = os.environ.get("GROWW_TOTP_SECRET")
    if totp_secret:
        import pyotp

        return GrowwAPI.get_access_token(api_key=api_key, totp=pyotp.TOTP(totp_secret).now())
    secret = os.environ.get("GROWW_API_SECRET")
    if secret:
        return GrowwAPI.get_access_token(api_key=api_key, secret=secret)
    raise GrowwUnavailable("Set GROWW_TOTP_SECRET or GROWW_API_SECRET in .env")


def has_credentials() -> bool:
    config.load_dotenv()
    return bool(os.environ.get("GROWW_ACCESS_TOKEN") or os.environ.get("GROWW_API_KEY"))


class Groww:
    """Lazily-connected SDK handle with an order rate limiter."""

    def __init__(self, max_orders_per_second: float = 1.0):
        self._api = None
        self._lock = threading.Lock()
        self._min_gap = 1.0 / max(0.1, float(max_orders_per_second))
        self._last_order = 0.0

    @property
    def api(self):
        if self._api is None:
            GrowwAPI = _import_sdk()
            self._api = GrowwAPI(access_token())
        return self._api

    def call(self, method: str, *args, retries: int = 3, **kwargs):
        last = None
        for attempt in range(retries):
            try:
                return getattr(self.api, method)(*args, **kwargs)
            except Exception as e:  # SDK raises GrowwAPIRateLimitException / TimeoutException etc.
                name = type(e).__name__
                if "RateLimit" in name or "Timeout" in name:
                    last = e
                    _time.sleep(1.5 * (attempt + 1))
                    continue
                raise
        raise last  # type: ignore[misc]

    def order_call(self, method: str, **kwargs):
        """Like ``call`` but spaced out so we never exceed max_orders_per_second."""
        with self._lock:
            wait = self._min_gap - (_time.monotonic() - self._last_order)
            if wait > 0:
                _time.sleep(wait)
            try:
                return self.call(method, retries=1, **kwargs)
            finally:
                self._last_order = _time.monotonic()

    # ---- convenience wrappers -------------------------------------------------
    def ltp(self, symbols: list[str], exchange: str = "NSE") -> dict[str, float]:
        out: dict[str, float] = {}
        for i in range(0, len(symbols), 50):  # API takes up to 50 per call
            keys = tuple(f"{exchange}_{s}" for s in symbols[i:i + 50])
            resp = self.call("get_ltp", segment="CASH", exchange_trading_symbols=keys)
            for k, v in (resp or {}).items():
                out[k.split("_", 1)[1]] = float(v)
        return out

    def quote(self, symbol: str, exchange: str = "NSE") -> dict:
        return self.call("get_quote", exchange=exchange, segment="CASH", trading_symbol=symbol)

    def candles(self, symbol: str, interval: str, start: str, end: str, exchange: str = "NSE") -> list:
        resp = self.call(
            "get_historical_candles",
            exchange=exchange,
            segment="CASH",
            groww_symbol=f"{exchange}-{symbol}",
            start_time=start,
            end_time=end,
            candle_interval=interval,
        )
        return (resp or {}).get("candles", [])

    def cash_available(self) -> float:
        m = self.call("get_available_margin_details") or {}
        eq = m.get("equity_margin_details") or {}
        return float(eq.get("cnc_balance_available", m.get("clear_cash", 0.0)) or 0.0)
