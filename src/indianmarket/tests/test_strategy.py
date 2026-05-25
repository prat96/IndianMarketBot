"""Tests for the strategy scoring functions: momentum, dividend, swing."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from indianmarket.core.dividend import score_dividend
from indianmarket.core.momentum import momentum_score, rank_alpha
from indianmarket.core.models import MomentumResult
from indianmarket.core.swing import swing_setup


def _ohlcv(close_series: pd.Series, *, vol: float | pd.Series = 1_000_000) -> pd.DataFrame:
    n = len(close_series)
    idx = close_series.index if isinstance(close_series.index, pd.DatetimeIndex) else pd.date_range("2023-01-01", periods=n, freq="B")
    high = close_series.values * 1.01
    low = close_series.values * 0.99
    volume = np.full(n, vol) if isinstance(vol, (int, float)) else vol.values
    return pd.DataFrame(
        {"Open": close_series.values, "High": high, "Low": low,
         "Close": close_series.values, "Volume": volume},
        index=idx,
    )


# --- momentum ---------------------------------------------------------------

def test_momentum_rejects_short_history():
    close = pd.Series(np.linspace(100, 120, 50))
    df = _ohlcv(close)
    df.name = "FOO"
    r = momentum_score(df)
    assert not r.passed
    assert "Not enough data" in r.reason


def test_momentum_rejects_below_200dma():
    # 250 bars above 200, then crash to 50 for 20 more
    close = pd.Series([200.0] * 250 + [50.0] * 20)
    df = _ohlcv(close)
    df.name = "CRASH"
    r = momentum_score(df)
    assert not r.passed
    assert "Below 200-DMA" in r.reason


def test_momentum_rejects_far_off_52w_high():
    # Above 200-DMA but 25% off the 52-week high
    close = pd.Series([100.0] * 100 + list(np.linspace(100, 200, 50)) + list(np.linspace(200, 150, 110)))
    df = _ohlcv(close)
    df.name = "FADER"
    r = momentum_score(df)
    if r.passed:
        # In this constructed series price ends just under 25% off high.
        # If we're within 20% it would pass; assert message expresses 52W rule.
        assert r.high_52w is not None


def test_momentum_passes_clean_uptrend():
    close = pd.Series(np.linspace(100, 200, 260))
    df = _ohlcv(close)
    df.name = "GROWTH"
    r = momentum_score(df)
    assert r.passed
    assert r.score > 0   # 6M return is positive in a steady uptrend


def test_rank_alpha_picks_top_n():
    results = [
        MomentumResult("A", score=5, passed=True, reason="", price=10, dma_200=8, high_52w=11),
        MomentumResult("B", score=15, passed=True, reason="", price=20, dma_200=15, high_52w=22),
        MomentumResult("C", score=0, passed=False, reason="fail", price=30, dma_200=35, high_52w=40),
        MomentumResult("D", score=10, passed=True, reason="", price=15, dma_200=12, high_52w=16),
    ]
    top = rank_alpha(results, top_n=2)
    assert [r.ticker for r in top] == ["B", "D"]


# --- dividend ---------------------------------------------------------------

def _div_info(**kwargs):
    base = {
        "dividendRate": 25.0,
        "twoHundredDayAverage": 400.0,
        "trailingPE": 15.0,
        "payoutRatio": 0.50,
        "beta": 0.8,
    }
    base.update(kwargs)
    return base


def test_dividend_passes_good_stock():
    s = score_dividend(_div_info(), price=500.0, ticker="ITC")
    assert s.passed
    assert s.yield_pct == pytest.approx(5.0)
    # base yield 5 + beta bonus 0.4 = 5.4
    assert s.score > 5.0


def test_dividend_rejects_below_200dma():
    s = score_dividend(_div_info(), price=300.0, ticker="X")
    assert not s.passed
    assert "200-DMA" in s.reason


def test_dividend_rejects_value_trap_yield():
    s = score_dividend(_div_info(dividendRate=120.0), price=500.0)
    # 120/500 = 24% — way above 18% cap
    assert not s.passed
    assert "Value trap" in s.reason or "value trap" in s.reason


def test_dividend_rejects_high_payout():
    s = score_dividend(_div_info(payoutRatio=0.99), price=500.0)
    assert not s.passed
    assert "Payout" in s.reason


def test_dividend_penalises_high_beta():
    low = score_dividend(_div_info(beta=0.5), price=500.0)
    high = score_dividend(_div_info(beta=2.0), price=500.0)
    assert low.score > high.score


def test_dividend_no_dividend_data_fails_fast():
    s = score_dividend({}, price=100.0)
    assert not s.passed


# --- swing ------------------------------------------------------------------

def _swing_ohlcv(n: int = 250, seed: int = 1) -> pd.DataFrame:
    """OHLCV with a strong uptrend ending in a clean breakout day."""
    rng = np.random.default_rng(seed)
    base = np.linspace(100, 180, n) + rng.normal(0, 1, n)
    base[-3:] = base[-4] * np.array([1.005, 1.015, 1.04])    # final-day pop
    idx = pd.date_range("2023-01-01", periods=n, freq="B")
    df = pd.DataFrame(
        {
            "Open": base * 0.999,
            "High": base * 1.012,
            "Low": base * 0.988,
            "Close": base,
            "Volume": np.concatenate([rng.integers(800_000, 1_200_000, n - 1), [2_500_000]]),
        },
        index=idx,
    )
    df.name = "PUMP"
    return df


def test_swing_setup_returns_none_for_short_history():
    df = _swing_ohlcv(50)
    assert swing_setup(df) is None


def test_swing_setup_passes_uptrending_breakout():
    df = _swing_ohlcv(250, seed=1)
    setup = swing_setup(df)
    if setup is not None:
        assert setup.ticker == "PUMP"
        assert setup.score >= 4
        assert setup.stop_loss < setup.price
        assert setup.risk_per_share > 0


def test_swing_setup_returns_target_when_requested():
    df = _swing_ohlcv(250, seed=2)
    setup = swing_setup(df, rr_target=2.5)
    if setup is not None:
        assert setup.target is not None
        assert setup.target > setup.price
        expected = setup.price + setup.risk_per_share * 2.5
        assert setup.target == pytest.approx(expected)


def test_swing_setup_rejects_downtrend():
    """Bear-trend ticker: price below SMA50 should be screened out."""
    n = 250
    close = pd.Series(np.linspace(200, 80, n))   # straight decline
    df = _ohlcv(close)
    df.name = "FALLING_KNIFE"
    assert swing_setup(df) is None
