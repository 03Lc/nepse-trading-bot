"""Simple chronological bar backtest (Phase 8) — no look-ahead."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd

from nepse_bot.indicators.engine import TechnicalEngine
from nepse_bot.risk.manager import RiskManager, RiskConfig
from nepse_bot.signals.engine import SignalEngine
from nepse_bot.signals.rules import RuleConfig
from nepse_bot.signals.types import SignalState


@dataclass
class BacktestResult:
    symbol: str
    bars: int
    trades: int
    final_equity: float
    starting_equity: float
    return_pct: float
    trade_log: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def summary_lines(self) -> list[str]:
        return [
            f"Backtest {self.symbol}",
            f"  bars={self.bars}  trades={self.trades}",
            f"  start={self.starting_equity:.2f}  end={self.final_equity:.2f}",
            f"  return={self.return_pct:.2f}%",
            *([f"  note: {n}" for n in self.notes]),
            "  (Research simulation only — not a performance claim)",
        ]


class BacktestEngine:
    def __init__(
        self,
        *,
        rule_config: Optional[RuleConfig] = None,
        risk_config: Optional[RiskConfig] = None,
        min_bars: int = 60,
        qty: int = 100,
    ):
        self.rule_config = rule_config or RuleConfig()
        self.risk_config = risk_config or RiskConfig()
        self.min_bars = min_bars
        self.qty = qty
        self.technical = TechnicalEngine()
        self.signals = SignalEngine(self.rule_config)

    def run(self, df: pd.DataFrame, symbol: str = "SYM") -> BacktestResult:
        work = df.copy()
        work.columns = [str(c).strip().lower() for c in work.columns]
        work = work.sort_values("timestamp" if "timestamp" in work.columns else work.columns[0])
        work = work.reset_index(drop=True)

        risk = RiskManager(self.risk_config)
        starting = risk.equity
        trade_log: list[dict[str, Any]] = []
        notes: list[str] = []
        position = 0

        if len(work) < self.min_bars + 5:
            notes.append("insufficient bars for meaningful backtest")
            return BacktestResult(
                symbol=symbol, bars=len(work), trades=0,
                final_equity=starting, starting_equity=starting, return_pct=0.0, notes=notes,
            )

        for i in range(self.min_bars, len(work)):
            window = work.iloc[: i + 1]
            tech = self.technical.compute(window, symbol=symbol)
            report = self.signals.evaluate(symbol, technical=tech)
            price = float(work.iloc[i]["close"])

            if position == 0 and report.state == SignalState.BUY_SETUP:
                d = risk.check_new_order(symbol, self.qty, price, side="buy")
                if d.allowed:
                    risk.register_fill(symbol, self.qty, price, "buy")
                    position = self.qty
                    trade_log.append({"i": i, "side": "buy", "price": price, "qty": self.qty})
            elif position > 0 and report.state == SignalState.SELL_EXIT_SETUP:
                risk.register_fill(symbol, position, price, "sell")
                trade_log.append({"i": i, "side": "sell", "price": price, "qty": position})
                position = 0

        last = float(work.iloc[-1]["close"])
        final = risk.equity + position * last if position > 0 else risk.equity
        ret = 100.0 * (final - starting) / starting if starting else 0.0
        notes.append("Chronological walk; signals on expanding window only")
        return BacktestResult(
            symbol=symbol.upper(), bars=len(work), trades=len(trade_log),
            final_equity=final, starting_equity=starting, return_pct=ret,
            trade_log=trade_log, notes=notes,
        )
