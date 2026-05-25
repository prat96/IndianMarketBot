"""Allocation splits and position sizing.

Replaces 3× hard-coded 40/60 vs 80/20 splits and the ATR-based sizing math
duplicated between:
    legacy/paper_trader.py:467-478
    legacy/swing_backtest.py:299-311
    legacy/fire_builder_bot.py:106-111
    legacy/dividend_bot.py:102-104
    legacy/backtest.py:142-147
"""

from __future__ import annotations

from .models import Allocation, Regime


def allocation_split(
    budget: float,
    regime: Regime,
    *,
    bull_core: float = 0.40,
    bull_alpha: float = 0.60,
    bear_core: float = 0.80,
    bear_alpha: float = 0.20,
) -> Allocation:
    """Bull-or-bear core/alpha split. Percentages must sum to 1.0 per side."""
    if regime == "bull":
        core_pct, alpha_pct = bull_core, bull_alpha
    else:
        core_pct, alpha_pct = bear_core, bear_alpha
    return Allocation(
        core_inr=budget * core_pct,
        alpha_inr=budget * alpha_pct,
        core_pct=core_pct,
        alpha_pct=alpha_pct,
        regime=regime,
    )


def apply_position_sizing(
    equity: float,
    risk_per_share: float,
    price: float,
    *,
    risk_pct: float = 0.01,
    max_capital_pct: float = 0.20,
) -> int:
    """Compute share quantity for a target risk budget.

    Risks `risk_pct` of equity (default 1%) by sizing so that
    `qty * risk_per_share == equity * risk_pct`. Cap at `max_capital_pct` of
    equity (default 20%) so a low-volatility position can't blow position limits.

    Returns 0 if any input is unusable (e.g. zero risk-per-share, negative price).
    """
    if equity <= 0 or price <= 0 or risk_per_share <= 0:
        return 0

    risk_budget = equity * risk_pct
    optimal_qty = int(risk_budget // risk_per_share)
    if optimal_qty <= 0:
        return 0

    capital_cap = equity * max_capital_pct
    if optimal_qty * price > capital_cap:
        optimal_qty = int(capital_cap // price)

    return max(optimal_qty, 0)
