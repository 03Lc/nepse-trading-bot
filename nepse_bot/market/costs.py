"""
Transaction cost model for NEPSE.

Uses configurable commission slabs (SEBON ceiling rates as defaults),
SEBON regulatory fee, DP charge, optional CGT, and slippage.

All amounts in NPR. This is a model for research/backtest/paper —
verify live rates with your broker before any real trading.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence


@dataclass(frozen=True)
class CostBreakdown:
    trade_value: float
    commission: float
    sebon_fee: float
    dp_charge: float
    slippage_cost: float
    cgt: float
    total_fees: float
    total_cost: float

    def as_dict(self) -> dict:
        return {
            "trade_value": round(self.trade_value, 2),
            "commission": round(self.commission, 2),
            "sebon_fee": round(self.sebon_fee, 2),
            "dp_charge": round(self.dp_charge, 2),
            "slippage_cost": round(self.slippage_cost, 2),
            "cgt": round(self.cgt, 2),
            "total_fees": round(self.total_fees, 2),
            "total_cost": round(self.total_cost, 2),
        }


class TransactionCostModel:
    def __init__(
        self,
        commission_slabs: Optional[Sequence[tuple[Optional[float], float]]] = None,
        sebon_fee_pct: float = 0.015,
        dp_charge_npr: float = 25.0,
        slippage_pct: float = 0.10,
        cgt_short_term_pct: float = 10.0,
        cgt_long_term_pct: float = 7.5,
        apply_dp_on_sell_only: bool = True,
    ):
        if commission_slabs is None:
            commission_slabs = [
                (50_000, 0.36),
                (500_000, 0.33),
                (2_000_000, 0.31),
                (10_000_000, 0.27),
                (None, 0.24),
            ]
        self.commission_slabs = list(commission_slabs)
        self.sebon_fee_pct = sebon_fee_pct
        self.dp_charge_npr = dp_charge_npr
        self.slippage_pct = slippage_pct
        self.cgt_short_term_pct = cgt_short_term_pct
        self.cgt_long_term_pct = cgt_long_term_pct
        self.apply_dp_on_sell_only = apply_dp_on_sell_only

    @classmethod
    def from_config(cls, costs_cfg: dict) -> "TransactionCostModel":
        slabs_raw = costs_cfg.get("commission_slabs", [])
        slabs: list[tuple[Optional[float], float]] = []
        for item in slabs_raw:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                upper, rate = item
                slabs.append((None if upper is None else float(upper), float(rate)))
        return cls(
            commission_slabs=slabs or None,
            sebon_fee_pct=float(costs_cfg.get("sebon_fee_pct", 0.015)),
            dp_charge_npr=float(costs_cfg.get("dp_charge_npr", 25.0)),
            slippage_pct=float(costs_cfg.get("slippage_pct", 0.10)),
            cgt_short_term_pct=float(costs_cfg.get("cgt_short_term_pct", 10.0)),
            cgt_long_term_pct=float(costs_cfg.get("cgt_long_term_pct", 7.5)),
        )

    def commission_rate(self, trade_value: float) -> float:
        if trade_value < 0:
            raise ValueError("trade_value must be non-negative")
        for upper, rate in self.commission_slabs:
            if upper is None or trade_value <= upper:
                return rate
        return self.commission_slabs[-1][1]

    def estimate(
        self,
        quantity: int,
        price: float,
        side: str,
        realized_profit: float = 0.0,
        is_long_term: bool = False,
        apply_cgt: bool = False,
        apply_slippage: bool = True,
    ) -> CostBreakdown:
        side = side.lower()
        if side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        if quantity <= 0 or price <= 0:
            raise ValueError("quantity and price must be positive")

        trade_value = quantity * price
        rate = self.commission_rate(trade_value)
        commission = trade_value * (rate / 100.0)
        sebon_fee = trade_value * (self.sebon_fee_pct / 100.0)

        dp = 0.0
        if side == "sell" or not self.apply_dp_on_sell_only:
            dp = self.dp_charge_npr

        slippage_cost = 0.0
        if apply_slippage:
            slippage_cost = trade_value * (self.slippage_pct / 100.0)

        cgt = 0.0
        if apply_cgt and side == "sell" and realized_profit > 0:
            cgt_rate = (
                self.cgt_long_term_pct if is_long_term else self.cgt_short_term_pct
            )
            cgt = realized_profit * (cgt_rate / 100.0)

        total_fees = commission + sebon_fee + dp + cgt
        total_cost = total_fees + slippage_cost

        return CostBreakdown(
            trade_value=trade_value,
            commission=commission,
            sebon_fee=sebon_fee,
            dp_charge=dp,
            slippage_cost=slippage_cost,
            cgt=cgt,
            total_fees=total_fees,
            total_cost=total_cost,
        )

    def round_trip_cost_pct(
        self,
        quantity: int,
        price: float,
        apply_slippage: bool = True,
    ) -> float:
        buy = self.estimate(quantity, price, "buy", apply_slippage=apply_slippage)
        sell = self.estimate(quantity, price, "sell", apply_slippage=apply_slippage)
        total = buy.total_cost + sell.total_cost
        return (total / (quantity * price)) * 100.0 if price > 0 else 0.0
