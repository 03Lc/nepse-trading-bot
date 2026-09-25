"""Configurable rule thresholds — research defaults, not claimed edge."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Optional


@dataclass
class RuleConfig:
    rsi_buy_min: float = 40.0
    rsi_buy_max: float = 70.0
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    min_relative_volume: float = 1.2
    require_above_ema50: bool = True
    require_above_ema200: bool = False
    prefer_breakout: bool = True
    adx_trend_min: float = 20.0
    require_positive_eps_growth: bool = False
    require_positive_roe: bool = False
    max_pe: Optional[float] = None
    max_pb: Optional[float] = None
    prefer_outperform_nepse_20d: bool = True
    avoid_strong_downtrend_market: bool = True
    buy_setup_min_passed: int = 5
    buy_setup_max_failed: int = 2
    watch_min_passed: int = 3
    sell_setup_min_failed_bullish: int = 4
    atr_stop_mult: float = 1.5
    atr_target_mult: float = 2.5

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> RuleConfig:
        if not data:
            return cls()
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore
        return cls(**{k: v for k, v in data.items() if k in known})


def default_rule_config() -> RuleConfig:
    return RuleConfig()
