"""Shared types for indicators and later fundamental/valuation metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class MetricStatus(str, Enum):
    OK = "ok"
    INSUFFICIENT_DATA = "insufficient_data"
    UNAVAILABLE = "unavailable"
    STALE = "stale"
    ERROR = "error"


@dataclass(frozen=True)
class MetricResult:
    """
    Traceable metric: never invent values when data is missing.

    value may be None when status != OK.
    """

    name: str
    value: Optional[float]
    status: MetricStatus
    source: str = "computed"
    timestamp: Optional[datetime] = None
    period: Optional[int] = None
    unit: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "status": self.status.value,
            "source": self.source,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "period": self.period,
            "unit": self.unit,
            **self.extra,
        }

    @classmethod
    def unavailable(cls, name: str, reason: str = "data unavailable") -> MetricResult:
        return cls(
            name=name,
            value=None,
            status=MetricStatus.UNAVAILABLE,
            source=reason,
            timestamp=datetime.now(timezone.utc),
        )

    @classmethod
    def insufficient(cls, name: str, need: int, have: int) -> MetricResult:
        return cls(
            name=name,
            value=None,
            status=MetricStatus.INSUFFICIENT_DATA,
            source="computed",
            timestamp=datetime.now(timezone.utc),
            extra={"bars_needed": need, "bars_available": have},
        )

    @classmethod
    def ok(
        cls,
        name: str,
        value: float,
        *,
        period: Optional[int] = None,
        unit: Optional[str] = None,
        source: str = "computed",
        timestamp: Optional[datetime] = None,
        **extra: Any,
    ) -> MetricResult:
        return cls(
            name=name,
            value=float(value),
            status=MetricStatus.OK,
            source=source,
            timestamp=timestamp or datetime.now(timezone.utc),
            period=period,
            unit=unit,
            extra=dict(extra),
        )
