"""Configuration loader.

Loads `config/default.toml` from the repo, then merges:
1. `~/.imbot/config.toml` if present (user overrides)
2. Environment variables prefixed `IMBOT_` (deepest precedence)

Env vars use double-underscore for nested keys, e.g.
    IMBOT_RISK__MAX_POSITIONS=5
    IMBOT_PATHS__STATE_DB=/tmp/test.duckdb
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "default.toml"
USER_CONFIG_PATH = Path.home() / ".imbot" / "config.toml"
ENV_PREFIX = "IMBOT_"


def _deep_merge(base: dict, overlay: dict) -> dict:
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _env_overrides() -> dict:
    out: dict[str, Any] = {}
    for key, raw in os.environ.items():
        if not key.startswith(ENV_PREFIX):
            continue
        path = key[len(ENV_PREFIX):].lower().split("__")
        node = out
        for part in path[:-1]:
            node = node.setdefault(part, {})
        # Try parsing as TOML literal (number/bool); fall back to string.
        try:
            parsed = tomllib.loads(f"v = {raw}")["v"]
        except tomllib.TOMLDecodeError:
            parsed = raw
        node[path[-1]] = parsed
    return out


def _expand_paths(cfg: dict) -> dict:
    paths = cfg.get("paths", {})
    if "state_db" in paths:
        paths["state_db"] = str(Path(paths["state_db"]).expanduser())
    if "yfinance_cache" in paths:
        paths["yfinance_cache"] = str(Path(paths["yfinance_cache"]).expanduser())
    home_override = os.environ.get("IMBOT_HOME")
    if home_override:
        home = Path(home_override).expanduser()
        paths["state_db"] = str(home / "state.duckdb")
        paths["yfinance_cache"] = str(home / "yfinance.cache")
    cfg["paths"] = paths
    return cfg


@dataclass(frozen=True)
class Config:
    raw: dict

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)

    @property
    def state_db(self) -> Path:
        return Path(self.raw["paths"]["state_db"])

    @property
    def yfinance_cache(self) -> Path:
        return Path(self.raw["paths"]["yfinance_cache"])


@lru_cache(maxsize=1)
def load_config(path: Path | None = None) -> Config:
    cfg_path = path or DEFAULT_CONFIG_PATH
    with open(cfg_path, "rb") as f:
        cfg = tomllib.load(f)
    if USER_CONFIG_PATH.exists():
        with open(USER_CONFIG_PATH, "rb") as f:
            cfg = _deep_merge(cfg, tomllib.load(f))
    cfg = _deep_merge(cfg, _env_overrides())
    cfg = _expand_paths(cfg)
    return Config(raw=cfg)


def reset_config_cache() -> None:
    """For tests: clear the lru_cache so a fresh config is loaded next call."""
    load_config.cache_clear()
