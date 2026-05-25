"""Forward-looking FIRE projection (cross-border EUR resident -> INR portfolio).

Replaces legacy/project.py:67-110. Pure math, no I/O.
"""

from __future__ import annotations

from .models import ProjectionResult, ProjectionSnapshot


def project_fire(
    years: int,
    monthly_sip_eur: float,
    target_expense_eur: float,
    *,
    swr_pct: float = 3.5,
    inr_return_pct: float = 16.0,
    inr_depreciation_pct: float = 3.0,
    eu_inflation_pct: float = 2.5,
) -> ProjectionResult:
    """Project a monthly SIP against cross-border FIRE math.

    The effective EUR return is (1+INR_return) / (1+INR_depreciation) - 1.
    A snapshot is captured at the end of each year; FIRE is "achieved" the
    first month the SWR-implied monthly income exceeds the inflated target
    expense.
    """
    eff = ((1 + inr_return_pct / 100) / (1 + inr_depreciation_pct / 100)) - 1
    monthly_return = eff / 12
    monthly_swr = (swr_pct / 100) / 12

    total_months = years * 12
    portfolio = 0.0
    invested = 0.0
    fire_month: int | None = None

    snapshots: list[ProjectionSnapshot] = []

    for m in range(1, total_months + 1):
        inflated_expense = target_expense_eur * ((1 + eu_inflation_pct / 100) ** (m / 12))
        safe_withdrawal = portfolio * monthly_swr

        if fire_month is None and safe_withdrawal >= inflated_expense:
            fire_month = m

        portfolio += portfolio * monthly_return
        portfolio += monthly_sip_eur
        invested += monthly_sip_eur

        if m % 12 == 0:
            year = m // 12
            real_value = portfolio / ((1 + eu_inflation_pct / 100) ** year)
            snapshots.append(ProjectionSnapshot(
                year=year,
                invested=invested,
                nominal_value=portfolio,
                real_value=real_value,
                safe_withdrawal=safe_withdrawal,
                inflated_expense=inflated_expense,
                fire_achieved=fire_month is not None and fire_month <= m,
            ))

    return ProjectionResult(
        snapshots=snapshots,
        fire_month=fire_month,
        effective_eur_return=eff,
    )
