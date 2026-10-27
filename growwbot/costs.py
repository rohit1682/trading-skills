"""Groww equity transaction costs (NSE cash segment).

Rates from https://groww.in/pricing/stocks as checked in October 2026. Charges
change; update ``config.toml [costs]`` if Groww or the exchange revises them.
Small trades are hit hardest: the Rs 5 minimum brokerage on a Rs 2,000 trade
is already 0.25 % each way.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    brokerage_pct: float = 0.001          # 0.1 % per executed order ...
    brokerage_max: float = 20.0           # ... capped at Rs 20 ...
    brokerage_min: float = 5.0            # ... with a Rs 5 minimum
    stt_delivery_pct: float = 0.001       # 0.1 % on buy and sell
    stt_intraday_sell_pct: float = 0.00025
    stamp_delivery_buy_pct: float = 0.00015
    stamp_intraday_buy_pct: float = 0.00003
    exchange_txn_pct: float = 0.0000297   # NSE
    sebi_fee_pct: float = 0.000001
    ipft_pct: float = 0.000001
    gst_pct: float = 0.18                 # on brokerage + exchange + SEBI + IPFT (+ DP)
    dp_charge_per_sell: float = 20.0      # delivery sells only, per scrip per day (approx. incl. Groww's part)

    @classmethod
    def from_dict(cls, d: dict | None) -> "CostModel":
        d = d or {}
        return cls(**{k: float(v) for k, v in d.items() if k in cls.__dataclass_fields__})

    def order_cost(self, side: str, price: float, qty: int, intraday: bool) -> float:
        """All-in charges in rupees for one executed order."""
        turnover = price * qty
        if turnover <= 0:
            return 0.0
        brokerage = min(self.brokerage_max, max(self.brokerage_min, turnover * self.brokerage_pct))
        exchange = turnover * self.exchange_txn_pct
        sebi = turnover * self.sebi_fee_pct
        ipft = turnover * self.ipft_pct
        side = side.upper()
        if intraday:
            stt = turnover * self.stt_intraday_sell_pct if side == "SELL" else 0.0
            stamp = turnover * self.stamp_intraday_buy_pct if side == "BUY" else 0.0
            dp = 0.0
        else:
            stt = turnover * self.stt_delivery_pct
            stamp = turnover * self.stamp_delivery_buy_pct if side == "BUY" else 0.0
            dp = self.dp_charge_per_sell if side == "SELL" else 0.0
        gst = self.gst_pct * (brokerage + exchange + sebi + ipft + dp)
        return round(brokerage + exchange + sebi + ipft + stt + stamp + dp + gst, 2)

    def round_trip(self, buy_price: float, sell_price: float, qty: int, intraday: bool) -> float:
        return round(
            self.order_cost("BUY", buy_price, qty, intraday) + self.order_cost("SELL", sell_price, qty, intraday), 2
        )
