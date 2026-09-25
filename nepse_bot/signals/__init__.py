"""
Transparent signal / rule engine.

Signals are labels (BUY SETUP, WATCH, …), not profit guarantees.
Every signal lists conditions that passed, failed, or were unavailable.
"""

from nepse_bot.signals.types import SignalState, ConditionResult, ConditionStatus
from nepse_bot.signals.engine import SignalEngine, SignalReport
from nepse_bot.signals.rules import RuleConfig, default_rule_config

__all__ = [
    "SignalState",
    "ConditionResult",
    "ConditionStatus",
    "SignalEngine",
    "SignalReport",
    "RuleConfig",
    "default_rule_config",
]
