"""Tests for configuration loading."""

from nepse_bot.config import get_settings, load_yaml_config


def test_default_yaml_loads():
    data = load_yaml_config()
    assert "bot" in data
    assert "market" in data
    assert "costs" in data
    assert "risk" in data


def test_settings_mode_default():
    settings = get_settings(reload=True)
    assert settings.bot_mode in ("research", "backtest", "paper", "live")
    assert settings.is_live_allowed() is False


def test_risk_overrides_present():
    settings = get_settings(reload=True)
    risk = settings.risk()
    assert "max_risk_per_trade_pct" in risk
    assert risk["max_risk_per_trade_pct"] > 0
    assert risk["max_open_positions"] >= 1


def test_market_section():
    settings = get_settings(reload=True)
    market = settings.market()
    assert market.get("continuous_open") == "11:00"
    assert market.get("continuous_close") == "15:00"
    assert 0 in market.get("trading_weekdays", [])
