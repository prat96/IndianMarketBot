"""Tests for indianmarket.core.projection."""

from __future__ import annotations

import pytest

from indianmarket.core.projection import project_fire


def test_zero_return_no_inflation_just_sums_sip():
    r = project_fire(
        years=1, monthly_sip_eur=100, target_expense_eur=10_000,
        swr_pct=4.0, inr_return_pct=0, inr_depreciation_pct=0, eu_inflation_pct=0,
    )
    assert len(r.snapshots) == 1
    snap = r.snapshots[0]
    assert snap.invested == pytest.approx(1200)
    assert snap.nominal_value == pytest.approx(1200)
    assert snap.real_value == pytest.approx(1200)
    assert r.effective_eur_return == pytest.approx(0.0)


def test_effective_return_formula():
    r = project_fire(
        years=1, monthly_sip_eur=1.0, target_expense_eur=1e9,
        inr_return_pct=20.0, inr_depreciation_pct=4.0, eu_inflation_pct=0,
    )
    # (1.20 / 1.04) - 1 = 0.1538...
    assert r.effective_eur_return == pytest.approx(0.153846, abs=1e-4)


def test_snapshot_count_matches_years():
    r = project_fire(
        years=15, monthly_sip_eur=500, target_expense_eur=2500,
    )
    assert len(r.snapshots) == 15
    assert r.snapshots[0].year == 1
    assert r.snapshots[-1].year == 15


def test_fire_eventually_achieved_with_good_returns():
    """A 30-year run at default 16% INR return should hit FIRE before year 30."""
    r = project_fire(years=30, monthly_sip_eur=500, target_expense_eur=2500)
    assert r.fire_month is not None
    assert 0 < r.fire_month <= 360


def test_fire_not_achieved_with_low_sip():
    """€10/month against €5000 expenses will never hit FIRE."""
    r = project_fire(
        years=10, monthly_sip_eur=10, target_expense_eur=5000,
        inr_return_pct=10.0, inr_depreciation_pct=2.0, eu_inflation_pct=2.0,
    )
    assert r.fire_month is None
    for snap in r.snapshots:
        assert not snap.fire_achieved
