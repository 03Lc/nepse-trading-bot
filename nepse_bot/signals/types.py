"""Signal states and condition results."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class SignalState(str, Enum):
    BUY_SETUP = "BUY SETUP"
    WATCH = "WATCH"
    HOLD = "HOLD"
    SELL_EXIT_SETUP = "SELL/EXIT SETUP"
    NO_SIGNAL = "NO SIGNAL"


class ConditionStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ConditionResult:
    id: str
    description: str
    status: ConditionStatus
    category: str
    detail: str = ""
    value: Optional[float] = None
    threshold: Optional[float] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status.value,
            "category": self.category,
            "detail": self.detail,
            "value": self.value,
            "threshold": self.threshold,
        }

    @property
    def mark(self) -> str:
        if self.status == ConditionStatus.PASSED:
            return "✓"
        if self.status == ConditionStatus.FAILED:
            return "✗"
        return "?"
