"""Market regime detection (Nifty 200-DMA + universe breadth).

Replaces the regime checks scattered across:
    legacy/backtest.py:138-140
    legacy/fire_builder_bot.py:88-95
    legacy/paper_trader.py:129-156
    legacy/swing_backtest.py:150-170
    legacy/swing_trade_bot.py:151-158
"""

from __future__ import annotations

import pandas as pd

from .models import Regime


def nifty_regime(
    nifty_close: pd.Series,
    ts: pd.Timestamp | None = None,
    *,
    dma_window: int = 200,
) -> Regime:
    """Classify the market as 'bull' or 'bear' from Nifty vs its N-DMA.

    If `ts` is None, uses the last bar. If `ts` is given but absent from the
    index, ffill is applied (defends against weekends/holidays).
    """
    if nifty_close.empty:
        return "bull"           # fail-open: don't refuse trades if we have no data
    dma = nifty_close.rolling(window=dma_window).mean()

    if ts is None:
        price = nifty_close.iloc[-1]
        ma = dma.iloc[-1]
    else:
        price = nifty_close.reindex([ts], method="ffill").iloc[0]
        ma = dma.reindex([ts], method="ffill").iloc[0]

    if pd.isna(ma) or pd.isna(price):
        return "bull"
    return "bull" if price > ma else "bear"


def market_breadth(
    universe_close: pd.DataFrame,
    ts: pd.Timestamp | None = None,
    *,
    window: int = 50,
    threshold: float = 0.40,
) -> bool:
    """True iff >`threshold` fraction of the universe trades above its `window`-DMA.

    `universe_close` is a DataFrame indexed by date with one column per ticker
    (Close series for each). NaNs are ignored.
    """
    if universe_close.empty:
        return True
    dma = universe_close.rolling(window=window).mean()

    if ts is None:
        last_price = universe_close.iloc[-1]
        last_dma = dma.iloc[-1]
    else:
        last_price = universe_close.reindex([ts], method="ffill").iloc[0]
        last_dma = dma.reindex([ts], method="ffill").iloc[0]

    valid = last_price.notna() & last_dma.notna()
    if valid.sum() == 0:
        return True
    above = int((last_price[valid] > last_dma[valid]).sum())
    return bool((above / int(valid.sum())) >= threshold)
