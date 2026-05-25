"""Tests for indianmarket.core.regime."""

from __future__ import annotations

import numpy as np
import pandas as pd

from indianmarket.core.regime import market_breadth, nifty_regime


def _nifty_series(values: list[float]) -> pd.Series:
    idx = pd.date_range("2024-01-01", periods=len(values), freq="B")
    return pd.Series(values, index=idx)


def test_regime_bull_when_above_dma():
    # 250 flat at 100, then surge to 200 — current price is way above 200-DMA.
    series = _nifty_series([100.0] * 250 + [200.0] * 10)
    assert nifty_regime(series) == "bull"


def test_regime_bear_when_below_dma():
    series = _nifty_series([200.0] * 250 + [80.0] * 10)
    assert nifty_regime(series) == "bear"


def test_regime_fail_open_on_empty():
    assert nifty_regime(pd.Series(dtype=float)) == "bull"


def test_regime_fail_open_when_dma_nan():
    """If we don't have 200 bars yet, return bull rather than refuse trading."""
    series = _nifty_series([100.0] * 50)
    # SMA-200 will be NaN throughout.
    assert nifty_regime(series) == "bull"


def test_breadth_above_threshold_returns_true():
    """If most of the universe is above its 50-DMA, breadth is bullish."""
    n = 60
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    # 8 of 10 tickers trade well above their 50-DMA in the last bar.
    bullish = pd.DataFrame(
        {f"T{i}": np.linspace(100, 150, n) for i in range(8)}, index=idx,
    )
    bearish = pd.DataFrame(
        {f"T{i}": np.linspace(100, 80, n) for i in range(8, 10)}, index=idx,
    )
    df = pd.concat([bullish, bearish], axis=1)
    assert market_breadth(df, threshold=0.40) is True


def test_breadth_below_threshold_returns_false():
    """If only 1 of 10 are above their 50-DMA, breadth fails."""
    n = 60
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    bullish = pd.DataFrame({"T0": np.linspace(100, 150, n)}, index=idx)
    bearish = pd.DataFrame(
        {f"T{i}": np.linspace(100, 80, n) for i in range(1, 10)}, index=idx,
    )
    df = pd.concat([bullish, bearish], axis=1)
    assert market_breadth(df, threshold=0.40) is False
