"""Tests for indianmarket.core.sizing."""

from __future__ import annotations

import pytest

from indianmarket.core.sizing import allocation_split, apply_position_sizing


# --- allocation_split -------------------------------------------------------

def test_bull_split_is_40_60():
    alloc = allocation_split(100_000, "bull")
    assert alloc.core_pct == 0.40
    assert alloc.alpha_pct == 0.60
    assert alloc.core_inr == 40_000
    assert alloc.alpha_inr == 60_000
    assert alloc.regime == "bull"


def test_bear_split_is_80_20():
    alloc = allocation_split(100_000, "bear")
    assert alloc.core_pct == 0.80
    assert alloc.alpha_pct == 0.20
    assert alloc.core_inr == 80_000
    assert alloc.alpha_inr == 20_000


def test_split_sums_to_budget():
    for budget in (1_000, 50_000, 12_345.67):
        for regime in ("bull", "bear"):
            a = allocation_split(budget, regime)
            assert a.core_inr + a.alpha_inr == pytest.approx(budget)


# --- apply_position_sizing --------------------------------------------------

def test_sizing_risks_exactly_one_percent():
    """If risk_per_share fits cleanly into 1% of equity, qty hits the budget."""
    # 1% of 1,000,000 = 10,000. Risk per share = 50 -> 200 shares.
    qty = apply_position_sizing(
        equity=1_000_000, risk_per_share=50, price=1000,
    )
    assert qty == 200


def test_sizing_caps_at_max_capital_pct():
    """High-price low-volatility stock can't exceed 20% of equity."""
    # equity=1M, risk_per_share=10 → optimal_qty=1000.
    # 1000 * price 5000 = 5M, way over 20% cap (200k).
    # Cap: 200_000 // 5000 = 40 shares.
    qty = apply_position_sizing(
        equity=1_000_000, risk_per_share=10, price=5000,
    )
    assert qty == 40


def test_sizing_returns_zero_on_bad_inputs():
    assert apply_position_sizing(0, 50, 100) == 0
    assert apply_position_sizing(1_000_000, 0, 100) == 0
    assert apply_position_sizing(1_000_000, 50, 0) == 0
    assert apply_position_sizing(-1, 50, 100) == 0


def test_sizing_uses_custom_risk_pct():
    """0.5% risk halves the quantity vs default 1%."""
    qty_1 = apply_position_sizing(1_000_000, 50, 1000, risk_pct=0.01)
    qty_05 = apply_position_sizing(1_000_000, 50, 1000, risk_pct=0.005)
    assert qty_1 == 200
    assert qty_05 == 100


def test_sizing_floor_at_zero_when_risk_too_large():
    """If 1% of equity can't even afford 1 share at this volatility, qty=0."""
    qty = apply_position_sizing(equity=10_000, risk_per_share=200, price=500)
    # 1% of 10k = 100. 100 // 200 = 0 shares.
    assert qty == 0
