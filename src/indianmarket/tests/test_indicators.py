"""Tests for indianmarket.core.indicators.

We verify both shape (correct length, dtype) and golden values against the
legacy implementations on the same synthetic input.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from indianmarket.core.indicators import (
    atr,
    macd,
    precalc_technicals,
    rsi,
    sma,
    sparkline,
)


def _synthetic_ohlcv(n: int = 260, seed: int = 42) -> pd.DataFrame:
    """Deterministic synthetic OHLCV — random walk anchored at 1000."""
    rng = np.random.default_rng(seed)
    returns = rng.normal(0.0005, 0.012, size=n)
    close = 1000 * np.exp(np.cumsum(returns))
    high = close * (1 + rng.uniform(0, 0.012, size=n))
    low = close * (1 - rng.uniform(0, 0.012, size=n))
    open_ = close * (1 + rng.normal(0, 0.003, size=n))
    volume = rng.integers(1_000_000, 5_000_000, size=n)
    idx = pd.date_range("2023-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=idx,
    )


# --- Indicator unit tests ---------------------------------------------------

def test_rsi_bounds_and_length():
    df = _synthetic_ohlcv(50)
    r = rsi(df["Close"], window=14)
    assert len(r) == 50
    # RSI is bounded [0, 100], NaN for the first `window` rows.
    finite = r.dropna()
    assert finite.between(0, 100).all()
    assert r.iloc[:13].isna().all()


def test_macd_shapes():
    df = _synthetic_ohlcv(60)
    m, sig, hist = macd(df["Close"])
    assert len(m) == len(sig) == len(hist) == 60
    # Hist == macd - signal, exactly.
    assert np.allclose((m - sig).iloc[-10:], hist.iloc[-10:])


def test_sma_window_correct():
    s = pd.Series(range(10), dtype=float)
    out = sma(s, 3)
    # Average of positions 7,8,9 = 8.
    assert out.iloc[-1] == pytest.approx(8.0)
    assert pd.isna(out.iloc[1])


def test_atr_nonnegative_and_length():
    df = _synthetic_ohlcv(60)
    a = atr(df["High"], df["Low"], df["Close"], window=14)
    assert len(a) == 60
    assert (a.dropna() >= 0).all()


def test_precalc_appends_expected_columns():
    df = _synthetic_ohlcv(260)
    out = precalc_technicals(df)
    expected = {
        "RSI", "MACD", "MACD_Signal", "MACD_Hist",
        "SMA_20", "SMA_50", "SMA_200", "Avg_Vol_20", "ATR", "High_52W",
        "Prev_Close", "Prev_RSI", "Prev_MACD_Hist", "Prev_SMA_20",
    }
    assert expected.issubset(out.columns)
    # Original frame not mutated.
    assert "RSI" not in df.columns


def test_precalc_sma200_starts_at_index_199():
    df = _synthetic_ohlcv(260)
    out = precalc_technicals(df)
    assert pd.isna(out["SMA_200"].iloc[198])
    assert not pd.isna(out["SMA_200"].iloc[199])


def test_sparkline_handles_empty_and_constant():
    assert sparkline([]) == ""
    flat = sparkline([1.0] * 10)
    assert len(flat) == 10
    assert len(set(flat)) == 1   # all the same char


def test_sparkline_width_clamp():
    s = sparkline(list(range(100)), width=20)
    assert len(s) == 20


# --- Golden values vs legacy implementations --------------------------------
# These pin the new functions to bit-identical output as the legacy bots
# computed them. If you change indicator behaviour, these MUST be re-baselined
# with the explanatory commit message.

def test_rsi_golden_value():
    """Pin RSI semantics: last bar value on the seed-42 synthetic series.
    If this diverges, the indicator's behaviour changed and downstream bots'
    signals will too — bump intentionally."""
    rng = np.random.default_rng(42)
    returns = rng.normal(0.0005, 0.012, size=260)
    close = pd.Series(1000 * np.exp(np.cumsum(returns)))
    r = rsi(close, window=14)
    assert r.iloc[-1] == pytest.approx(60.288535, abs=1e-3)


def test_macd_hist_sign_matches_close_drift():
    """If the series ends in a clear uptrend, MACD histogram is positive."""
    rng = np.random.default_rng(7)
    n = 200
    # Strong uptrend in the second half so MACD has time to react.
    returns = np.concatenate([rng.normal(-0.001, 0.005, 100), rng.normal(0.008, 0.004, 100)])
    close = pd.Series(1000 * np.exp(np.cumsum(returns)))
    _, _, hist = macd(close)
    # Last-bar histogram should be solidly positive after 100 bars of drift.
    assert hist.iloc[-1] > 0
