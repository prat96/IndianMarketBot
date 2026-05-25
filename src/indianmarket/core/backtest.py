"""Backtest engines — dividend SIP and swing V4.0.

Both functions are pure: caller injects all market data, we return a
BacktestResult dataclass. No yfinance, no I/O, no Rich.

Source extraction:
    run_dividend_backtest  <- legacy/backtest.py:47-298
    run_swing_backtest     <- legacy/swing_backtest.py:87-353

The inner per-day loops stay monolithic by design (see refactor plan §H).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Mapping

import pandas as pd

from .indicators import atr as atr_fn
from .indicators import precalc_technicals, sma
from .models import (
    BacktestResult,
    DividendBacktestConfig,
    SwingBacktestConfig,
    Trade,
)
from .regime import market_breadth, nifty_regime
from .sizing import allocation_split, apply_position_sizing

try:
    from pyxirr import xirr as _xirr
except ImportError:                                            # pragma: no cover
    _xirr = None


# ---------------------------------------------------------------------------
# Dividend SIP backtest (Route 1: snowball)
# ---------------------------------------------------------------------------

def run_dividend_backtest(
    prices: Mapping[str, pd.DataFrame],
    nifty: pd.DataFrame,
    eur_inr: pd.Series,
    core_tickers: list[str],
    alpha_tickers: list[str],
    cfg: DividendBacktestConfig = DividendBacktestConfig(),
) -> BacktestResult:
    """SIP-style monthly accumulator with bull/bear regime tilt.

    Args:
        prices: ticker -> OHLCV DataFrame with Close + Dividends columns.
        nifty: ^NSEI history (Close + computed 200-DMA via SMA).
        eur_inr: Close series for EURINR=X, daily.
        core_tickers: tickers treated as the Core bucket (ETFs, mega caps).
        alpha_tickers: tickers eligible for the Alpha bucket (high-yield equities).
        cfg: DividendBacktestConfig.

    Buys on the last trading day of each calendar month. Reinvests dividends
    on their ex-date (DRIP).
    """
    end_date = nifty.index.max()
    start_backtest = end_date - pd.DateOffset(years=cfg.years)

    nifty_close = nifty["Close"]
    nifty_dma = sma(nifty_close, 200)

    backtest_dates = nifty.index[nifty.index >= start_backtest]
    if backtest_dates.empty:
        return _empty_backtest_result(invested=0.0)

    # Last trading day of each (year, month) — that's our SIP day.
    sip_days = set(
        pd.Series(backtest_dates).groupby([backtest_dates.year, backtest_dates.month]).max()
    )

    # FX reindexed onto backtest calendar, forward-filled then back-filled
    fx = eur_inr.reindex(backtest_dates, method="ffill").bfill()

    portfolio: dict[str, float] = {t: 0.0 for t in list(core_tickers) + list(alpha_tickers)}
    cash_inr = 0.0
    total_dividends = 0.0

    cf_dates: list[datetime] = []
    cf_amounts_eur: list[float] = []

    for day in backtest_dates:
        # Dividend reinvestment
        for t, df in prices.items():
            if day not in df.index or "Dividends" not in df.columns:
                continue
            div = df.loc[day, "Dividends"]
            if div > 0 and portfolio.get(t, 0) > 0:
                amount = div * portfolio[t]
                cash_inr += amount
                total_dividends += amount

        if day not in sip_days:
            continue

        current_fx = float(fx.loc[day]) if not pd.isna(fx.loc[day]) else 90.0
        sip_inr = cfg.monthly_sip_eur * current_fx
        available_cash = sip_inr + cash_inr

        cf_dates.append(day.to_pydatetime())
        cf_amounts_eur.append(-cfg.monthly_sip_eur)
        cash_inr = 0.0

        # Regime
        n_price = nifty_close.loc[day]
        n_dma = nifty_dma.loc[day] if day in nifty_dma.index else float("nan")
        regime = "bull" if (pd.isna(n_dma) or n_price > n_dma) else "bear"
        alloc = allocation_split(
            available_cash, regime,
            bull_core=cfg.bull_core_pct, bull_alpha=cfg.bull_alpha_pct,
            bear_core=cfg.bear_core_pct, bear_alpha=cfg.bear_alpha_pct,
        )

        # Allocate Core: equal-weight across tickers that have data today
        active_cores = [t for t in core_tickers if t in prices and day in prices[t].index]
        core_remaining = alloc.core_inr
        if active_cores:
            per = alloc.core_inr / len(active_cores)
            for t in active_cores:
                price = prices[t].loc[day, "Close"]
                if price > 0:
                    shares = int(per // price)
                    portfolio[t] += shares
                    core_remaining -= shares * price
        cash_inr += core_remaining

        # Allocate Alpha: 200-DMA + 52W + 6M momentum, top N
        alpha_stats = []
        for t in alpha_tickers:
            if t not in prices or day not in prices[t].index:
                continue
            df = prices[t]
            close = df["Close"]
            window = close.loc[:day]
            if len(window) < 200:
                continue
            dma = window.rolling(200).mean().iloc[-1]
            high_52 = window.iloc[-252:].max() if len(window) >= 252 else window.max()
            price = window.iloc[-1]
            if price < dma or price < high_52 * 0.80:
                continue
            past_6m = window[window.index <= day - pd.DateOffset(months=6)]
            if past_6m.empty:
                continue
            momentum = ((price - past_6m.iloc[-1]) / past_6m.iloc[-1]) * 100
            alpha_stats.append((t, momentum, price))

        alpha_stats.sort(key=lambda x: x[1], reverse=True)
        top_alphas = alpha_stats[: cfg.alpha_top_n]
        alpha_remaining = alloc.alpha_inr
        if top_alphas:
            per = alloc.alpha_inr / len(top_alphas)
            for t, _momentum, price in top_alphas:
                shares = int(per // price)
                portfolio[t] += shares
                alpha_remaining -= shares * price
        cash_inr += alpha_remaining

    # Final mark-to-market
    final_inr = cash_inr
    last_day = backtest_dates[-1]
    for t, qty in portfolio.items():
        if qty <= 0 or t not in prices:
            continue
        price = prices[t]["Close"].asof(last_day)
        if pd.notna(price):
            final_inr += qty * price

    final_fx = float(fx.iloc[-1]) if not pd.isna(fx.iloc[-1]) else 90.0
    final_eur = final_inr / final_fx
    invested_eur = -sum(cf_amounts_eur)

    xirr_pct = None
    if _xirr and cf_dates:
        try:
            xirr_pct = _xirr(
                cf_dates + [last_day.to_pydatetime()],
                cf_amounts_eur + [final_eur],
            )
            if xirr_pct is not None:
                xirr_pct = xirr_pct * 100
        except Exception:
            xirr_pct = None

    profit_eur = final_eur - invested_eur
    roi_pct = (profit_eur / invested_eur * 100) if invested_eur > 0 else 0.0

    return BacktestResult(
        final_equity=final_eur,
        total_invested=invested_eur,
        net_profit=profit_eur,
        roi_pct=roi_pct,
        xirr_pct=xirr_pct,
        max_drawdown_pct=0.0,   # not tracked for SIP backtest
        wins=0, losses=0,
        trades=[],
    )


# ---------------------------------------------------------------------------
# Swing V4.0 backtest (Route 3: alpha)
# ---------------------------------------------------------------------------

@dataclass
class _OpenPos:
    qty: int
    entry_price: float
    entry_date: pd.Timestamp
    stop_loss: float
    days_held: int = 0


def run_swing_backtest(
    prices: Mapping[str, pd.DataFrame],
    nifty: pd.DataFrame,
    universe: list[str],
    cfg: SwingBacktestConfig = SwingBacktestConfig(),
) -> BacktestResult:
    """ATR-sized swing backtest with RS filter and breadth gating.

    Pre-computes technicals once per ticker (precalc_technicals).
    Iterates the Nifty calendar; per day:
      1. Update trailing stops, evaluate exits.
      2. Check regime + breadth; if both bullish and room exists, scan setups.
      3. Buy top-scored setups using ATR-based 1%-risk sizing.

    Pure: no yfinance, no console output.
    """
    end_date = nifty.index.max()
    start_backtest = end_date - pd.DateOffset(years=cfg.years)

    # Pre-compute technicals + RS for each universe ticker
    tech: dict[str, pd.DataFrame] = {}
    nifty_close = nifty["Close"]
    for t in universe:
        if t not in prices:
            continue
        df = precalc_technicals(prices[t])
        aligned_nifty = nifty_close.reindex(df.index, method="ffill")
        df["RS"] = df["Close"] / aligned_nifty
        df["RS_SMA20"] = df["RS"].rolling(window=20).mean()
        tech[t] = df

    calendar = nifty.index
    backtest_dates = calendar[calendar >= start_backtest]
    if backtest_dates.empty:
        return _empty_backtest_result(invested=cfg.initial_capital)

    # Per-day universe breadth via close panel (column per ticker)
    closes_by_t = {t: df["Close"] for t, df in tech.items() if not df.empty}
    if closes_by_t:
        breadth_panel = pd.DataFrame(closes_by_t).reindex(backtest_dates, method="ffill")
    else:
        breadth_panel = pd.DataFrame(index=backtest_dates)

    cash = cfg.initial_capital
    open_positions: dict[str, _OpenPos] = {}
    trades: list[Trade] = []
    wins = losses = 0
    equity_curve: list[float] = []

    nifty_sma20 = nifty_close.rolling(window=20).mean()

    for day in backtest_dates:
        # Mark-to-market equity
        equity = cash + sum(
            pos.qty * tech[t]["Close"].asof(day)
            for t, pos in open_positions.items()
            if t in tech and pd.notna(tech[t]["Close"].asof(day))
        )

        # Regime checks
        n_close = nifty_close.asof(day)
        n_sma20 = nifty_sma20.asof(day)
        is_bull = pd.notna(n_sma20) and n_close > n_sma20
        is_breadth_ok = market_breadth(
            breadth_panel, ts=day,
            window=cfg.breadth_window, threshold=cfg.breadth_threshold,
        )

        # Exits
        for t, pos in list(open_positions.items()):
            if t not in tech or day not in tech[t].index:
                continue
            row = tech[t].loc[day]
            close = float(row["Close"])
            atr_val = float(row["ATR"]) if not pd.isna(row["ATR"]) else 0.0

            pos.days_held += 1
            # Ratcheting trailing stop
            new_sl = close - cfg.atr_multiplier * atr_val
            if new_sl > pos.stop_loss:
                pos.stop_loss = new_sl

            sell_price: float | None = None
            reason = ""
            if close <= pos.stop_loss:
                sell_price = close
                reason = "Trailing SL"
            elif pos.days_held >= cfg.time_stop_days:
                # FIX vs legacy bug #5: time-stop now fires regardless of P&L sign,
                # so runaway winners eventually book profit too.
                sell_price = close
                reason = "Time stop"

            if sell_price is None:
                continue

            revenue = pos.qty * sell_price
            cost_basis = pos.qty * pos.entry_price
            tax = (revenue + cost_basis) * (cfg.tax_slippage_pct / 2)
            net = revenue - tax
            profit = net - cost_basis
            pnl_pct = (profit / cost_basis) * 100 if cost_basis else 0.0
            cash += net
            trades.append(Trade(
                ticker=t, entry_ts=pos.entry_date.to_pydatetime(),
                exit_ts=day.to_pydatetime(),
                qty=pos.qty, entry_price=pos.entry_price, exit_price=sell_price,
                net_pnl=profit, pnl_pct=pnl_pct, reason=reason,
            ))
            if profit > 0: wins += 1
            else: losses += 1
            del open_positions[t]

        # Refresh equity after exits
        equity = cash + sum(
            pos.qty * tech[t]["Close"].asof(day)
            for t, pos in open_positions.items()
            if t in tech and pd.notna(tech[t]["Close"].asof(day))
        )
        equity_curve.append(equity)

        # Entries
        if not (is_bull and is_breadth_ok):
            continue
        if len(open_positions) >= cfg.max_positions:
            continue
        if cash <= cfg.initial_capital * 0.05:
            continue

        setups = _score_swing_entries(tech, day, cfg)
        setups.sort(key=lambda s: s[1], reverse=True)

        for setup in setups:
            if len(open_positions) >= cfg.max_positions:
                break
            t, score, price, stop_loss, risk_per_share = setup
            if t in open_positions:
                continue

            qty = apply_position_sizing(
                equity=equity, risk_per_share=risk_per_share, price=price,
                risk_pct=cfg.risk_per_trade_pct,
                max_capital_pct=cfg.max_capital_per_trade_pct,
            )
            if qty <= 0:
                continue

            cost = qty * price
            buy_tax = cost * (cfg.tax_slippage_pct / 2)
            if cash < cost + buy_tax:
                continue
            cash -= (cost + buy_tax)
            open_positions[t] = _OpenPos(
                qty=qty, entry_price=price, entry_date=day, stop_loss=stop_loss, days_held=0,
            )

    # Close any remaining positions at last price
    last_day = backtest_dates[-1]
    for t, pos in list(open_positions.items()):
        if t not in tech: continue
        final_price = float(tech[t]["Close"].iloc[-1])
        revenue = pos.qty * final_price
        cost_basis = pos.qty * pos.entry_price
        tax = (revenue + cost_basis) * (cfg.tax_slippage_pct / 2)
        net = revenue - tax
        profit = net - cost_basis
        pnl_pct = (profit / cost_basis) * 100 if cost_basis else 0.0
        cash += net
        trades.append(Trade(
            ticker=t, entry_ts=pos.entry_date.to_pydatetime(),
            exit_ts=last_day.to_pydatetime(),
            qty=pos.qty, entry_price=pos.entry_price, exit_price=final_price,
            net_pnl=profit, pnl_pct=pnl_pct, reason="End of test",
        ))
        if profit > 0: wins += 1
        else: losses += 1

    final_equity = cash
    invested = cfg.initial_capital
    profit = final_equity - invested
    roi_pct = (profit / invested * 100) if invested else 0.0

    # Drawdown from equity curve
    peak = invested
    max_dd = 0.0
    for eq in equity_curve:
        peak = max(peak, eq)
        dd = (peak - eq) / peak * 100 if peak else 0.0
        max_dd = max(max_dd, dd)

    return BacktestResult(
        final_equity=final_equity,
        total_invested=invested,
        net_profit=profit,
        roi_pct=roi_pct,
        xirr_pct=None,
        max_drawdown_pct=max_dd,
        wins=wins, losses=losses,
        trades=trades,
    )


def _score_swing_entries(
    tech: dict[str, pd.DataFrame],
    day: pd.Timestamp,
    cfg: SwingBacktestConfig,
) -> list[tuple[str, int, float, float, float]]:
    """Return (ticker, score, price, stop_loss, risk_per_share) for valid entries."""
    out = []
    for t, df in tech.items():
        if day not in df.index:
            continue
        row = df.loc[day]
        # Filters
        if any(pd.isna(row.get(k)) for k in (
            "SMA_50", "SMA_200", "ATR", "RSI", "MACD_Hist",
            "SMA_20", "Prev_SMA_20", "Prev_RSI", "Prev_MACD_Hist", "Avg_Vol_20",
            "RS", "RS_SMA20",
        )):
            continue
        price = float(row["Close"])
        if price < row["SMA_50"] or price < row["SMA_200"]:
            continue
        if row["RS"] < row["RS_SMA20"]:
            continue
        # Score
        score = 0
        if row["MACD_Hist"] > 0 and row["Prev_MACD_Hist"] <= 0:
            score += 3
        if row["RSI"] > 50 and row["Prev_RSI"] <= 50:
            score += 2
        if price > row["SMA_20"] and df["Close"].iloc[df.index.get_loc(day) - 1] <= row["Prev_SMA_20"]:
            score += 3
        if row["Volume"] > row["Avg_Vol_20"] * 1.5:
            score += 2
        if score < cfg.min_score:
            continue
        atr_val = float(row["ATR"])
        risk_per_share = cfg.atr_multiplier * atr_val
        if (risk_per_share / price) > 0.15:
            continue
        out.append((t, score, price, price - risk_per_share, risk_per_share))
    return out


def _empty_backtest_result(invested: float) -> BacktestResult:
    return BacktestResult(
        final_equity=invested,
        total_invested=invested,
        net_profit=0.0,
        roi_pct=0.0,
        xirr_pct=None,
        max_drawdown_pct=0.0,
        wins=0, losses=0,
        trades=[],
    )
