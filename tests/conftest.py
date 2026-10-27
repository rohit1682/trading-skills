import numpy as np
import pandas as pd
import pytest


def make_daily(n=600, seed=7, drift=0.0006, vol=0.015, start=1000.0):
    rng = np.random.default_rng(seed)
    # Alternate trending regimes so trend and mean-reversion strategies both fire.
    regime = np.sign(np.sin(np.arange(n) / 60.0)) * drift * 3 + drift
    rets = rng.normal(regime, vol)
    close = start * np.exp(np.cumsum(rets))
    open_ = np.r_[start, close[:-1]] * (1 + rng.normal(0, 0.003, n))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.006, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.006, n)))
    vol_ = rng.integers(500_000, 2_000_000, n).astype(float)
    idx = pd.bdate_range("2023-01-02", periods=n)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": vol_}, index=idx)


def make_intraday(days=20, seed=3, start=500.0):
    rng = np.random.default_rng(seed)
    frames, px = [], start
    for d in pd.bdate_range("2026-09-01", periods=days):
        times = pd.date_range(d + pd.Timedelta(hours=9, minutes=15), d + pd.Timedelta(hours=15, minutes=25), freq="5min")
        n = len(times)
        day_drift = rng.normal(0, 0.0008)
        rets = rng.normal(day_drift, 0.002, n)
        close = px * np.exp(np.cumsum(rets))
        open_ = np.r_[px, close[:-1]]
        high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.001, n)))
        low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.001, n)))
        vol = rng.integers(10_000, 80_000, n).astype(float)
        vol[:3] *= 3
        frames.append(pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": vol}, index=times))
        px = close[-1]
    return pd.concat(frames)


@pytest.fixture
def daily():
    return make_daily()


@pytest.fixture
def intraday():
    return make_intraday()


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Every test gets its own state/ folder and no real credentials."""
    import shutil
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    shutil.copy(root / "config.example.toml", tmp_path / "config.toml")
    monkeypatch.setenv("GROWWBOT_HOME", str(tmp_path))
    for k in ("GROWW_API_KEY", "GROWW_ACCESS_TOKEN", "GROWW_TOTP_SECRET", "GROWW_API_SECRET", "GROWW_ENABLE_LIVE"):
        monkeypatch.delenv(k, raising=False)
    return tmp_path
