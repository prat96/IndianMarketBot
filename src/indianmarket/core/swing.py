"""Swing-setup scoring — the V4.0 institutional version.

Consolidates two near-duplicates:
    legacy/swing_trade_bot.py:55-135  (`analyze_stock`, hard targets)
    legacy/paper_trader.py:158-248    (`analyze_stock`, ATR stops + RS filter)

This is the V4.0 logic from paper_trader: relative-strength filter against
Nifty, ATR-based stop, optional hard target (for the one-shot screener).
"""

from __future__ import annotations

import pandas as pd

from .indicators import precalc_technicals, sma
from .models import SwingSetup


def swing_setup(
    ohlcv: pd.DataFrame,
    nifty_close: pd.Series | None = None,
    *,
    ticker: str | None = None,
    atr_multiplier: float = 2.5,
    min_score: int = 4,
    max_risk_pct: float = 0.15,
    rr_target: float | None = None,
    precalc: bool = True,
) -> SwingSetup | None:
    """Evaluate an OHLCV frame for a swing-long setup.

    Args:
        ohlcv: DataFrame with Open/High/Low/Close/Volume indexed by date.
            If precalc is True, indicators are computed here; otherwise the
            frame must already have RSI, MACD_Hist, SMA_20/50/200, ATR,
            Avg_Vol_20, Prev_* columns from `indicators.precalc_technicals`.
        nifty_close: Optional Nifty 50 Close series for the relative-strength
            filter. If None, the RS filter is skipped (caller has only the
            single stock).
        ticker: Symbol for the resulting SwingSetup; defaults to ohlcv.name.
        atr_multiplier: Stop-loss distance in ATRs (default 2.5).
        min_score: Minimum aggregate score for a valid setup (default 4).
        max_risk_pct: Reject setups where stop distance > this fraction of
            price (default 15%).
        rr_target: If set, attach a hard target at `risk * rr_target` above entry.
        precalc: When False, assumes indicators are already attached.

    Returns:
        SwingSetup if setup passes all filters; None otherwise.
    """
    df = precalc_technicals(ohlcv) if precalc else ohlcv
    if len(df) < 200:
        return None

    name = ticker or getattr(ohlcv, "name", None) or "?"
    row = df.iloc[-1]

    # Required indicator presence
    required = ("SMA_50", "SMA_200", "ATR", "RSI", "MACD_Hist",
                "SMA_20", "Prev_SMA_20", "Prev_RSI", "Prev_MACD_Hist", "Avg_Vol_20")
    if any(pd.isna(row.get(k)) for k in required):
        return None

    price = float(row["Close"])
    prev_close = float(df["Close"].iloc[-2])
    atr_val = float(row["ATR"])

    # --- Hard filters --------------------------------------------------------
    if price < row["SMA_50"] or price < row["SMA_200"]:
        return None

    # Relative Strength: must be outperforming Nifty 50-DMA-of-RS
    if nifty_close is not None and not nifty_close.empty:
        aligned = nifty_close.reindex(df.index, method="ffill")
        rs = df["Close"] / aligned
        rs_sma20 = sma(rs, 20)
        if pd.isna(rs_sma20.iloc[-1]) or rs.iloc[-1] < rs_sma20.iloc[-1]:
            return None

    # --- Scoring -------------------------------------------------------------
    score = 0
    triggers: list[str] = []

    if row["MACD_Hist"] > 0 and row["Prev_MACD_Hist"] <= 0:
        score += 3
        triggers.append("MACD bullish cross")

    if row["RSI"] > 50 and row["Prev_RSI"] <= 50:
        score += 2
        triggers.append("RSI > 50 bounce")

    if price > row["SMA_20"] and prev_close <= row["Prev_SMA_20"]:
        score += 3
        triggers.append("20-DMA breakout")

    if row["Volume"] > row["Avg_Vol_20"] * 1.5:
        score += 2
        triggers.append("Volume > 1.5× avg")

    if score < min_score:
        return None

    # --- Risk / stop ---------------------------------------------------------
    risk_per_share = atr_multiplier * atr_val
    if (risk_per_share / price) > max_risk_pct:
        return None

    stop_loss = price - risk_per_share
    target = None if rr_target is None else price + risk_per_share * rr_target

    return SwingSetup(
        ticker=name,
        price=price,
        score=score,
        stop_loss=stop_loss,
        atr=atr_val,
        risk_per_share=risk_per_share,
        triggers=tuple(triggers),
        target=target,
    )
