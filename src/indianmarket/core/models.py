"""Strongly-typed result objects returned by the strategy core.

All frozen dataclasses — pure data, no I/O, no logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


Regime = Literal["bull", "bear"]


@dataclass(frozen=True)
class MomentumResult:
    ticker: str
    score: float                # 6-month % return (or 0 if filter failed)
    passed: bool
    reason: str
    price: float
    dma_200: float | None
    high_52w: float | None


@dataclass(frozen=True)
class DividendScore:
    ticker: str
    score: float
    yield_pct: float
    passed: bool
    reason: str


@dataclass(frozen=True)
class SwingSetup:
    ticker: str
    price: float
    score: int
    stop_loss: float
    atr: float
    risk_per_share: float
    triggers: tuple[str, ...]
    target: float | None = None        # only set when caller asked for a hard target


@dataclass(frozen=True)
class Allocation:
    core_inr: float
    alpha_inr: float
    core_pct: float
    alpha_pct: float
    regime: Regime


@dataclass(frozen=True)
class Position:
    ticker: str
    qty: int
    entry_price: float
    entry_ts: datetime
    stop_loss: float
    atr_at_entry: float
    days_held: int = 0
    high_water: float | None = None


@dataclass(frozen=True)
class Trade:
    ticker: str
    entry_ts: datetime
    exit_ts: datetime
    qty: int
    entry_price: float
    exit_price: float
    net_pnl: float
    pnl_pct: float
    reason: str


@dataclass(frozen=True)
class BacktestResult:
    final_equity: float
    total_invested: float
    net_profit: float
    roi_pct: float
    xirr_pct: float | None
    max_drawdown_pct: float
    wins: int
    losses: int
    trades: list[Trade] = field(default_factory=list)


@dataclass(frozen=True)
class ProjectionSnapshot:
    year: int
    invested: float
    nominal_value: float
    real_value: float
    safe_withdrawal: float
    inflated_expense: float
    fire_achieved: bool


@dataclass(frozen=True)
class ProjectionResult:
    snapshots: list[ProjectionSnapshot]
    fire_month: int | None         # 1-indexed month when FIRE crossover happens
    effective_eur_return: float
