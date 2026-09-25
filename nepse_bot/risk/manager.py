"""Risk management (Phase 9)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Optional


@dataclass
class RiskConfig:
    max_risk_per_trade_pct: float = 1.0
    max_daily_loss_pct: float = 3.0
    max_open_positions: int = 3
    max_position_size_pct: float = 20.0
    max_order_frequency_per_minute: int = 10
    emergency_kill_switch: bool = False
    starting_equity: float = 1_000_000.0


@dataclass
class RiskDecision:
    allowed: bool
    reason: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class Position:
    symbol: str
    qty: int
    avg_price: float
    side: str = "long"


class RiskManager:
    def __init__(self, config: Optional[RiskConfig] = None):
        self.config = config or RiskConfig()
        self.equity = self.config.starting_equity
        self.day_start_equity = self.equity
        self.day: date = datetime.now(timezone.utc).date()
        self.positions: dict[str, Position] = {}
        self.order_timestamps: list[datetime] = []
        self.realized_pnl_today: float = 0.0

    def _roll_day(self) -> None:
        today = datetime.now(timezone.utc).date()
        if today != self.day:
            self.day = today
            self.day_start_equity = self.equity
            self.realized_pnl_today = 0.0
            self.order_timestamps.clear()

    def kill_switch(self, enabled: bool = True) -> None:
        self.config.emergency_kill_switch = enabled

    def open_position_count(self) -> int:
        return len(self.positions)

    def check_new_order(self, symbol: str, qty: int, price: float, side: str = "buy") -> RiskDecision:
        self._roll_day()
        cfg = self.config
        if cfg.emergency_kill_switch:
            return RiskDecision(False, "emergency kill switch active")
        if qty <= 0 or price <= 0:
            return RiskDecision(False, "invalid qty/price")
        notional = qty * price
        if self.equity <= 0:
            return RiskDecision(False, "equity non-positive")
        if side.lower() == "buy" and symbol.upper() not in self.positions:
            if self.open_position_count() >= cfg.max_open_positions:
                return RiskDecision(False, f"max open positions ({cfg.max_open_positions}) reached")
        size_pct = 100.0 * notional / self.equity
        if size_pct > cfg.max_position_size_pct:
            return RiskDecision(False, f"position size {size_pct:.1f}% > max {cfg.max_position_size_pct}%", {"size_pct": size_pct})
        day_pnl_pct = 100.0 * (self.equity - self.day_start_equity) / self.day_start_equity
        if day_pnl_pct <= -cfg.max_daily_loss_pct:
            return RiskDecision(False, f"daily loss limit hit ({day_pnl_pct:.2f}%)", {"day_pnl_pct": day_pnl_pct})
        now = datetime.now(timezone.utc)
        self.order_timestamps = [t for t in self.order_timestamps if (now - t).total_seconds() < 60]
        if len(self.order_timestamps) >= cfg.max_order_frequency_per_minute:
            return RiskDecision(False, "order frequency limit per minute exceeded")
        return RiskDecision(True, "ok", {"notional": notional, "size_pct": size_pct})

    def register_fill(self, symbol: str, qty: int, price: float, side: str) -> None:
        self._roll_day()
        self.order_timestamps.append(datetime.now(timezone.utc))
        sym = symbol.upper()
        side = side.lower()
        if side == "buy":
            if sym in self.positions:
                pos = self.positions[sym]
                new_qty = pos.qty + qty
                pos.avg_price = (pos.avg_price * pos.qty + price * qty) / new_qty
                pos.qty = new_qty
            else:
                self.positions[sym] = Position(symbol=sym, qty=qty, avg_price=price)
            self.equity -= qty * price
        elif side == "sell":
            if sym not in self.positions:
                return
            pos = self.positions[sym]
            sell_qty = min(qty, pos.qty)
            self.realized_pnl_today += (price - pos.avg_price) * sell_qty
            self.equity += sell_qty * price
            pos.qty -= sell_qty
            if pos.qty <= 0:
                del self.positions[sym]

    def snapshot(self) -> dict[str, Any]:
        self._roll_day()
        return {
            "equity": self.equity,
            "day_start_equity": self.day_start_equity,
            "open_positions": self.open_position_count(),
            "positions": {k: {"qty": v.qty, "avg_price": v.avg_price} for k, v in self.positions.items()},
            "kill_switch": self.config.emergency_kill_switch,
            "realized_pnl_today": self.realized_pnl_today,
        }
