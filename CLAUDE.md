# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup & Run

All Python scripts live in `Src/` and share one virtualenv at `Src/venv`. Top-level `requirements.txt` is the canonical dep list.

```bash
# from repo root
source Src/venv/bin/activate
pip install -r requirements.txt

# unified menu
python Src/launcher.py

# or run any bot standalone
python Src/<script>.py
```

`paper_trader.py` now uses a script-relative `STATE_FILE` path, so it no longer matters which cwd you launch from. The `yfinance.cache` file is still relative — it lands wherever you launched from.

There are no tests, no linter config, and no build step — every script is run directly.

## Architecture

This is a collection of **independent CLI bots** for SIP-style investing in Indian equities (NSE) from the perspective of a Euro-resident. They are not a library; there's no shared module. Each script duplicates boilerplate (FX fetch, `SuppressOutput` context manager, Rich UI panels). When changing shared behavior (e.g., a new safety filter), update each bot — there is no single source of truth.

### The three strategies (from `Docs/FIRE_Strategies_40k_SIP.md`)

The bots collectively implement a framework documented in `Docs/`:

- **Route 1 — Dividend Snowball:** `dividend_bot.py` (live screener) + `backtest.py` (historical simulator). Core (40%) in dividend ETFs + ITC; Satellite (60%) in high-yield stocks gated by PE > 0, payout < 95%, and **price > 200-DMA** (the v3.0 momentum filter that eliminates value traps).
- **Route 2 + 3 hybrid — Index + Momentum:** `fire_builder_bot.py` (live) + `swing_backtest.py` (backtest, v4.0). Allocation flips with Nifty 50 regime: bull → 40/60 Core/Alpha, bear → 80/20. Alpha picks rank by 6-month momentum, must be > 200-DMA and within 20% of 52-week high.
- **Swing trading:** `swing_trade_bot.py` (live EOD scanner, 15-day holds) and `paper_trader.py` (continuous live paper-trading loop with persisted virtual account).

### Shared design conventions

- **Universes are hardcoded** as `UNIVERSE` / `ALPHA_CANDIDATES` / `CORE_TICKERS` lists at the top of each file. To change tradable tickers, edit the list in each bot that needs it.
- **Market regime gate:** most bots check `^NSEI` vs its SMA-20/50/200 before authorizing any aggressive position. Removing this gate is what turns a defensive bot into a value-trap machine — be very careful editing the regime logic.
- **FX:** all live bots call `fetch_fx_rates()` (USD/INR, EUR/INR) with hardcoded fallbacks (83/90). The backtests reindex an EUR/INR history series for accurate per-month conversion of EUR SIP → INR.
- **Rich UI:** every bot renders Panels + Tables via the `rich` library; `SuppressOutput` is used to silence `yfinance`'s noisy stdout during live status spinners.
- **Reinvestment (DRIP):** backtests credit dividends to `cash_inr` and roll the cash into the next SIP day rather than holding it. XIRR (via `pyxirr`) is the headline return metric, not CAGR.

### Backtester internals (`backtest.py`, `swing_backtest.py`)

Both follow the same shape: download history with a 1-year buffer (so 200-DMA and 52-week-high are valid from day one of the test window), iterate every trading day from `^NSEI`'s calendar, apply regime + entry logic on the last trading day of each month (for SIP bots) or every day (for swing). Position sizing in `swing_backtest.py` uses **ATR-based 1%-risk sizing** (the v4.0 "institutional math" upgrade): `qty = (equity * 0.01) / (2.5 * ATR)`, capped at 20% of equity per position.

### `optimize.py` / `optimize2.py`

These are **parameter-sweep scripts**, not user-facing tools — they print plaintext results for grid searches (trailing-stop %, breakout condition, RSI threshold, R:R) used to tune the swing strategy. They have no Rich UI and no prompts; just `python optimize.py` and read stdout.

### `paper_trader.py`

Long-running continuous loop that ticks during NSE hours (uses `pytz` for `Asia/Kolkata`). Persists state to `virtual_account_state.json` between runs — deleting that file resets the ₹10,00,000 virtual account. State includes `cash`, `positions`, `history`, `logs`, `equity_history`, `bot_thoughts` (a rolling 10-entry list of the bot's reasoning shown in the TUI).

## Things to know before editing

- **`yfinance` is flaky.** Every network call is wrapped in `try/except: pass` with sensible fallbacks. Don't "improve" this by raising — silent degradation is intentional so a single failing ticker doesn't kill the whole screen.
- **All monetary defaults are in EUR** (the user invests from Europe). The "₹40,000 SIP" framing in `Docs/FIRE_Strategies_40k_SIP.md` is illustrative; the actual prompts default to €500/month.
- **No CI, no formatters.** Match existing style (4-space indent, Rich-heavy output, f-strings everywhere).
