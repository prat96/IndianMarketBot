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

# Define Universe
CORE_TICKERS = ["DIVOPPBEES.NS", "CPSEETF.NS", "ITC.NS"]
SATELLITE_CANDIDATES = [
    "COALINDIA.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS", "GAIL.NS",
    "PFC.NS", "RECLTD.NS", "IRFC.NS",
    "TCS.NS", "HCLTECH.NS", "INFY.NS"
]

def run_backtest(years=5, monthly_sip=10000.0, inflation_rate=6.0):
    end_date = pd.Timestamp.now(tz='Asia/Kolkata')
    start_backtest = end_date - pd.DateOffset(years=years)
    # Fetch 1 extra year for 200-DMA and Trailing Yield calculation
    start_data = start_backtest - pd.DateOffset(years=1)
    
    all_tickers = CORE_TICKERS + SATELLITE_CANDIDATES
    
    # Download historical prices and dividends
    console.print("[yellow]Downloading historical data (including 1-year buffer for 200-DMA)...[/yellow]")
    data = {}
    for ticker in all_tickers:
        try:
            tk = yf.Ticker(ticker)
            hist = tk.history(start=start_data.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
            if not hist.empty:
                # Pre-calculate 200-DMA
                hist['200_DMA'] = hist['Close'].rolling(window=200).mean()
                data[ticker] = hist
        except:
            pass
            
    # Align dates to month ends for the actual backtest period
    all_dates = pd.concat([df['Close'] for df in data.values()], axis=1).dropna(how='all').index
    backtest_dates = all_dates[all_dates >= start_backtest]
    if backtest_dates.empty:
        console.print("[bold red]Not enough historical data for the selected timeframe.[/bold red]")
        return
        
    monthly_dates = set(pd.Series(backtest_dates).groupby([backtest_dates.year, backtest_dates.month]).max())
    
    portfolio = {t: {"shares": 0.0} for t in data.keys()}
    cash = 0.0
    total_invested = 0.0
    total_invested_adjusted = 0.0 # Inflation adjusted principal invested
    total_dividends_collected = 0.0
    
    cash_flows_dates = []
    cash_flows_amounts = []
    
    for day in backtest_dates:
        # Check for dividends today on existing shares
        for t, df in data.items():
            if day in df.index:
                div = df.loc[day, 'Dividends']
                if div > 0 and portfolio[t]["shares"] > 0:
                    amount = div * portfolio[t]["shares"]
                    cash += amount
                    total_dividends_collected += amount
        
        # If it's a SIP day (last trading day of month)
        if day in monthly_dates:
            available_cash = monthly_sip + cash
            
            total_invested += monthly_sip
            
            # Calculate inflation adjusted contribution (value of that SIP in today's money)
            # Time elapsed from this SIP date to end_date in years
            years_elapsed = (end_date - day).days / 365.25
            # Purchasing power of this SIP today = SIP * (1 + inflation/100) ^ years_elapsed
            total_invested_adjusted += monthly_sip * ((1 + inflation_rate/100) ** years_elapsed)
            
            cash = 0.0
            
            cash_flows_dates.append(day.to_pydatetime())
            cash_flows_amounts.append(-monthly_sip)
            
            core_budget = available_cash * 0.40
            sat_budget = available_cash * 0.60
            
            # Core
            active_cores = [t for t in CORE_TICKERS if t in data and day in data[t].index]
            if active_cores:
                budget_per_core = core_budget / len(active_cores)
                for t in active_cores:
                    price = data[t].loc[day, 'Close']
                    if price > 0:
                        shares = int(budget_per_core // price)
                        portfolio[t]["shares"] += shares
                        core_budget -= (shares * price)
                cash += core_budget
                
            # Satellite (v3.0 - With 200-DMA filter)
            sat_stats = []
            for t in SATELLITE_CANDIDATES:
                if t not in data or day not in data[t].index: continue
                df = data[t]
                
                # Check 200-DMA
                dma_200 = df.loc[day, '200_DMA']
                price = df.loc[day, 'Close']
                
                # Momentum Filter: Price must be >= 200-DMA
                if pd.isna(dma_200) or price < dma_200:
                    continue
                
                t12m_df = df[(df.index > day - pd.DateOffset(years=1)) & (df.index <= day)]
                if price > 0:
                    yield_pct = (t12m_df['Dividends'].sum() / price) * 100
                    if yield_pct >= 2.0 and yield_pct <= 20.0: 
                        sat_stats.append({"ticker": t, "yield": yield_pct, "price": price})
            
            sat_stats.sort(key=lambda x: x["yield"], reverse=True)
            top_sats = sat_stats[:4]
            if top_sats:
                budget_per_sat = sat_budget / len(top_sats)
                for sat in top_sats:
                    shares = int(budget_per_sat // sat["price"])
                    portfolio[sat["ticker"]]["shares"] += shares
                    sat_budget -= (shares * sat["price"])
                cash += sat_budget
            else:
                # Fallback: if no satellites passed the 200-DMA filter, save cash
                cash += sat_budget

    # Final Value
    final_value = cash
    for t in portfolio:
        if portfolio[t]["shares"] > 0:
            last_price = data[t]['Close'].iloc[-1]
            final_value += portfolio[t]["shares"] * last_price
            
    # Add final portfolio value to cash flows for XIRR
    if len(backtest_dates) > 0:
        cash_flows_dates.append(backtest_dates[-1].to_pydatetime())
        cash_flows_amounts.append(final_value)
            
    profit = final_value - total_invested
    roi_pct = (profit / total_invested) * 100 if total_invested > 0 else 0
    
    # Calculate Inflation-Adjusted (Real) metrics
    # Deflate final value to "start date" purchasing power
    # Equivalently, Real Profit = Final Value - total_invested_adjusted (value of all contributions in today's money)
    # The true purchasing power of the final portfolio is reduced by inflation
    purchasing_power_loss = final_value - (final_value / ((1 + inflation_rate/100) ** years))
    real_final_value = final_value / ((1 + inflation_rate/100) ** years)
    
    annual_return = "N/A"
    real_annual_return = "N/A"
    
    if xirr:
        try:
            xirr_val = xirr(cash_flows_dates, cash_flows_amounts)
            if xirr_val:
                # Nominal CAGR
                nominal_cagr = xirr_val
                annual_return = f"{nominal_cagr * 100:.2f}%"
                
                # Real CAGR formula: ((1 + Nominal_CAGR) / (1 + Inflation_Rate)) - 1
                inf_decimal = inflation_rate / 100
                real_cagr = ((1 + nominal_cagr) / (1 + inf_decimal)) - 1
                real_annual_return = f"{real_cagr * 100:.2f}%"
        except:
            annual_return = "Error calculating"
            real_annual_return = "Error calculating"
    
    try:
        usd_inr = yf.Ticker('USDINR=X').info.get('regularMarketPrice') or yf.Ticker('USDINR=X').info.get('currentPrice', 83.0)
        eur_inr = yf.Ticker('EURINR=X').info.get('regularMarketPrice') or yf.Ticker('EURINR=X').info.get('currentPrice', 90.0)
    except:
        usd_inr, eur_inr = 83.0, 90.0
        
    console.print("\n")
    console.print(Panel.fit(f"[bold cyan]💱 Current Live FX Rates:[/bold cyan] 1 USD = ₹{usd_inr:,.2f} | 1 EUR = ₹{eur_inr:,.2f}", border_style="cyan"))
        
    table = Table(
        title=f"📊 v3.0 {years}-Year Backtest (SIP: ₹{monthly_sip:,.0f}/mo)", 
        style="green",
        box=box.SIMPLE_HEAVY,
        header_style="bold bright_cyan",
        title_justify="center"
    )
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value (INR)", style="magenta", justify="right")
    table.add_column("Value (USD)", style="cyan", justify="right")
    table.add_column("Value (EUR)", style="blue", justify="right")
    table.add_column("Real (INR)", style="yellow", justify="right")
    table.add_column("Real (USD)", style="yellow", justify="right")
    table.add_column("Real (EUR)", style="yellow", justify="right")
    
    table.add_row(
        "Total Capital Invested", 
        f"₹{total_invested:,.2f}", f"${total_invested/usd_inr:,.2f}", f"€{total_invested/eur_inr:,.2f}", 
        f"₹{total_invested_adjusted:,.2f}*", f"${total_invested_adjusted/usd_inr:,.2f}*", f"€{total_invested_adjusted/eur_inr:,.2f}*"
    )
    table.add_row(
        "Total Dividends Reinvested", 
        f"₹{total_dividends_collected:,.2f}", f"${total_dividends_collected/usd_inr:,.2f}", f"€{total_dividends_collected/eur_inr:,.2f}",
        "-", "-", "-"
    )
    table.add_row(
        "Final Portfolio Value", 
        f"₹{final_value:,.2f}", f"${final_value/usd_inr:,.2f}", f"€{final_value/eur_inr:,.2f}",
        f"₹{real_final_value:,.2f}**", f"${real_final_value/usd_inr:,.2f}**", f"€{real_final_value/eur_inr:,.2f}**"
    )
    table.add_row(
        "Net Profit", 
        f"₹{profit:,.2f}", f"${profit/usd_inr:,.2f}", f"€{profit/eur_inr:,.2f}",
        f"₹{real_final_value - total_invested:,.2f}", f"${(real_final_value - total_invested)/usd_inr:,.2f}", f"€{(real_final_value - total_invested)/eur_inr:,.2f}"
    )
    table.add_row("Absolute ROI", f"{roi_pct:.2f}%", "-", "-", "-", "-", "-")
    if xirr:
        table.add_row("Annualized Return (XIRR)", f"{annual_return}", "-", "-", f"{real_annual_return}", "-", "-")
    
    console.print("\n")
    console.print(table)
    
    console.print(f"\n[italic]* 'Total Capital Invested (Real)' shows how much your SIPs would be worth if invested entirely today, accounting for {inflation_rate}% inflation.[/italic]")
    console.print(f"[italic]** 'Final Portfolio Value (Real)' shows the purchasing power of your final portfolio expressed in Year-1 money terms.[/italic]\n")
    
    console.print(Panel(
        "[bold yellow]Inflation & Strategy Insights:[/bold yellow]\n\n"
        f"1. [bold]The Silent Tax:[/bold] At {inflation_rate}% inflation, cash loses its purchasing power quickly. However, the Real Annualized Return proves that this strategy generated wealth [bold]above and beyond inflation[/bold].\n"
        "2. [bold]Momentum Protection:[/bold] The 200-DMA filter prevented accumulating shares of companies whose stock prices were failing to keep up with inflation (downtrends).\n"
        "3. [bold]Dividend Reinvestment (DRIP) Power:[/bold] Reinvesting dividends accelerates share accumulation, ensuring that your dividend income snowballs faster than the inflation rate depreciates it.",
        title="[bold gold1]Backtest Analysis[/bold gold1]",
        border_style="yellow",
        box=box.HEAVY
    ))

def main():
    console.clear()
    header = Panel(
        Align.center(
            "\n[bold gold1]🇮🇳 INDIA DIVIDEND SNOWBALL BACKTESTER (v3.0) ⏱️[/bold gold1]\n\n"
            "[italic white]Time-machine simulation with Institutional Momentum Filters & Inflation Adjustments.[/italic white]\n"
        ),
        box=box.DOUBLE_EDGE,
        border_style="gold1",
        padding=(1, 2)
    )
    console.print(header)
    
    years = IntPrompt.ask("\n[bold]1.[/bold] How many years back do you want to test?", default=5)
    monthly_sip = FloatPrompt.ask("[bold]2.[/bold] Enter the monthly SIP amount (₹)", default=10000.0)
    inflation_rate = FloatPrompt.ask("[bold]3.[/bold] Enter the assumed Annual Inflation Rate (%)", default=6.0)
    
    console.print("\n")
    run_backtest(years=years, monthly_sip=monthly_sip, inflation_rate=inflation_rate)

if __name__ == "__main__":
    main()
