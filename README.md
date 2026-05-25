<div align="center">

# 🇮🇳 Indian Market Bot

### A toolkit of algorithmic SIP, swing, and F.I.R.E. bots for the Indian stock market — built for a Euro-resident investor.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache_2.0-green.svg)](LICENSE)
[![Data: yfinance](https://img.shields.io/badge/data-yfinance-orange.svg)](https://github.com/ranaroussi/yfinance)
[![UI: Rich](https://img.shields.io/badge/UI-rich-magenta.svg)](https://github.com/Textualize/rich)
[![XIRR: pyxirr](https://img.shields.io/badge/XIRR-pyxirr-yellow.svg)](https://github.com/Anexen/pyxirr)

*"Earn in Euros, invest in Rupees, retire anywhere."*

</div>

---

## ✨ What's inside

A collection of **7 standalone terminal bots** that screen, allocate, backtest, and paper-trade Indian equities — all wrapped in a beautiful [Rich](https://github.com/Textualize/rich) TUI and unified behind a single `launcher.py` menu.

```
┌─────────────────────────────────────────────────────────────────────┐
│  🇮🇳  INDIAN MARKET BOT — UNIFIED LAUNCHER  🇮🇳                       │
│  One menu, every strategy. Pick a bot and go.                       │
├─────┬──────────┬──────────────────────────────────────┬─────────────┤
│  #  │  Kind    │  Bot                                 │  What it does│
├─────┼──────────┼──────────────────────────────────────┼─────────────┤
│  1  │  LIVE    │  F.I.R.E. Wealth Builder             │  Hybrid SIP │
│  2  │  LIVE    │  Dividend Snowball Screener          │  Core+Sat.  │
│  3  │  LIVE    │  Intra-Week Swing Trader             │  EOD scan   │
│  4  │  LOOP    │  Paper Trader                        │  Virtual A/c│
│  5  │  BACKTEST│  Geo-Arbitrage Backtester            │  EUR→INR    │
│  6  │  BACKTEST│  Swing Strategy Backtester (V4.0)    │  ATR sizing │
│  7  │  PROJECT │  Cross-Border F.I.R.E. Projector     │  15y model  │
└─────┴──────────┴──────────────────────────────────────┴─────────────┘
```

---

## 🚀 Quickstart

```bash
# 1. Clone
git clone <this-repo> IndianMarketBot
cd IndianMarketBot

# 2. Create + activate venv
python3 -m venv Src/venv
source Src/venv/bin/activate          # Windows: Src\venv\Scripts\activate

# 3. Install deps
pip install -r requirements.txt

# 4. Launch the menu
python Src/launcher.py
```

That's it. Pick a number from the menu and the bot fires up.

> **Tip:** Each bot also works standalone — `python Src/fire_builder_bot.py` etc. The launcher is just a friendlier front door.

---

## 🧠 The big idea

This repo implements a **3-route framework for Financial Independence, Retire Early (F.I.R.E.)** documented in [`Docs/FIRE_Strategies_40k_SIP.md`](Docs/FIRE_Strategies_40k_SIP.md):

| Route | Style | Vehicle | When it wins |
|---|---|---|---|
| **1. Snowball** 🐌 | Income | High-yield stocks + DRIP | Retirement — live off pure dividends |
| **2. Indexing** 📚 | Reliability | Nifty 50 / Next 50 ETFs | Always works given a 15-year horizon |
| **3. Momentum** 🚀 | Alpha | Mid/Small caps, 200-DMA + 6M momo | Bull markets — fastest path to target |

The bots blend these dynamically. The flagship `fire_builder_bot.py` rebalances every month based on whether Nifty 50 is above or below its 200-DMA:

```
   BULL MARKET (Nifty > 200-DMA)        BEAR MARKET (Nifty < 200-DMA)
   ┌──────────────────────────┐         ┌──────────────────────────┐
   │   Core (Index ETFs)      │ 40%     │   Core (Index ETFs)      │ 80%
   │ ████████░░░░░░░░░░░░░░░░ │         │ ████████████████░░░░░░░░ │
   │   Alpha (Momentum)       │ 60%     │   Alpha (Momentum)       │ 20%
   │ ████████████░░░░░░░░░░░░ │         │ ████░░░░░░░░░░░░░░░░░░░░ │
   └──────────────────────────┘         └──────────────────────────┘
```

---

## 🧰 Bot-by-bot tour

<details open>
<summary><b>1. <code>fire_builder_bot.py</code> — F.I.R.E. Wealth Builder ⭐</b></summary>

**Purpose:** Tells you exactly which shares to buy this month with your €500 SIP.

Combines safe index ETFs (`NIFTYBEES`, `JUNIORBEES`) with a top-3 momentum pick from a curated alpha universe. Allocation flips based on Nifty 50's 200-DMA regime.

**Filters applied to alpha picks:**
- Price > 200-DMA (uptrend confirmed)
- Price within 20% of 52-week high (not a falling knife)
- Top 3 by 6-month return

**Output:** A "Broker Shopping List" — exact share quantities to enter into Zerodha/Groww/Upstox.

</details>

<details>
<summary><b>2. <code>dividend_bot.py</code> — Dividend Snowball Screener</b></summary>

**Purpose:** Build a passive cash-flow portfolio that pays you to wait.

Uses a **Core & Satellite** architecture:
- **Core (40%):** `DIVOPPBEES`, `CPSEETF`, `ITC` — unshakeable foundation.
- **Satellite (60%):** High-yield stocks gated by these v3.0 filters:
  - Yield between 3–18% (above is value-trap territory)
  - PE > 0 and < 40 (profitable, not bubble)
  - Payout ratio < 95% (sustainable)
  - **Price > 200-DMA** (the magic filter that eliminates dying companies)
  - Beta-adjusted score (rewards low-volatility)

</details>

<details>
<summary><b>3. <code>swing_trade_bot.py</code> — Intra-Week Swing Trader</b></summary>

**Purpose:** Find 15-day swing setups with proper Risk/Reward mechanics.

Scans the alpha universe at EOD for:
- MACD bullish cross
- RSI crossing 50 from below
- 20-DMA breakout
- Volume > 1.5× 20-day average

Trades only authorized when Nifty 50 > 20-DMA. Each setup ships with a hard stop loss (recent swing low, capped at -6%) and a 2.5R target.

</details>

<details>
<summary><b>4. <code>paper_trader.py</code> — Live Virtual Account 🔴</b></summary>

**Purpose:** Run the V4.0 swing strategy against live NSE prices, paper-money only.

Continuous loop that ticks during NSE hours (`Asia/Kolkata` 9:15am–3:30pm), executes EOD entries/exits using **ATR-based 1%-risk position sizing**, and persists everything to `virtual_account_state.json` between runs.

Watch the bot think in real time via the "Bot Thoughts" panel.

> Delete `virtual_account_state.json` to reset back to ₹10,00,000.

</details>

<details>
<summary><b>5. <code>backtest.py</code> — Geo-Arbitrage Backtester</b></summary>

**Purpose:** Mathematically prove the dividend strategy works over your chosen window.

Time-machine simulation that:
- Converts your monthly **€** SIP to **₹** at the *historical* EUR/INR rate
- Reinvests dividends on their actual ex-dates (DRIP)
- Applies the 200-DMA momentum filter month-by-month
- Computes **XIRR** in EUR terms (via `pyxirr`)
- Adjusts for EU inflation to show **real purchasing power**

</details>

<details>
<summary><b>6. <code>swing_backtest.py</code> — Swing Strategy Backtester (V4.0)</b></summary>

**Purpose:** Stress-test the swing strategy with institutional-grade math.

Improvements over a naive backtest:
- **ATR-based position sizing** — every trade risks exactly 1% of equity
- **Relative Strength filter** — only buys stocks outperforming Nifty
- **Market Breadth gate** — refuses entries unless >40% of universe > 50-DMA
- **Chandelier trailing stop** — `Close − 2.5×ATR`, lets winners run
- Tax/slippage modeled at 0.2% round-trip

</details>

<details>
<summary><b>7. <code>project.py</code> — Cross-Border F.I.R.E. Projector</b></summary>

**Purpose:** Forward-looking model. "If I invest €X/month for Y years..."

Computes the **effective EUR return** as `(1+INR_return)/(1+INR_depreciation) − 1`, applies a Safe Withdrawal Rate, inflates your target European expenses, and finds the exact month you cross F.I.R.E.

</details>

---

## 🔧 Tweaking the bots

Everything you'd want to change lives in **constants at the top of each script** — no config files, no YAML, no abstractions.

| To change... | Edit... | In file(s) |
|---|---|---|
| The list of stocks scanned | `UNIVERSE` / `ALPHA_CANDIDATES` / `CORE_TICKERS` | each bot |
| Core/Satellite split | `0.40 / 0.60` ratios | `fire_builder_bot.py`, `backtest.py` |
| Momentum filter strictness | `200-DMA`, `0.80` (52W threshold) | `score_momentum()` |
| Swing risk per trade | `RISK_PER_TRADE_PCT = 0.01` | `swing_backtest.py`, `paper_trader.py` |
| Default SIP amount | `default=500.0` in `FloatPrompt.ask` | each bot |
| Inflation rate | `eu_inflation_rate` param | `backtest.py`, `project.py` |
| FX fallback | `83.0, 90.0` in `fetch_fx_rates()` | every bot |

### Example: add a new ticker

```python
# Src/fire_builder_bot.py
ALPHA_CANDIDATES = [
    "TRENT.NS", "RELIANCE.NS", "VBL.NS",
    "ZOMATO.NS",   # ← add yours here, NSE tickers always end .NS
    ...
]
```

That's the entire API.

### Parameter sweeps

`Src/optimize.py` and `Src/optimize2.py` are bare-bones grid-search scripts. Edit the nested `for` loops, run `python Src/optimize.py`, read stdout. Use these to find the trailing-stop %, RSI threshold, and R:R values that work best on recent market data before promoting them into the live bots.

---

## 📁 Repository layout

```
IndianMarketBot/
├── Docs/
│   ├── development_journey.md       # How v1.0 → v3.0 evolved
│   └── FIRE_Strategies_40k_SIP.md   # The 3-route F.I.R.E. framework
├── Src/
│   ├── launcher.py                  # ⭐ unified menu
│   ├── fire_builder_bot.py          # Live: hybrid index + momentum
│   ├── dividend_bot.py              # Live: dividend snowball screener
│   ├── swing_trade_bot.py           # Live: 15-day swing setups
│   ├── paper_trader.py              # Live: virtual-money paper trader
│   ├── backtest.py                  # Backtest: dividend strategy
│   ├── swing_backtest.py            # Backtest: swing V4.0
│   ├── project.py                   # Forward F.I.R.E. projector
│   ├── optimize.py / optimize2.py   # Param-sweep grid searches
│   └── venv/                        # (gitignored)
├── requirements.txt
├── CLAUDE.md                        # Notes for Claude Code agents
├── README.md                        # ← you are here
└── LICENSE                          # Apache 2.0
```

---

## ⚠️ Disclaimer

This is **research/educational code**, not financial advice.

- All "live" bots tell you what to buy. They **do not place real orders**. Execution is on you, via your broker.
- `paper_trader.py` is paper money only. No broker API is wired in.
- `yfinance` data can be delayed or inaccurate; never trust a screen blindly.
- Past backtest performance does not predict future returns.
- The author is not a SEBI-registered investment advisor.

By using this code you accept full responsibility for any decisions you make with it.

---

## 🛠️ Built with

- [**yfinance**](https://github.com/ranaroussi/yfinance) — free Yahoo Finance market data
- [**rich**](https://github.com/Textualize/rich) — beautiful terminal output
- [**pandas**](https://pandas.pydata.org/) — time-series everything
- [**pyxirr**](https://github.com/Anexen/pyxirr) — fast Rust-backed XIRR
- [**pytz**](https://pythonhosted.org/pytz/) — `Asia/Kolkata` timezone awareness

---

## 📜 License

[Apache 2.0](LICENSE) — do what you want, just don't sue me.

<div align="center">

**Star ⭐ this repo if it sparked an idea. PRs welcome.**

</div>
