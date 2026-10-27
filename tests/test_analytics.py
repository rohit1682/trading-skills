import pandas as pd
import pytest

from growwbot import alerts, analytics, strategies
from tests.conftest import make_daily


def frames(n=8):
    return {f"S{i}": make_daily(seed=50 + i) for i in range(n)}


def test_universe_file_and_list(isolated_home):
    (isolated_home / "universes").mkdir()
    (isolated_home / "universes" / "mine.txt").write_text("# comment\ninfy\nTCS\n\n")
    assert analytics.universe("mine") == ["INFY", "TCS"]
    assert analytics.universe(["a", "b"]) == ["A", "B"]


def test_regime_score_and_posture():
    out = analytics.market_regime(make_daily(seed=1), frames())
    assert 0 <= out["score"] <= 100
    assert out["suggested_risk_multiplier"] in (0.0, 0.5, 1.0)
    assert out["stocks_counted"] == 8
    # a steadily falling index must not read as risk-on
    falling = make_daily(seed=2, drift=-0.003, vol=0.005)
    assert analytics.market_regime(falling, frames())["score"] < 70


def test_screen_presets_and_query():
    f = frames()
    for name in analytics.PRESETS:
        analytics.screen(f, name)  # every preset must be a valid query
    everything = analytics.screen(f, "close > 0")
    assert len(everything) == len(f)


def test_relative_strength_ranks():
    t = analytics.relative_strength(frames(), make_daily(seed=3))
    assert t["rs_rating"].between(1, 99).all()
    assert t["rs_rating"].is_monotonic_decreasing


def test_pivots_math():
    df = pd.DataFrame({"open": [100.0] * 30, "high": [110.0] * 30, "low": [90.0] * 30, "close": [105.0] * 30,
                       "volume": [1.0] * 30}, index=pd.bdate_range("2026-01-01", periods=30))
    lv = analytics.pivot_levels(df)
    p = (110 + 90 + 105) / 3
    assert lv["classic"]["P"] == pytest.approx(p, abs=0.01)
    assert lv["classic"]["R1"] == pytest.approx(2 * p - 90, abs=0.01)
    assert lv["classic"]["S1"] == pytest.approx(2 * p - 110, abs=0.01)
    assert lv["cpr"]["BC"] <= lv["cpr"]["P"] <= lv["cpr"]["TC"]


def test_monte_carlo_bounds():
    r = [2.0, -1.0, -1.0, 1.5, -1.0, 3.0, -1.0, -1.0, 2.0, -1.0, 0.5, -1.0]
    mc = analytics.monte_carlo(r, risk_pct=1.0, sims=500)
    assert mc["return_pct"]["p5"] <= mc["return_pct"]["median"] <= mc["return_pct"]["p95"]
    assert mc["max_drawdown_pct"]["p99_worst"] <= mc["max_drawdown_pct"]["median"] <= 0
    with pytest.raises(ValueError):
        analytics.monte_carlo([1.0, -1.0])


def test_walk_forward_runs():
    out = analytics.walk_forward(frames(4), strategies.get("ema_trend"), {"adx_min": [15, 25]}, folds=2)
    assert len(out["folds"]) == 2 and out["combinations_tested"] == 2
    assert isinstance(out["verdict"], str)


def test_parse_grid():
    assert analytics.parse_grid("adx_min=20,25 rr=1.5,2", "x") == {"adx_min": [20, 25], "rr": [1.5, 2]}
    assert analytics.parse_grid(None, "ema_trend") == analytics.DEFAULT_GRIDS["ema_trend"]


def test_portfolio_review_flags():
    f = {"A": make_daily(seed=5), "B": make_daily(seed=6)}
    t = analytics.portfolio_review([{"symbol": "A", "qty": 100, "avg_price": 1000}, {"symbol": "B", "qty": 1, "avg_price": 1000}], f)
    assert t["weight_pct"].sum() == pytest.approx(100, abs=0.2)
    assert "concentrated" in t.loc["A", "flags"]


def test_alerts_fire_once():
    a = alerts.add("INFY", "above", 1500)
    b = alerts.add("INFY", "rsi_below", 30)
    al = alerts.load()
    fired = alerts.evaluate(al, {"INFY": 1501}, {"INFY": 45})
    assert [x["id"] for x in fired] == [a["id"]]
    assert alerts.evaluate(al, {"INFY": 1600}, {"INFY": 45}) == []
    assert alerts.remove(b["id"]) and not alerts.remove("nope")
    with pytest.raises(ValueError):
        alerts.add("INFY", "sideways", 1)
