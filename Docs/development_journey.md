# Indian Market Dividend Snowball Bot: Development Journey

This document chronicles the evolution of the Indian Market Dividend Bot, from a basic yield-chasing script to an institutional-grade, momentum-filtered investment screener and backtester.

## The Goal
The objective was to build a system that automates a high-yield dividend portfolio strategy in the Indian stock market using a fixed monthly SIP (e.g., ₹10,000). The strategy needed to generate significant passive cash flow while mitigating risk and accelerating wealth through the "snowball effect" (Dividend Reinvestment - DRIP).

---

## Version 1.0: The "Pure Yield" Chaser
### The Approach
The initial version of the bot (`dividend_bot.py`) scraped real-time data using `yfinance` across five key categories: FMCG, PSUs, Finance/Infra, IT, and REITs. 
- It simply calculated the current dividend yield `(Dividend Rate / Current Price) * 100`.
- It sorted the universe of stocks from highest yield to lowest.
- It equally distributed the user's monthly SIP across the top 5 highest-yielding assets.

### The Flaw (The "Value Trap")
While mathematically correct, this strategy is dangerous in the real world. A stock's dividend yield can skyrocket to 15% simply because its stock price crashed by 60% due to a failing business model or impending bankruptcy. Sorting purely by yield blindly leads an investor into **Value Traps**.

---

## Version 2.0: The Core & Satellite Strategy
### The Upgrade
To protect capital, the algorithm was entirely rewritten to use a professional wealth-management framework: the **Core & Satellite Strategy**.

1. **The Core (40% of Capital):**
   - Allocated to ultra-safe, low-volatility assets: `Nifty Div Opp 50 ETF` (DIVOPPBEES), `CPSE ETF`, and mega-cap staples like `ITC`. 
   - This formed an unshakeable foundation for the portfolio that wouldn't collapse if a single company failed.

2. **The Satellite (60% of Capital):**
   - Allocated to direct high-yield equities, but guarded by strict algorithmic safety filters:
     - **Profitability:** Price-to-Earnings (PE) must be > 0. The company must be making money.
     - **Payout Ratio:** Must be < 95%. Companies paying out more than they earn will inevitably cut their dividends.
     - **Volatility (Beta):** Rewarded low-beta (stable) stocks and penalized high-beta (volatile) stocks.

### The Discovery
This version was significantly safer, ensuring we only bought profitable companies. However, we needed to mathematically prove it worked over the long term.

---

## The Proving Ground: Building the Time Machine
We built a secondary script (`backtest.py`) to simulate investing ₹10,000 every month over the past 5 years. The backtester tracked historical prices, accurately distributed dividends on the exact days they were paid, and immediately reinvested that cash into the next month's SIP (DRIP).

**Key Finding:** 
The DRIP effect was massive (generating over ₹1.3 Lakhs in pure cash over 5 years). However, the absolute return revealed that some high-yield PSUs severely lagged behind the broader market in terms of *capital appreciation*. We were earning dividends, but the underlying stock prices weren't growing fast enough.

---

## Version 3.0: Institutional Momentum & Real Returns (Current)
### The Ultimate Upgrade
To ensure we were capturing both high yield *and* capital growth, we introduced **Momentum Investing** to the Satellite bucket.

1. **The 200-DMA Momentum Filter:**
   - Before buying *any* high-yield stock, the algorithm now checks its 200-Day Moving Average (200-DMA).
   - If the current price is *below* the 200-DMA, the stock is in a long-term downtrend. The bot instantly rejects it and holds cash instead.
   - This absolutely eliminates Value Traps. We only buy dividend-paying companies that the market actively values and is pushing upwards.

2. **Interactive Backtesting with XIRR & Inflation:**
   - The backtester was upgraded to be fully interactive (configurable years, SIP amount, and inflation rate).
   - Integrated `pyxirr` to calculate the exact Annualized Return Rate (XIRR) based on the complex monthly cash flows.
   - Added an **Inflation Adjustment** module. It strips away a user-defined inflation rate (e.g., 6% for India) to show the *Real Purchasing Power* of the final portfolio, proving that the strategy generates wealth above and beyond the "silent tax" of inflation.

### The Final Result
A 5-year historical backtest of v3.0 (with a ₹10,000 SIP) resulted in:
- A massive **~33.8% Nominal Annualized Return (XIRR)**.
- A highly impressive **~26.3% Real Annualized Return** (after accounting for 6% annual inflation).
- Perfect capital protection during market crashes by automatically holding cash when stocks fell below their 200-DMA.

---

## Workspace Structure
- `/Src/dividend_bot.py`: The live terminal tool. Run this every month to get your actionable SIP allocation based on today's prices.
- `/Src/backtest.py`: The historical simulator. Use this to stress-test the strategy over any time period or inflation environment.
- `/Docs/`: Project documentation and development history.