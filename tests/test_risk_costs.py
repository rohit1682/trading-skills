from datetime import datetime

import pytest

from growwbot import risk
from growwbot.costs import CostModel

T = datetime(2026, 10, 27, 10, 30)


def rm(**over):
    return risk.RiskManager({"regime_filter": True, **over}, capital=100_000)


def test_size_by_risk_and_cap():
    r = rm()
    assert r.size(100, 95) == 100            # Rs 500 risk / Rs 5 per share
    assert r.size(100, 99.9) == 200          # risk says 5000, 20 % cap says 200
    assert r.size(100, 95, cash=3000) == 30  # cash-limited
    assert r.size(100, 101) == 0             # stop above entry


def test_pass_and_block_reasons():
    assert rm().check_entry("INFY", 100, 95, 110, T, 0, False).ok
    d = rm().check_entry("INFY", 100, 95, 103, T, 0, False)
    assert not d.ok and "reward:risk" in d.reasons[0]
    d = rm().check_entry("INFY", 100, 95, None, T, 3, False)
    assert not d.ok and any("open positions" in x for x in d.reasons)
    d = rm(blocked_symbols=["INFY"]).check_entry("INFY", 100, 95, None, T, 0, False)
    assert not d.ok
    d = rm().check_entry("INFY", 100, 95, None, T, 0, False, regime_ok=False)
    assert not d.ok and any("regime" in x for x in d.reasons)
    d = rm().check_entry("PENNY", 20, 19, None, T, 0, False)
    assert not d.ok and any("min_price" in x for x in d.reasons)


def test_intraday_window():
    early = datetime(2026, 10, 27, 9, 20)
    late = datetime(2026, 10, 27, 14, 45)
    assert not rm().check_entry("SBIN", 800, 790, None, early, 0, True).ok
    assert not rm().check_entry("SBIN", 800, 790, None, late, 0, True).ok
    assert rm().check_entry("SBIN", 800, 790, None, T, 0, True).ok
    assert rm().check_entry("SBIN", 800, 760, None, late, 0, False).ok  # window is intraday-only


def test_cost_gate_blocks_trades_too_small_for_the_fees():
    # Delivery, Rs 250 at risk on a Rs 20k position: ~Rs 115 of charges (46 % of the risk) -> blocked.
    d = rm().check_entry("SBIN", 800, 790, None, T, 0, False)
    assert not d.ok and any("charges" in x for x in d.reasons)
    assert rm(max_cost_pct_of_risk=0).check_entry("SBIN", 800, 790, None, T, 0, False).ok
    # Same trade intraday: no STT on the buy, no DP charge -> passes.
    assert rm().check_entry("SBIN", 800, 790, None, T, 0, True).ok


def test_daily_limits_and_consecutive_losses():
    r = rm(max_trades_per_day=2)
    r.roll_day(T.date())
    r.record_entry(); r.record_entry()
    assert not r.check_entry("TCS", 4000, 3950, None, T, 0, False).ok
    r = rm()
    r.roll_day(T.date())
    for _ in range(3):
        r.record_exit(-100)
    d = r.check_entry("TCS", 4000, 3950, None, T, 0, False)
    assert not d.ok and r.day.halted_reason
    r = rm()
    r.roll_day(T.date())
    r.record_exit(-1900)  # limit is 2 % of 1,00,000 = 2000
    d = r.check_entry("TCS", 4000, 3950, None, T, 0, False)
    assert not d.ok and any("at risk today" in x for x in d.reasons)
    assert r.breached_daily_loss(unrealised_pnl=-200)


def test_kill_switch_blocks_entries():
    risk.engage_kill_switch("test")
    assert not rm().check_entry("INFY", 100, 95, None, T, 0, False).ok
    assert risk.release_kill_switch()
    assert rm().check_entry("INFY", 100, 95, None, T, 0, False).ok


def test_slippage_guard():
    d = rm().check_entry("INFY", 101, 95, None, T, 0, False, signal_close=100)
    assert not d.ok and any("past the signal" in x for x in d.reasons)


def test_costs_intraday_round_trip():
    c = CostModel()
    # Rs 1,00,000 intraday each way: brokerage 20+20, STT 25 (sell), stamp 3 (buy),
    # exchange 2.97*2, SEBI 0.1*2, IPFT 0.1*2, GST 18 % of (40 + 5.94 + 0.2 + 0.2)
    expected = 40 + 25 + 3 + 5.94 + 0.2 + 0.2 + 0.18 * (40 + 5.94 + 0.2 + 0.2)
    assert c.round_trip(1000, 1000, 100, intraday=True) == pytest.approx(expected, abs=0.05)


def test_costs_min_brokerage_and_delivery():
    c = CostModel()
    small = c.order_cost("BUY", 100, 10, intraday=False)  # Rs 1,000 turnover -> Rs 5 min brokerage
    assert small > 5
    sell = c.order_cost("SELL", 1000, 100, intraday=False)
    assert sell > 100 + 20  # 0.1 % STT on Rs 1 lakh + DP charge
