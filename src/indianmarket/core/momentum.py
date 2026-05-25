"""Momentum scoring — the filter that kept the legacy bots out of value traps.

Replaces legacy/fire_builder_bot.py:52-79 (`score_momentum`).
"""

from __future__ import annotations

import pandas as pd

from .indicators import sma
from .models import MomentumResult


def momentum_score(
    price_df: pd.DataFrame,
    *,
    fifty_two_week_floor: float = 0.80,
    dma_window: int = 200,
    momentum_window_days: int = 126,
) -> MomentumResult:
    """Score a single ticker on simple uptrend criteria.

    Filters:
      1. Price > N-DMA (default 200) — uptrend
      2. Price within (1 - fifty_two_week_floor) of the 52-week high
         (default: skip stocks > 20% off their high)

    If both pass, the score is the 6-month return (in %).
    Caller is expected to sort/rank multiple results by .score.
    """
    if price_df.empty:
        return MomentumResult(
            ticker=getattr(price_df, "name", "?"),
            score=0.0, passed=False, reason="No data",
            price=0.0, dma_200=None, high_52w=None,
        )

    ticker = getattr(price_df, "name", None) or "?"
    close = price_df["Close"]
    if len(close) < dma_window:
        return MomentumResult(
            ticker=ticker, score=0.0, passed=False,
            reason=f"Not enough data ({len(close)} < {dma_window})",
            price=float(close.iloc[-1]), dma_200=None, high_52w=None,
        )

    price = float(close.iloc[-1])
    dma = float(sma(close, dma_window).iloc[-1])
    high_52 = float(close.iloc[-252:].max()) if len(close) >= 252 else float(close.max())

    if price < dma:
        return MomentumResult(
            ticker=ticker, score=0.0, passed=False, reason="Below 200-DMA",
            price=price, dma_200=dma, high_52w=high_52,
        )
    if price < high_52 * fifty_two_week_floor:
        return MomentumResult(
            ticker=ticker, score=0.0, passed=False,
            reason="More than 20% off 52-week high",
            price=price, dma_200=dma, high_52w=high_52,
        )

    if len(close) > momentum_window_days:
        price_n_ago = float(close.iloc[-momentum_window_days])
    else:
        price_n_ago = float(close.iloc[0])
    score = ((price - price_n_ago) / price_n_ago) * 100 if price_n_ago > 0 else 0.0

    return MomentumResult(
        ticker=ticker, score=score, passed=True, reason="Pass",
        price=price, dma_200=dma, high_52w=high_52,
    )


def rank_alpha(results: list[MomentumResult], top_n: int = 3) -> list[MomentumResult]:
    """Filter to passers, sort by score desc, return top N."""
    passed = [r for r in results if r.passed]
    passed.sort(key=lambda r: r.score, reverse=True)
    return passed[:top_n]
