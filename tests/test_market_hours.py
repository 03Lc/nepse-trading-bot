"""Tests for NEPSE market-hours helpers."""

from datetime import datetime, time
from zoneinfo import ZoneInfo

from nepse_bot.market.hours import MarketHours

KTM = ZoneInfo("Asia/Kathmandu")


def _dt(y, m, d, hh, mm=0) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=KTM)


def test_weekday_is_trading_day():
    hours = MarketHours()
    assert hours.is_trading_day(_dt(2026, 9, 25, 12, 0)) is True
    assert hours.is_trading_day(_dt(2026, 9, 26, 12, 0)) is False
    assert hours.is_trading_day(_dt(2026, 9, 27, 12, 0)) is False


def test_open_during_session():
    hours = MarketHours()
    assert hours.is_open(_dt(2026, 9, 25, 12, 0)) is True
    assert hours.is_open(_dt(2026, 9, 25, 10, 0)) is False
    assert hours.is_open(_dt(2026, 9, 25, 15, 0)) is False
    assert hours.is_open(_dt(2026, 9, 26, 12, 0)) is False


def test_next_open_after_close():
    hours = MarketHours()
    after = _dt(2026, 9, 25, 16, 0)
    nxt = hours.next_open(after)
    assert nxt.date().weekday() == 0
    assert nxt.time() == time(11, 0)


def test_next_open_before_open_same_day():
    hours = MarketHours()
    before = _dt(2026, 9, 25, 9, 0)
    nxt = hours.next_open(before)
    assert nxt.date() == before.date()
    assert nxt.time() == time(11, 0)


def test_seconds_to_close():
    hours = MarketHours()
    mid = _dt(2026, 9, 25, 14, 0)
    secs = hours.seconds_to_close(mid)
    assert secs is not None
    assert 3500 < secs < 3700
    after = _dt(2026, 9, 25, 16, 0)
    assert hours.seconds_to_close(after) is None


def test_from_config():
    cfg = {
        "continuous_open": "11:00",
        "continuous_close": "15:00",
        "trading_weekdays": [0, 1, 2, 3, 4],
    }
    hours = MarketHours.from_config(cfg)
    assert hours.open_time == time(11, 0)
    assert hours.close_time == time(15, 0)
