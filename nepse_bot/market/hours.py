"""
NEPSE market-hours helpers.

Uses Asia/Kathmandu. Trading week is Monday–Friday as of April 2026.
Continuous session default: 11:00–15:00 NPT.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

KATHMANDU = ZoneInfo("Asia/Kathmandu")


@dataclass(frozen=True)
class MarketHours:
    open_time: time = time(11, 0)
    close_time: time = time(15, 0)
    trading_weekdays: tuple[int, ...] = (0, 1, 2, 3, 4)
    timezone: ZoneInfo = KATHMANDU

    @classmethod
    def from_config(cls, market_cfg: dict) -> "MarketHours":
        open_str = market_cfg.get("continuous_open", "11:00")
        close_str = market_cfg.get("continuous_close", "15:00")
        weekdays = market_cfg.get("trading_weekdays", [0, 1, 2, 3, 4])
        oh, om = map(int, open_str.split(":"))
        ch, cm = map(int, close_str.split(":"))
        return cls(
            open_time=time(oh, om),
            close_time=time(ch, cm),
            trading_weekdays=tuple(weekdays),
        )

    def now(self, dt: Optional[datetime] = None) -> datetime:
        if dt is None:
            return datetime.now(self.timezone)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=self.timezone)
        return dt.astimezone(self.timezone)

    def is_trading_day(self, d: date | datetime) -> bool:
        if isinstance(d, datetime):
            d = self.now(d).date()
        return d.weekday() in self.trading_weekdays

    def is_open(self, dt: Optional[datetime] = None) -> bool:
        current = self.now(dt)
        if not self.is_trading_day(current):
            return False
        t = current.time()
        return self.open_time <= t < self.close_time

    def session_bounds(self, d: Optional[date] = None) -> tuple[datetime, datetime]:
        current = self.now()
        target = d if d is not None else current.date()
        open_dt = datetime.combine(target, self.open_time, tzinfo=self.timezone)
        close_dt = datetime.combine(target, self.close_time, tzinfo=self.timezone)
        return open_dt, close_dt

    def next_open(self, dt: Optional[datetime] = None) -> datetime:
        current = self.now(dt)
        candidate_date = current.date()
        for _ in range(10):
            if self.is_trading_day(candidate_date):
                open_dt, _ = self.session_bounds(candidate_date)
                if open_dt > current:
                    return open_dt
            candidate_date += timedelta(days=1)
        raise RuntimeError("Could not find next open within 10 days")

    def next_close(self, dt: Optional[datetime] = None) -> datetime:
        current = self.now(dt)
        if self.is_open(current):
            _, close_dt = self.session_bounds(current.date())
            return close_dt
        open_dt = self.next_open(current)
        _, close_dt = self.session_bounds(open_dt.date())
        return close_dt

    def seconds_to_close(self, dt: Optional[datetime] = None) -> Optional[float]:
        current = self.now(dt)
        if not self.is_open(current):
            return None
        _, close_dt = self.session_bounds(current.date())
        return (close_dt - current).total_seconds()


_DEFAULT = MarketHours()


def is_market_open(dt: Optional[datetime] = None) -> bool:
    return _DEFAULT.is_open(dt)


def next_open(dt: Optional[datetime] = None) -> datetime:
    return _DEFAULT.next_open(dt)


def next_close(dt: Optional[datetime] = None) -> datetime:
    return _DEFAULT.next_close(dt)
