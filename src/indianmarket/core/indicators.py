"""Technical indicators.

Pure pandas functions extracted from the legacy bots. Every function takes
Series/DataFrame in and returns Series/DataFrame out — no I/O.

Sources (now consolidated):
    legacy/paper_trader.py:102-108     calculate_rsi
    legacy/paper_trader.py:110-116     calculate_macd
    legacy/swing_backtest.py:53-85     precalculate_technicals + ATR
    legacy/paper_trader.py:93-99       sparkline
"""

from __future__ import annotations

import pandas as pd


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """Wilder-style RSI computed via simple rolling mean of gains/losses."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Standard MACD. Returns (macd_line, signal_line, histogram)."""
    exp1 = close.ewm(span=fast, adjust=False).mean()
    exp2 = close.ewm(span=slow, adjust=False).mean()
    macd_line = exp1 - exp2
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window).mean()


def atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int = 14,
) -> pd.Series:
    """Average True Range (Wilder), simple-moving-average smoothing."""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=window).mean()


def precalc_technicals(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """Append RSI, MACD, SMA(20/50/200), ATR, Avg Vol, prev-shifts to an OHLCV frame.

    Input must have columns: Open, High, Low, Close, Volume.
    Returns the same frame with added columns (in-place semantics avoided —
    returns a shallow-copied frame).
    """
    df = ohlcv.copy()
    close, high, low, vol = df["Close"], df["High"], df["Low"], df["Volume"]

    df["RSI"] = rsi(close, 14)
    macd_line, macd_signal, macd_hist = macd(close)
    df["MACD"] = macd_line
    df["MACD_Signal"] = macd_signal
    df["MACD_Hist"] = macd_hist

    df["SMA_20"] = sma(close, 20)
    df["SMA_50"] = sma(close, 50)
    df["SMA_200"] = sma(close, 200)
    df["Avg_Vol_20"] = vol.rolling(window=20).mean()
    df["ATR"] = atr(high, low, close, 14)
    df["High_52W"] = high.rolling(window=252).max()

    df["Prev_Close"] = close.shift(1)
    df["Prev_RSI"] = df["RSI"].shift(1)
    df["Prev_MACD_Hist"] = df["MACD_Hist"].shift(1)
    df["Prev_SMA_20"] = df["SMA_20"].shift(1)
    return df


def sparkline(values: list[float] | pd.Series, width: int = 40) -> str:
    """Unicode sparkline. Returns an empty string for empty input."""
    seq = list(values)
    if not seq:
        return ""
    seq = seq[-width:]
    bars = " ▂▃▄▅▆▇█"
    lo, hi = min(seq), max(seq)
    if lo == hi:
        return bars[3] * len(seq)
    return "".join(bars[int((v - lo) / (hi - lo) * 7)] for v in seq)
