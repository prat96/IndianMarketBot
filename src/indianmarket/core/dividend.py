"""Dividend-snowball scoring.

Replaces legacy/dividend_bot.py:37-89 (`score_stock`).

Inputs come from yfinance .info dicts — keys we use:
    dividendRate, twoHundredDayAverage, trailingPE, payoutRatio, beta
The wrapper that fetches these lives in data/yahoo.py; the scoring itself is
pure: pass in plain dicts and floats.
"""

from __future__ import annotations

from .models import DividendScore


def score_dividend(
    info: dict,
    price: float,
    ticker: str | None = None,
    *,
    min_yield_pct: float = 3.0,
    max_yield_pct: float = 18.0,
    max_pe: float = 40.0,
    max_payout: float = 0.95,
    high_payout_warn: float = 0.75,
) -> DividendScore:
    """Score a stock for the dividend-snowball satellite bucket.

    Filters (any fail -> score=0):
      * has dividendRate, price > 0
      * price >= 200-DMA   (the "no value trap" filter)
      * yield in [min_yield_pct, max_yield_pct]
      * PE in (0, max_pe]  (profitable, not bubble)
      * payoutRatio <= max_payout

    Scoring (when all filters pass):
      base = yield_pct
      + bonus for beta < 1.0 (rewards low-volatility)
      - penalty for beta > 1.0
      - extra penalty when payout > high_payout_warn (sustainability concern)
    """
    name = ticker or info.get("symbol") or "?"

    div_rate = info.get("dividendRate") or 0
    if not div_rate or price <= 0:
        return DividendScore(name, 0.0, 0.0, False, "No dividend data")

    yield_pct = (div_rate / price) * 100

    dma_200 = info.get("twoHundredDayAverage") or 0
    if dma_200 and price < dma_200:
        return DividendScore(name, 0.0, yield_pct, False, "Below 200-DMA (downtrend)")

    if yield_pct < min_yield_pct:
        return DividendScore(name, 0.0, yield_pct, False, f"Yield <{min_yield_pct}%")
    if yield_pct > max_yield_pct:
        return DividendScore(name, 0.0, yield_pct, False, "Yield too high (value trap risk)")

    pe = info.get("trailingPE")
    if pe is None or pe <= 0 or pe > max_pe:
        return DividendScore(name, 0.0, yield_pct, False, "Unprofitable or overvalued")

    payout = info.get("payoutRatio") or 0
    if payout > max_payout:
        return DividendScore(name, 0.0, yield_pct, False, f"Payout >{max_payout * 100:.0f}%")

    beta = info.get("beta")
    if beta is None:
        beta = 1.0

    score = yield_pct
    if beta < 1.0:
        score += (1.0 - beta) * 2
    else:
        score -= (beta - 1.0) * 2

    if payout > high_payout_warn:
        score -= (payout - high_payout_warn) * 10

    return DividendScore(name, score, yield_pct, True, "Pass")
