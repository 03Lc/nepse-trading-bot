"""
Configuration loader.

Priority (highest wins):
  1. Environment variables / .env
  2. Optional local YAML override
  3. config/default.yaml
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_YAML = PROJECT_ROOT / "config" / "default.yaml"


def load_yaml_config(path: Path | str | None = None) -> dict[str, Any]:
    p = Path(path) if path else DEFAULT_YAML
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config root must be a mapping: {p}")
    return data


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    bot_mode: str = Field(default="paper", alias="BOT_MODE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_dir: str = Field(default="logs", alias="LOG_DIR")
    data_dir: str = Field(default="data/storage", alias="DATA_DIR")
    timezone: str = Field(default="Asia/Kathmandu", alias="TIMEZONE")

    max_risk_per_trade_pct: float = Field(default=1.0, alias="MAX_RISK_PER_TRADE_PCT")
    max_daily_loss_pct: float = Field(default=3.0, alias="MAX_DAILY_LOSS_PCT")
    max_open_positions: int = Field(default=3, alias="MAX_OPEN_POSITIONS")
    max_position_size_pct: float = Field(default=20.0, alias="MAX_POSITION_SIZE_PCT")

    yaml_config: dict[str, Any] = Field(default_factory=dict, exclude=True)

    def market(self) -> dict[str, Any]:
        return self.yaml_config.get("market", {})

    def costs(self) -> dict[str, Any]:
        return self.yaml_config.get("costs", {})

    def risk(self) -> dict[str, Any]:
        base = self.yaml_config.get("risk", {})
        return {
            **base,
            "max_risk_per_trade_pct": self.max_risk_per_trade_pct,
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "max_open_positions": self.max_open_positions,
            "max_position_size_pct": self.max_position_size_pct,
        }

    def universe(self) -> dict[str, Any]:
        return self.yaml_config.get("universe", {})

    def is_live_allowed(self) -> bool:
        return False


@lru_cache
def get_settings(yaml_path: str | None = None, reload: bool = False) -> Settings:
    if reload:
        get_settings.cache_clear()
    yaml_data = load_yaml_config(yaml_path)
    bot_section = yaml_data.get("bot", {})
    if "BOT_MODE" not in os.environ and bot_section.get("mode"):
        os.environ.setdefault("BOT_MODE", str(bot_section["mode"]))
    if "TIMEZONE" not in os.environ and bot_section.get("timezone"):
        os.environ.setdefault("TIMEZONE", str(bot_section["timezone"]))
    if "LOG_LEVEL" not in os.environ:
        log_section = yaml_data.get("logging", {})
        if log_section.get("level"):
            os.environ.setdefault("LOG_LEVEL", str(log_section["level"]))
    settings = Settings()
    settings.yaml_config = yaml_data
    return settings
