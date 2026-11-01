"""scripts/validate_strategies.py: look-ahead probe and statistics (network-free)."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

from growwbot import strategies
from tests.conftest import make_daily, make_intraday

_spec = importlib.util.spec_from_file_location(
    "validate_strategies", Path(__file__).resolve().parent.parent / "scripts" / "validate_strategies.py")
vs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vs)


def test_no_strategy_looks_ahead():
    daily, intra = make_daily(700), make_intraday(25)
    for s in strategies.STRATEGIES.values():
        df = intra if s.intraday else daily
        assert vs.lookahead_probe(df, s, cuts=6)["mismatched_values"] == 0, s.name


def test_probe_catches_a_cheating_strategy():
    def peek(df):
        c = df["close"]
        return pd.DataFrame({"entry": c.shift(-1) > c, "exit": False, "stop": c * 0.97, "target": np.nan})
    cheat = strategies.Strategy("cheat", "uses tomorrow's close", "1day", False, peek)
    assert vs.lookahead_probe(make_daily(400), cheat, cuts=6)["mismatched_values"] > 0


def test_r_stats():
    out = vs.r_stats(np.array([1.0, -1.0] * 50 + [2.0] * 10))
    assert out["exp_r"] > 0 and out["t_stat"] > 0
    assert out["ci95_r"][0] < out["exp_r"] < out["ci95_r"][1]
    assert out["trades_needed_t2"] > 0
    assert vs.r_stats(np.array([]))["exp_r"] is None
