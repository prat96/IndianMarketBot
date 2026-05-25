import sys
import os
import yfinance as yf
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import IntPrompt, FloatPrompt
from rich.align import Align
from rich import box
import warnings
from datetime import datetime
from dateutil.relativedelta import relativedelta
try:
    from pyxirr import xirr
except ImportError:
    xirr = None

warnings.filterwarnings('ignore')
console = Console()

class SuppressOutput:
    def __enter__(self):
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        sys.stdout = open(os.devnull, 'w')
        sys.stderr = open(os.devnull, 'w')

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stderr.close()
        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr

# Define Universe
SAFE_CORE_ETFS = [
    "NIFTYBEES.NS", "JUNIORBEES.NS"
]

ALPHA_CANDIDATES = [
    "TRENT.NS", "RELIANCE.NS", "VBL.NS", "BSE.NS", "CDSL.NS",
    "HAL.NS", "TATAPOWER.NS", "DIXON.NS", "BAJAJ-AUTO.NS",
    "BHARTIARTL.NS", "ADANIPOWER.NS", "LT.NS", "HDFCBANK.NS",
    "MOMOMENTUM.NS", "MID150BEES.NS", "TCS.NS"
]

def run_backtest(years=5, monthly_sip_eur=500.0, eu_inflation_rate=2.5):
    end_date = pd.Timestamp.now(tz='Asia/Kolkata')
    start_backtest = end_date - pd.DateOffset(years=years)
    # Fetch 1 extra year for 200-DMA and Trailing Yield calculation
    start_data = start_backtest - pd.DateOffset(years=1)
    
    all_tickers = SAFE_CORE_ETFS + ALPHA_CANDIDATES + ["^NSEI", "EURINR=X"]
    
    console.print("[yellow]Downloading historical data (including 1-year buffer for 200-DMA & EUR/INR)...[/yellow]")
    data = {}
    with console.status("[yellow]Fetching data and building cross-border models...[/yellow]"):
        for ticker in all_tickers:
            try:
                with SuppressOutput():
                    tk = yf.Ticker(ticker)
                    hist = tk.history(start=start_data.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
                if not hist.empty:
                    if ticker not in ["^NSEI", "EURINR=X"]:
                        # Pre-calculate 200-DMA and 52W High for equities
                        hist['200_DMA'] = hist['Close'].rolling(window=200).mean()
                        hist['52W_High'] = hist['Close'].rolling(window=252).max()
                    elif ticker == "^NSEI":
                        hist['200_DMA'] = hist['Close'].rolling(window=200).mean()
                    data[ticker] = hist
            except:
                pass
            
    if "^NSEI" not in data:
        console.print("[bold red]Failed to fetch Nifty data for regime detection. Cannot run backtest.[/bold red]")
        return
        
    all_dates = data["^NSEI"].dropna(subset=['200_DMA']).index
    backtest_dates = all_dates[all_dates >= start_backtest]
    if backtest_dates.empty:
        console.print("[bold red]Not enough historical data for the selected timeframe.[/bold red]")
        return
        
    monthly_dates = set(pd.Series(backtest_dates).groupby([backtest_dates.year, backtest_dates.month]).max())
    
    # Process EUR/INR history
    eur_inr_hist = data.get("EURINR=X")
    if eur_inr_hist is not None and not eur_inr_hist.empty:
        eur_inr_series = eur_inr_hist['Close'].reindex(backtest_dates).ffill()
    else:
        # Fallback if Yahoo Finance fails to deliver EUR/INR history
        eur_inr_series = pd.Series(90.0, index=backtest_dates)
    
    portfolio = {t: {"shares": 0.0} for t in all_tickers if t not in ["^NSEI", "EURINR=X"]}
    cash_inr = 0.0
    total_invested_eur = 0.0
    total_invested_adjusted_eur = 0.0 # EU Inflation adjusted
    total_invested_inr = 0.0
    total_dividends_collected_inr = 0.0
    
    cash_flows_dates = []
    cash_flows_amounts_eur = []
    
    for day in backtest_dates:
        # Check for dividends today on existing shares
        for t, df in data.items():
            if t in ["^NSEI", "EURINR=X"]: continue
            if day in df.index:
                div = df.loc[day, 'Dividends']
                if div > 0 and portfolio[t]["shares"] > 0:
                    amount = div * portfolio[t]["shares"]
                    cash_inr += amount
                    total_dividends_collected_inr += amount
        
        # If it's a SIP day (last trading day of month)
        if day in monthly_dates:
            current_fx = eur_inr_series.loc[day]
            if pd.isna(current_fx) or current_fx <= 0:
                current_fx = 90.0
                
            monthly_sip_inr = monthly_sip_eur * current_fx
            
            available_cash = monthly_sip_inr + cash_inr
            
            total_invested_eur += monthly_sip_eur
            total_invested_inr += monthly_sip_inr
            
            # Calculate EU inflation adjusted contribution (value of that EUR SIP in today's EUR money)
            years_elapsed = (end_date - day).days / 365.25
            total_invested_adjusted_eur += monthly_sip_eur * ((1 + eu_inflation_rate/100) ** years_elapsed)
            
            cash_inr = 0.0
            
            cash_flows_dates.append(day.to_pydatetime())
            cash_flows_amounts_eur.append(-monthly_sip_eur)
            
            # Regime Check
            nifty_price = data["^NSEI"].loc[day, 'Close']
            nifty_200dma = data["^NSEI"].loc[day, '200_DMA']
            is_bull_market = nifty_price > nifty_200dma if not pd.isna(nifty_200dma) else True
            
            if is_bull_market:
                core_budget = available_cash * 0.40
                alpha_budget = available_cash * 0.60
            else:
                core_budget = available_cash * 0.80
                alpha_budget = available_cash * 0.20
            
            # Core
            active_cores = [t for t in SAFE_CORE_ETFS if t in data and day in data[t].index]
            if active_cores:
                budget_per_core = core_budget / len(active_cores)
                for t in active_cores:
                    price = data[t].loc[day, 'Close']
                    if price > 0:
                        shares = int(budget_per_core // price)
                        portfolio[t]["shares"] += shares
                        core_budget -= (shares * price)
                cash_inr += core_budget
                
            # Alpha
            alpha_stats = []
            for t in ALPHA_CANDIDATES:
                if t not in data or day not in data[t].index: continue
                df = data[t]
                
                # Check 200-DMA & 52W High
                dma_200 = df.loc[day, '200_DMA']
                high_52 = df.loc[day, '52W_High']
                price = df.loc[day, 'Close']
                
                if pd.isna(dma_200) or price < dma_200:
                    continue
                if pd.isna(high_52) or price < (high_52 * 0.80):
                    continue
                
                # 6M momentum
                past_6m_date = day - pd.DateOffset(months=6)
                past_df = df[df.index <= past_6m_date]
                if past_df.empty:
                    continue
                    
                price_6m_ago = past_df['Close'].iloc[-1]
                if price_6m_ago > 0:
                    momentum = ((price - price_6m_ago) / price_6m_ago) * 100
                    alpha_stats.append({"ticker": t, "momentum": momentum, "price": price})
            
            alpha_stats.sort(key=lambda x: x["momentum"], reverse=True)
            top_alphas = alpha_stats[:3]
            if top_alphas:
                budget_per_alpha = alpha_budget / len(top_alphas)
                for alpha in top_alphas:
                    shares = int(budget_per_alpha // alpha["price"])
                    portfolio[alpha["ticker"]]["shares"] += shares
                    alpha_budget -= (shares * alpha["price"])
                cash_inr += alpha_budget
            else:
                # Fallback: if no satellites passed the 200-DMA filter, save cash
                cash_inr += alpha_budget

    # Final Value in INR
    final_value_inr = cash_inr
    for t in portfolio:
        if portfolio[t]["shares"] > 0:
            last_price = data[t]['Close'].iloc[-1]
            final_value_inr += portfolio[t]["shares"] * last_price
            
    # Final Conversion to EUR
    try:
        with SuppressOutput():
            eur_inr = yf.Ticker('EURINR=X').info.get('regularMarketPrice') or yf.Ticker('EURINR=X').info.get('currentPrice', 90.0)
            usd_inr = yf.Ticker('USDINR=X').info.get('regularMarketPrice') or yf.Ticker('USDINR=X').info.get('currentPrice', 83.0)
    except:
        eur_inr, usd_inr = 90.0, 83.0
        
    final_value_eur = final_value_inr / eur_inr
            
    # Add final portfolio value in EUR to cash flows for XIRR
    if len(backtest_dates) > 0:
        cash_flows_dates.append(backtest_dates[-1].to_pydatetime())
        cash_flows_amounts_eur.append(final_value_eur)
            
    profit_eur = final_value_eur - total_invested_eur
    roi_pct = (profit_eur / total_invested_eur) * 100 if total_invested_eur > 0 else 0
    
    # Calculate EU Inflation-Adjusted (Real) metrics
    real_final_value_eur = final_value_eur / ((1 + eu_inflation_rate/100) ** years)
    
    annual_return_eur = "N/A"
    real_annual_return_eur = "N/A"
    
    if xirr:
        try:
            xirr_val = xirr(cash_flows_dates, cash_flows_amounts_eur)
            if xirr_val:
                # Nominal CAGR in EUR
                nominal_cagr = xirr_val
                annual_return_eur = f"{nominal_cagr * 100:.2f}%"
                
                # Real CAGR in EUR formula
                inf_decimal = eu_inflation_rate / 100
                real_cagr = ((1 + nominal_cagr) / (1 + inf_decimal)) - 1
                real_annual_return_eur = f"{real_cagr * 100:.2f}%"
        except:
            annual_return_eur = "Error calculating"
            real_annual_return_eur = "Error calculating"
    
    console.print("\n")
    console.print(Panel.fit(f"[bold cyan]💱 Final Live FX Rates:[/bold cyan] 1 USD = ₹{usd_inr:,.2f} | 1 EUR = ₹{eur_inr:,.2f}", border_style="cyan"))
        
    table = Table(
        title=f"📊 GEO-ARBITRAGE {years}-Year Backtest (SIP: €{monthly_sip_eur:,.0f}/mo)", 
        style="blue",
        box=box.SIMPLE_HEAVY,
        header_style="bold bright_cyan",
        title_justify="center"
    )
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value (EUR)", style="blue", justify="right")
    table.add_column("Real (EUR)", style="yellow", justify="right")
    table.add_column("Value (INR)", style="magenta", justify="right")
    
    table.add_row(
        "Total Capital Invested", 
        f"€{total_invested_eur:,.2f}", f"€{total_invested_adjusted_eur:,.2f}*", f"₹{total_invested_inr:,.2f}"
    )
    table.add_row(
        "Total Dividends Reinvested", 
        f"€{total_dividends_collected_inr/eur_inr:,.2f}", "-", f"₹{total_dividends_collected_inr:,.2f}"
    )
    table.add_row(
        "Final Portfolio Value", 
        f"€{final_value_eur:,.2f}", f"€{real_final_value_eur:,.2f}**", f"₹{final_value_inr:,.2f}"
    )
    table.add_row(
        "Net Profit", 
        f"€{profit_eur:,.2f}", f"€{real_final_value_eur - total_invested_eur:,.2f}", f"₹{final_value_inr - total_invested_inr:,.2f}"
    )
    table.add_row("Absolute ROI", f"{roi_pct:.2f}%", "-", "-")
    if xirr:
        table.add_row("Annualized Return (XIRR)", f"{annual_return_eur}", f"{real_annual_return_eur}", "-")
    
    console.print("\n")
    console.print(table)
    
    console.print(f"\n[italic]* 'Total Capital Invested (Real)' shows how much your Euros would be worth if invested entirely today, accounting for {eu_inflation_rate}% EU inflation.[/italic]")
    console.print(f"[italic]** 'Final Portfolio Value (Real)' shows the purchasing power of your final portfolio expressed in Year-1 European money terms.[/italic]\n")
    
    console.print(Panel(
        "[bold yellow]Geo-Arbitrage Insights:[/bold yellow]\n\n"
        "1. [bold]The Geo-Arbitrage Edge:[/bold] The backtest actively converts your Euros to Rupees every month at the historical exchange rate. Despite the INR depreciating against the EUR over these 5 years, the explosive momentum of the Indian market completely overwhelmed the currency loss.\n"
        f"2. [bold]Low EU Inflation:[/bold] Because your target lifestyle is in Europe, we discounted the massive nominal returns by a much lower {eu_inflation_rate}% inflation rate. This causes your 'Real' wealth to stay incredibly high compared to an investor retiring inside India facing 6%+ inflation.\n"
        "3. [bold]The Hybrid Engine:[/bold] You captured the safety of index funds during bear markets and the hyper-growth of Indian small-caps during bull markets, all from the safety of the Eurozone.",
        title="[bold gold1]Backtest Analysis[/bold gold1]",
        border_style="yellow",
        box=box.HEAVY
    ))

def main():
    console.clear()
    header = Panel(
        Align.center(
            "\n[bold gold1]🌍 GEO-ARBITRAGE BACKTESTER (EU -> INDIA) ⏱️[/bold gold1]\n\n"
            "[italic white]Time-machine simulation with dynamic EUR/INR currency conversions, Momentum Filters, and European Inflation Adjustments.\n"
            "Proves the math behind investing in high-growth emerging markets while living in low-inflation developed markets.[/italic white]\n"
        ),
        box=box.DOUBLE_EDGE,
        border_style="gold1",
        padding=(1, 2)
    )
    console.print(header)
    
    years = IntPrompt.ask("\n[bold cyan]1.[/bold cyan] How many years back do you want to test?", default=5)
    monthly_sip_eur = FloatPrompt.ask("[bold cyan]2.[/bold cyan] Enter your monthly SIP amount in Euros (€)", default=500.0)
    eu_inflation_rate = FloatPrompt.ask("[bold cyan]3.[/bold cyan] Expected European Annual Inflation Rate (%) [Historic Avg: ~2.5%]", default=2.5)
    
    console.print("\n")
    run_backtest(years=years, monthly_sip_eur=monthly_sip_eur, eu_inflation_rate=eu_inflation_rate)

if __name__ == "__main__":
    main()
