"""Phases 7–14 unit tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nepse_bot.alerts.base import Alert, AlertManager, ConsoleAlertBackend
from nepse_bot.backtesting.engine import BacktestEngine
from nepse_bot.dashboard.app import write_scan_dashboard
from nepse_bot.execution.live import LiveExecutionAdapter, LiveExecutionBlockedError
from nepse_bot.paper_trading.broker import PaperBroker
from nepse_bot.providers.base import MockDataProvider, OfficialRealtimeDataProvider
from nepse_bot.risk.manager import RiskManager, RiskConfig
from nepse_bot.scanner.engine import ConcurrentScanner
from nepse_bot.signals.rules import RuleConfig


def _frame(symbol: str, n: int = 120, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="B", tz="UTC")
    rets = rng.normal(0.0008, 0.012, size=n)
    close = 500 * np.exp(np.cumsum(rets))
    return pd.DataFrame({
        "symbol": symbol, "timestamp": dates,
        "open": close, "high": close * 1.01, "low": close * 0.99,
        "close": close, "volume": rng.integers(1000, 20000, n).astype(float),
    })


def test_mock_provider_and_scanner():
    frames = {"AAA": _frame("AAA", seed=1), "BBB": _frame("BBB", seed=2), "CCC": _frame("CCC", seed=3)}
    scanner = ConcurrentScanner(
        MockDataProvider(frames), max_workers=4,
        rule_config=RuleConfig(buy_setup_min_passed=2, buy_setup_max_failed=10, watch_min_passed=1),
    )
    report = scanner.scan(["AAA", "BBB", "CCC"])
    assert report.symbols_scanned == 3
    assert len(report.results) == 3


def test_risk_and_paper_broker():
    risk = RiskManager(RiskConfig(max_open_positions=1, starting_equity=100_000))
    broker = PaperBroker(risk)
    assert broker.submit("NABIL", "buy", 10, 500).status == "filled"
    assert broker.submit("NICA", "buy", 10, 500).status == "rejected"
    assert "NABIL" in broker.portfolio()["risk"]["positions"]


def test_kill_switch():
    risk = RiskManager(RiskConfig())
    risk.kill_switch(True)
    assert not risk.check_new_order("X", 1, 100).allowed


def test_backtest_runs():
    result = BacktestEngine(min_bars=50, qty=10).run(_frame("TEST", n=150, seed=5), symbol="TEST")
    assert result.bars == 150
    assert "Research" in "\n".join(result.summary_lines())


def test_alerts_dedupe():
    mgr = AlertManager(backends=[ConsoleAlertBackend()], dedupe_ttl_sec=60)
    a = Alert(symbol="NABIL", title="BUY SETUP", body="test", signal="BUY SETUP", priority="high")
    assert mgr.emit(a) is True
    assert mgr.emit(a) is False


def test_live_blocked():
    with pytest.raises(LiveExecutionBlockedError):
        LiveExecutionAdapter()
    with pytest.raises(NotImplementedError):
        OfficialRealtimeDataProvider()


def test_dashboard_html(tmp_path: Path):
    report = ConcurrentScanner(MockDataProvider({"AAA": _frame("AAA")}), max_workers=2).scan(["AAA"])
    path = write_scan_dashboard(report, path=tmp_path / "dash.html")
    assert "AAA" in path.read_text()
