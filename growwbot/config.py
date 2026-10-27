"""Load config.toml and .env from the repo root (or $GROWWBOT_HOME)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib  # type: ignore

LIVE_ACK = "YES_I_ACCEPT_REAL_MONEY_RISK"


def home() -> Path:
    env = os.environ.get("GROWWBOT_HOME")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


def state_dir() -> Path:
    d = home() / "state"
    d.mkdir(exist_ok=True)
    return d


def load_dotenv(path: Path | None = None) -> None:
    """Minimal .env reader: KEY=VALUE lines; existing environment variables win."""
    path = path or home() / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        if value:
            os.environ.setdefault(key.strip(), value)


@dataclass
class Config:
    mode: str = "paper"
    capital: float = 50000.0
    watchlist: list[str] = field(default_factory=list)
    strategy: dict = field(default_factory=lambda: {"name": "supertrend_adx", "params": {}})
    risk: dict = field(default_factory=dict)
    execution: dict = field(default_factory=dict)
    backtest: dict = field(default_factory=dict)
    costs: dict = field(default_factory=dict)
    path: Path | None = None

    @property
    def live_requested(self) -> bool:
        return self.mode == "live"


def load(path: str | Path | None = None) -> Config:
    load_dotenv()
    if path is None:
        path = home() / "config.toml"
        if not path.exists():
            path = home() / "config.example.toml"
    path = Path(path)
    data = tomllib.loads(path.read_text())
    cfg = Config(**{k: v for k, v in data.items() if k in Config.__dataclass_fields__ and k != "path"})
    cfg.path = path
    cfg.mode = str(cfg.mode).lower()
    if cfg.mode not in ("paper", "live"):
        raise SystemExit(f"config mode must be 'paper' or 'live', got {cfg.mode!r}")
    cfg.watchlist = [s.strip().upper() for s in cfg.watchlist]
    return cfg


def live_env_ack() -> bool:
    return os.environ.get("GROWW_ENABLE_LIVE", "") == LIVE_ACK
