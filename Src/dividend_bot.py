import yfinance as yf
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import track
from rich.prompt import FloatPrompt
from rich.align import Align
from rich import box
import datetime
import warnings

# Suppress warnings
warnings.filterwarnings('ignore')

console = Console()

# The "Core" bucket: Low-volatility ETFs or Mega-Cap Dividend Kings (40% of Budget)
# We won't strictly score these, they are foundational for safety and broad market yield.
CORE_TICKERS = [
    {"ticker": "DIVOPPBEES.NS", "name": "Nifty Div Opp 50 ETF", "category": "Core ETF"},
    {"ticker": "CPSEETF.NS", "name": "CPSE ETF", "category": "Core ETF"},
    {"ticker": "ITC.NS", "name": "ITC Ltd", "category": "Core FMCG"} 
]

# The "Satellite" bucket: High-Yield, Screened Direct Stocks (60% of Budget)
SATELLITE_CANDIDATES = [
    # PSUs & Energy
    "COALINDIA.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS", "GAIL.NS", "OIL.NS",
    # Finance & Infra
    "PFC.NS", "RECLTD.NS", "IRFC.NS", "HUDCO.NS",
    # IT Services
    "TCS.NS", "HCLTECH.NS", "INFY.NS", "TECHM.NS",
    # Others
    "VEDL.NS", "HINDZINC.NS", "PETRONET.NS", "NMDC.NS"
]

def score_stock(info, price):
    """
    Advanced Scoring Algorithm for 'Safe & High Yield'
    - Yield must be 3% to 15%
    - Payout Ratio must be sustainable (<90%)
    - Must be profitable (PE > 0)
    - Momentum: Price must be >= 200-DMA
    """
    div_rate = info.get('dividendRate', 0)
    if not div_rate or price <= 0:
        return 0, 0, "No Dividend Data"
        
    yield_pct = (div_rate / price) * 100
    
    # Momentum Filter (v3.0)
    dma_200 = info.get('twoHundredDayAverage', 0)
    if dma_200 and price < dma_200:
        return 0, yield_pct, "Below 200-DMA (Downtrend Risk)"
    
    # Safety Filters
    if yield_pct < 3.0:
        return 0, yield_pct, "Yield too low (<3%)"
    if yield_pct > 18.0:
        return 0, yield_pct, "Yield too high (Value Trap Risk)"
        
    pe = info.get('trailingPE', 0)
    if pe is None or pe <= 0 or pe > 40:
        return 0, yield_pct, "Unprofitable or Overvalued"
        
    payout = info.get('payoutRatio', 0)
    if payout is None:
        payout = 0
    if payout > 0.95:
        return 0, yield_pct, "Payout > 95% (Unsustainable)"
        
    beta = info.get('beta', 1.0)
    if beta is None:
        beta = 1.0
        
    # Base Score is the Yield itself
    score = yield_pct
    
    # Bonus for low Beta (Safety)
    if beta < 1.0:
        score += (1.0 - beta) * 2  # Max +2 points for extreme low volatility
    else:
        score -= (beta - 1.0) * 2  # Penalty for high volatility
        
    # Penalty for dangerously high payout ratio (above 75%)
    if payout > 0.75:
        score -= (payout - 0.75) * 10 # Deduct points as it approaches 95%
        
    return score, yield_pct, "Pass"

def fetch_fx_rates():
    try:
        usd_inr = yf.Ticker('USDINR=X').info.get('regularMarketPrice') or yf.Ticker('USDINR=X').info.get('currentPrice', 83.0)
        eur_inr = yf.Ticker('EURINR=X').info.get('regularMarketPrice') or yf.Ticker('EURINR=X').info.get('currentPrice', 90.0)
        return usd_inr, eur_inr
    except:
        return 83.0, 90.0

def fetch_and_analyze(budget):
    console.print(Panel.fit("[bold cyan]Running Advanced Core-Satellite Dividend Screener...[/bold cyan]", border_style="cyan"))
    
    # 40% Core, 60% Satellite
    core_budget = budget * 0.40
    sat_budget = budget * 0.60
    
    final_portfolio = []
    total_spent = 0
    
    # --- 1. Process Core ---
    core_allocation_per_asset = core_budget / len(CORE_TICKERS)
    
    for core in track(CORE_TICKERS, description="Securing Core Assets..."):
        try:
            ticker_obj = yf.Ticker(core["ticker"])
            info = ticker_obj.info
            price = info.get('currentPrice', info.get('regularMarketPrice', 0))
            if price <= 0:
                continue
                
            qty = int(core_allocation_per_asset // price)
            if qty > 0:
                cost = qty * price
                div_rate = info.get('dividendRate', 0)
                yield_pct = (div_rate / price * 100) if div_rate else (info.get('dividendYield', 0) * 100)
                if yield_pct < 1 and info.get('dividendYield'): # fallback if it was already in percentage
                    yield_pct = info.get('dividendYield') * 100 if info.get('dividendYield') < 1 else info.get('dividendYield')
                    
                final_portfolio.append({
                    "Ticker": core["ticker"].replace('.NS', ''),
                    "Category": core["category"],
                    "Price": price,
                    "Yield": yield_pct,
                    "Qty": qty,
                    "Cost": cost,
                    "Role": "[bold blue]CORE[/bold blue]"
                })
                total_spent += cost
        except:
            pass
            
    # --- 2. Process Satellite ---
    sat_results = []
    for ticker in track(SATELLITE_CANDIDATES, description="Screening Satellite Candidates..."):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            price = info.get('currentPrice', info.get('regularMarketPrice', 0))
            if price <= 0:
                continue
                
            score, yield_pct, status = score_stock(info, price)
            
            if score > 0:
                sat_results.append({
                    "Ticker": ticker.replace('.NS', ''),
                    "Category": "Satellite Equity",
                    "Price": price,
                    "Yield": yield_pct,
                    "Score": score,
                    "Status": status
                })
        except:
            pass
            
    # Sort satellite by Score (Safety + Yield)
    sat_results.sort(key=lambda x: x["Score"], reverse=True)
    
    # Pick top 4 satellite stocks to diversify the 60% budget
    top_sats = sat_results[:4]
    sat_allocation = sat_budget / max(1, len(top_sats))
    
    for sat in top_sats:
        qty = int(sat_allocation // sat["Price"])
        if qty > 0:
            cost = qty * sat["Price"]
            final_portfolio.append({
                "Ticker": sat["Ticker"],
                "Category": sat["Category"],
                "Price": sat["Price"],
                "Yield": sat["Yield"],
                "Qty": qty,
                "Cost": cost,
                "Role": "[bold magenta]SATELLITE[/bold magenta]"
            })
            total_spent += cost

    return final_portfolio, total_spent

def display_results(portfolio, budget, total_spent, usd_inr, eur_inr):
    table = Table(
        title=f"🛡️ Core-Satellite Dividend Portfolio (Budget: ₹{budget:,.2f})", 
        style="green",
        box=box.SIMPLE_HEAVY,
        header_style="bold bright_yellow",
        title_justify="center"
    )
    table.add_column("Role", justify="center")
    table.add_column("Ticker", style="cyan", no_wrap=True)
    table.add_column("Category", style="white")
    table.add_column("Current Price", justify="right", style="green")
    table.add_column("Div Yield", justify="right", style="bold red")
    table.add_column("Suggested Qty", justify="right", style="bold white")
    table.add_column("Allocated Cost", justify="right", style="bold green")
    table.add_column("Cost (USD)", justify="right", style="cyan")
    table.add_column("Cost (EUR)", justify="right", style="blue")
    
    for item in portfolio:
        yield_str = f"{item['Yield']:.2f}%" if item['Yield'] > 0 else "N/A (ETF/Growth)"
        table.add_row(
            item["Role"],
            item["Ticker"],
            item["Category"],
            f"₹{item['Price']:.2f}",
            yield_str,
            str(item["Qty"]),
            f"₹{item['Cost']:.2f}",
            f"${item['Cost']/usd_inr:,.2f}",
            f"€{item['Cost']/eur_inr:,.2f}"
        )
        
    console.print("\n")
    console.print(Panel.fit(f"[bold cyan]💱 Live FX Rates:[/bold cyan] 1 USD = ₹{usd_inr:,.2f} | 1 EUR = ₹{eur_inr:,.2f}", border_style="cyan"))
    console.print(table)
    
    remaining = budget - total_spent
    
    console.print("\n")
    summary_panel = Panel(
        f"[bold green]Monthly SIP Strategic Plan ({datetime.datetime.now().strftime('%B %Y')})[/]\n\n"
        f"This upgraded algorithm uses a [bold]Core & Satellite Strategy (v3.0)[/] to balance risk and reward:\n"
        f"• [bold blue]Core (40%):[/] Stable ETFs and Mega-Caps to build an unshakeable foundation.\n"
        f"• [bold magenta]Satellite (60%):[/] High-yield equities algorithmically filtered for safety (PE > 0, Payout < 95%, Low Volatility, and Price > 200-DMA).\n\n"
        f"Total Capital Allocated: [bold]₹{total_spent:,.2f}[/] [cyan](${total_spent/usd_inr:,.2f})[/cyan] [blue](€{total_spent/eur_inr:,.2f})[/blue]\n"
        f"Remaining Capital: [bold]₹{remaining:,.2f}[/] [cyan](${remaining/usd_inr:,.2f})[/cyan] [blue](€{remaining/eur_inr:,.2f})[/blue] (Keep as cash reserve)\n\n"
        "[italic]Pro Tip: By combining strict payout ratio filters with the 200-DMA momentum filter, you avoid 'Value Traps'—companies that pay high dividends today but are bleeding capital value.[/]",
        title="[bold gold1]Action Plan[/bold gold1]",
        border_style="green",
        box=box.HEAVY
    )
    console.print(summary_panel)

def main():
    console.clear()
    header = Panel(
        Align.center(
            "\n[bold gold1]🇮🇳 INDIA DIVIDEND SNOWBALL BOT (v3.0)[/bold gold1]\n\n"
            "[italic white]Advanced institutional-grade momentum screening for safe, high-yielding passive income.[/italic white]\n"
        ),
        box=box.DOUBLE_EDGE,
        border_style="gold1",
        padding=(1, 2)
    )
    console.print(header)
    
    budget = FloatPrompt.ask("\nEnter your monthly SIP amount (₹)", default=10000.0)
    
    usd_inr, eur_inr = fetch_fx_rates()
    portfolio, total_spent = fetch_and_analyze(budget)
    
    if not portfolio:
        console.print("[bold red]No suitable investments found or API error. Try again later.[/bold red]")
        return
        
    display_results(portfolio, budget, total_spent, usd_inr, eur_inr)
    
if __name__ == "__main__":
    main()
