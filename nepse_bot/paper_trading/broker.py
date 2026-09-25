"""Paper trading adapter (Phase 10) — simulated fills only."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from nepse_bot.risk.manager import RiskManager, RiskConfig


@dataclass
class PaperOrder:
    id: str
    symbol: str
    side: str
    qty: int
    price: float
    status: str
    reason: str = ""
    ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PaperBroker:
    mode = "paper"

    def __init__(self, risk: Optional[RiskManager] = None):
        self.risk = risk or RiskManager(RiskConfig())
        self.orders: list[PaperOrder] = []
        self.fills: list[dict[str, Any]] = []

    def submit(self, symbol: str, side: str, qty: int, price: float) -> PaperOrder:
        side = side.lower()
        decision = self.risk.check_new_order(symbol, qty, price, side=side)
        oid = str(uuid4())[:8]
        if not decision.allowed:
            order = PaperOrder(id=oid, symbol=symbol.upper(), side=side, qty=qty, price=price, status="rejected", reason=decision.reason)
            self.orders.append(order)
            return order
        self.risk.register_fill(symbol, qty, price, side)
        order = PaperOrder(id=oid, symbol=symbol.upper(), side=side, qty=qty, price=price, status="filled", reason="paper fill")
        self.orders.append(order)
        self.fills.append({"order_id": oid, "symbol": symbol.upper(), "side": side, "qty": qty, "price": price, "ts": datetime.now(timezone.utc).isoformat()})
        return order

    def portfolio(self) -> dict[str, Any]:
        return {"mode": self.mode, "risk": self.risk.snapshot(), "orders": len(self.orders), "fills": len(self.fills)}
