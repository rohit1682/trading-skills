import numpy as np
import pytest

from growwbot import odds, strategies
from tests.conftest import make_daily, make_intraday


def daily_pools(seed=7):
    return odds.build_pools(make_daily(seed=seed), intraday=False)


def test_pool_shapes():
    p = daily_pools()
    assert p.ndim == 2 and p.shape[1] == 4
    assert (p > 0).all()
    intra = make_intraday()
    pools = odds.build_pools(intra, intraday=True, window=2)
    bars_per_day = len(intra) // len(set(intra.index.date))
    assert isinstance(pools, list) and len(pools) == bars_per_day


def test_deterministic_for_a_seed():
    p = daily_pools()
    a = odds.replay(p, 100, 98, 104, bars=20, sims=2000, seed=19)
    b = odds.replay(p, 100, 98, 104, bars=20, sims=2000, seed=19)
    c = odds.replay(p, 100, 98, 104, bars=20, sims=2000, seed=20)
    assert a == b
    assert a["target_first_pct"] != c["target_first_pct"]


def test_outcomes_partition():
    o = odds.replay(daily_pools(), 100, 97, 106, bars=25, sims=3000)
    total = o["target_first_pct"] + o["stop_first_pct"] + o["neither_pct"]
    assert total == pytest.approx(100, abs=0.2)
    assert 0 <= o["green_pct"] <= 100


def test_near_target_beats_far_stop():
    p = daily_pools()
    easy = odds.replay(p, 100, 80, 100.2, bars=20, sims=2000)
    hard = odds.replay(p, 100, 99.8, 120, bars=20, sims=2000)
    assert easy["target_first_pct"] > 90
    assert hard["stop_first_pct"] > 90


def test_more_bars_decide_more_trades():
    p = daily_pools()
    short = odds.replay(p, 100, 95, 110, bars=2, sims=2000)
    long = odds.replay(p, 100, 95, 110, bars=40, sims=2000)
    assert long["neither_pct"] < short["neither_pct"]


def test_stop_must_be_below_entry():
    with pytest.raises(ValueError):
        odds.replay(daily_pools(), 100, 100, 110, bars=10, sims=100)


def test_breakeven_arithmetic():
    for rr, need in ((1.0, 50.0), (2.0, 33.3), (3.0, 25.0)):
        v = odds.verdict({"target_first_pct": 40.0, "stop_first_pct": 40.0, "neither_pct": 20.0,
                          "reward_risk": rr, "avg_r": 0.0, "worse_than_1R_loss_pct": 0.0})
        assert v["breakeven_win_rate_pct"] == pytest.approx(need, abs=0.1)


def test_verdict_wording_follows_the_edge():
    def v(target_first, stop_first, rr=1.0):
        return odds.verdict({"target_first_pct": target_first, "stop_first_pct": stop_first,
                             "neither_pct": 100 - target_first - stop_first, "reward_risk": rr,
                             "avg_r": 0.0, "worse_than_1R_loss_pct": 0.0})["verdict"]

    assert "coin flip" in v(50.0, 50.0)
    assert "strongly toward the target" in v(80.0, 20.0)
    assert "strongly toward the stop" in v(20.0, 80.0)
    assert "Leans toward the target" in v(57.0, 43.0)
    # A 3R target that wins only 30% of decided trades still beats its 25% break-even.
    v = odds.verdict({"target_first_pct": 30.0, "stop_first_pct": 70.0, "neither_pct": 0.0,
                      "reward_risk": 3.0, "avg_r": 0.2, "worse_than_1R_loss_pct": 0.0})
    assert "toward the target" in v["verdict"]


def test_gap_through_stop_can_lose_more_than_1r():
    o = odds.replay(daily_pools(), 100, 99.9, 110, bars=20, sims=3000)
    assert o["worse_than_1R_loss_pct"] > 0


def test_bars_remaining():
    from datetime import datetime

    now = datetime(2026, 10, 27, 10, 30)
    assert odds.bars_remaining("5minute", now, "15:10") == 56
    assert odds.bars_remaining("15minute", now, "15:10") == 19
    assert odds.bars_remaining("1day", now, "15:10", default_hold=20) == 20


def test_precedent_reports_real_trades():
    df = make_daily(seed=11)
    p = odds.precedent("X", df, strategies.get("ema_trend"), {}, {})
    assert p["trades"] > 0
    assert -5 < p["avg_r"] < 5
    assert p["worst_r"] <= p["best_r"]


def test_reconcile_flags_disagreement():
    out = {"edge_points": 12.0, "verdict": "x"}
    odds.reconcile(out, {"trades": 5, "avg_r": -0.9})
    assert any("disagree" in n for n in out["notes"])
    quiet = {"edge_points": 12.0}
    odds.reconcile(quiet, {"trades": 5, "avg_r": 0.4})
    assert "notes" not in quiet
    odds.reconcile(quiet, {"trades": 2, "avg_r": -0.9})  # too few to judge
    assert "notes" not in quiet


def test_backtest_breakeven_identity():
    from growwbot import backtest as bt

    res = bt.run({f"S{i}": make_daily(seed=i) for i in range(4)}, strategies.get("ema_trend"),
                 initial_capital=100_000)
    m = res.metrics()
    w, l = m["avg_win_r"], -m["avg_loss_r"]
    assert m["breakeven_win_rate_pct"] == pytest.approx(100 * l / (w + l), abs=0.1)
