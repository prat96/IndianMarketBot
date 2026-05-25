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
import sys
import os

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

# --- UNIVERSE DEFINITION ---
SAFE_CORE_ETFS = [
    {"ticker": "NIFTYBEES.NS", "name": "Nifty 50 ETF (Large Cap)"},
    {"ticker": "JUNIORBEES.NS", "name": "Nifty Next 50 ETF (Emerging)"}
]

# High-Growth / Alpha Universe (Small/Mid/Momentum Large Caps)
ALPHA_CANDIDATES = [
    "TRENT.NS", "RELIANCE.NS", "VBL.NS", "BSE.NS", "CDSL.NS",
    "HAL.NS", "TATAPOWER.NS", "DIXON.NS", "BAJAJ-AUTO.NS",
    "BHARTIARTL.NS", "ADANIPOWER.NS", "LT.NS", "HDFCBANK.NS",
    "MOMOMENTUM.NS", "MID150BEES.NS", "TCS.NS"
]

def fetch_fx_rates():
    try:
        usd_inr = yf.Ticker('USDINR=X').info.get('regularMarketPrice') or yf.Ticker('USDINR=X').info.get('currentPrice', 83.0)
        eur_inr = yf.Ticker('EURINR=X').info.get('regularMarketPrice') or yf.Ticker('EURINR=X').info.get('currentPrice', 90.0)
        return usd_inr, eur_inr
    except:
        return 83.0, 90.0

def score_momentum(info, hist, price):
    """
    Momentum Scoring Algorithm (Route 3):
    - Price must be > 200 DMA (Uptrend)
    - Price must be within 20% of 52-week high
    - Highest 6-month return wins
    """
    if hist.empty or len(hist) < 120:
        return 0, "Not enough data"
        
    dma_200 = hist['Close'].rolling(window=200).mean().iloc[-1] if len(hist) >= 200 else hist['Close'].mean()
    
    if price < dma_200:
        return 0, "Below 200-DMA (Downtrend)"
        
    high_52 = info.get('fiftyTwoWeekHigh', price)
    if high_52 and price < (high_52 * 0.80):
        return 0, "Too far from 52W High (>20%)"
        
    # Calculate 6-month momentum (approx 126 trading days)
    if len(hist) > 126:
        price_6m_ago = hist['Close'].iloc[-126]
        momentum_6m = ((price - price_6m_ago) / price_6m_ago) * 100
    else:
        momentum_6m = 0
        
    score = momentum_6m
    return score, "Pass"

def run_fire_bot(budget_eur):
    console.print("\n")
    
    usd_inr, eur_inr = fetch_fx_rates()
    budget = budget_eur * eur_inr
    
    # 1. Market Trend Check (Is Nifty 50 above 200 DMA?)
    try:
        with console.status("[yellow]Checking broad market regime...[/yellow]"):
            with SuppressOutput():
                nifty = yf.Ticker("^NSEI")
                nifty_hist = nifty.history(period="1y")
            nifty_price = nifty_hist['Close'].iloc[-1]
            nifty_200dma = nifty_hist['Close'].rolling(window=200).mean().iloc[-1]
            is_bull_market = nifty_price > nifty_200dma
    except:
        is_bull_market = True # default to bull if fetch fails

    market_status = "[bold green]BULL MARKET (Risk-ON)[/bold green]" if is_bull_market else "[bold red]BEAR MARKET (Risk-OFF)[/bold red]"
    console.print(Align.center(f"[bold]Market Regime Analysis:[/bold] Nifty 50 is currently in a {market_status}\n"))
    
    final_portfolio = []
    total_spent = 0
    
    # Dynamic Allocation based on Market Regime
    if is_bull_market:
        core_budget = budget * 0.40  # 40% Safe Index
        alpha_budget = budget * 0.60 # 60% Aggressive Momentum
    else:
        core_budget = budget * 0.80  # 80% Safe Index (Buy the dip safely)
        alpha_budget = budget * 0.20 # 20% Aggressive (Reduced exposure)
        
    # --- 1. CORE ALLOCATION (ROUTE 2) ---
    core_alloc_per_asset = core_budget / len(SAFE_CORE_ETFS)
    for core in track(SAFE_CORE_ETFS, description="Allocating Core Index Funds..."):
        try:
            with SuppressOutput():
                tk = yf.Ticker(core["ticker"])
                price = tk.info.get('regularMarketPrice') or tk.info.get('currentPrice', 0)
                if price == 0:
                    price = tk.history(period="1d")['Close'].iloc[-1]
                
            qty = int(core_alloc_per_asset // price)
            if qty > 0:
                cost = qty * price
                final_portfolio.append({
                    "Role": "[bold blue]CORE (Route 2)[/bold blue]",
                    "Ticker": core["ticker"].replace('.NS', ''),
                    "Name": core["name"],
                    "Price": price,
                    "Qty": qty,
                    "Cost": cost,
                    "Momentum": "N/A (Index)"
                })
                total_spent += cost
        except:
            pass
            
    # --- 2. ALPHA ALLOCATION (ROUTE 3) ---
    alpha_results = []
    for ticker in track(ALPHA_CANDIDATES, description="Screening Hyper-Growth Alpha..."):
        try:
            with SuppressOutput():
                tk = yf.Ticker(ticker)
                info = tk.info
                hist = tk.history(period="1y")
            
            price = info.get('regularMarketPrice') or info.get('currentPrice', 0)
            if price == 0:
                price = hist['Close'].iloc[-1]
                
            score, status = score_momentum(info, hist, price)
            
            if score > 0:
                alpha_results.append({
                    "Ticker": ticker.replace('.NS', ''),
                    "Name": "Momentum Equity/ETF",
                    "Price": price,
                    "Score": score,
                })
        except:
            pass
            
    # Sort by 6-month momentum
    alpha_results.sort(key=lambda x: x["Score"], reverse=True)
    
    # Pick Top 3 Alpha Assets
    top_alphas = alpha_results[:3]
    if top_alphas:
        alpha_alloc_per_asset = alpha_budget / len(top_alphas)
        for alpha in top_alphas:
            qty = int(alpha_alloc_per_asset // alpha["Price"])
            if qty > 0:
                cost = qty * alpha["Price"]
                final_portfolio.append({
                    "Role": "[bold magenta]ALPHA (Route 3)[/bold magenta]",
                    "Ticker": alpha["Ticker"],
                    "Name": alpha["Name"],
                    "Price": alpha["Price"],
                    "Qty": qty,
                    "Cost": cost,
                    "Momentum": f"{alpha['Score']:.1f}% (6M)"
                })
                total_spent += cost
    
    # Render Table
    table = Table(
        title=f"🔥 F.I.R.E. Accumulation Portfolio (Budget: €{budget_eur:,.0f} | ₹{budget:,.2f})", 
        style="green",
        box=box.SIMPLE_HEAVY,
        header_style="bold bright_yellow",
        title_justify="center"
    )
    table.add_column("Strategy", justify="center")
    table.add_column("Ticker", style="cyan", no_wrap=True)
    table.add_column("Current Price", justify="right", style="green")
    table.add_column("6M Momentum", justify="right", style="bold red")
    table.add_column("Suggested Qty", justify="right", style="bold white")
    table.add_column("Cost (INR)", justify="right", style="bold green")
    table.add_column("Cost (EUR)", justify="right", style="blue")
    
    for item in final_portfolio:
        table.add_row(
            item["Role"],
            item["Ticker"],
            f"₹{item['Price']:.2f}",
            item["Momentum"],
            str(item["Qty"]),
            f"₹{item['Cost']:.2f}",
            f"€{item['Cost']/eur_inr:,.2f}"
        )
        
    console.print("\n")
    console.print(Panel.fit(f"[bold cyan]💱 Live FX Rates:[/bold cyan] 1 USD = ₹{usd_inr:,.2f} | 1 EUR = ₹{eur_inr:,.2f}", border_style="cyan"))
    console.print(table)
    
    remaining = budget - total_spent
    
    orders_text = ""
    for item in final_portfolio:
        orders_text += f"   [bold green]BUY[/bold green] [bold white]{item['Qty']} shares[/bold white] of [bold cyan]{item['Ticker']}[/bold cyan] [italic](Market or Limit ~₹{item['Price']:.2f})[/italic]\n"
    
    summary_panel = Panel(
        f"[bold gold1]🛒 YOUR BROKER SHOPPING LIST (Zerodha / Groww / Upstox)[/bold gold1]\n"
        f"[italic]Log into your Demat account and execute the following orders to stay on track for F.I.R.E:[/italic]\n\n"
        f"{orders_text}\n"
        f"Total Capital Allocated: [bold]₹{total_spent:,.2f}[/] [blue](€{total_spent/eur_inr:,.2f})[/blue]\n"
        f"Remaining Capital: [bold]₹{remaining:,.2f}[/] [blue](€{remaining/eur_inr:,.2f})[/blue] (Hold as cash reserve)\n\n"
        f"[italic]Regime Note:[/italic] Because the market is {market_status}, the algorithm dynamically allocated {core_budget/budget*100:.0f}% to Core and {alpha_budget/budget*100:.0f}% to Alpha this month.",
        title=f"[bold green]Monthly Geo-Arbitrage Execution Plan ({datetime.datetime.now().strftime('%B %Y')})[/bold green]",
        border_style="green",
        box=box.HEAVY
    )
    console.print("\n")
    console.print(summary_panel)

def main():
    console.clear()
    header = Panel(
        Align.center(
            "\n[bold gold1]🌍 CROSS-BORDER F.I.R.E. WEALTH BUILDER BOT (HYBRID STRATEGY)[/bold gold1]\n\n"
            "[italic white]Maximum speed accumulation phase optimized for Euro-residents investing in India.\n"
            "Dynamically blends broad-market indexing with explosive momentum stocks based on market regimes.[/italic white]\n"
        ),
        box=box.DOUBLE_EDGE,
        border_style="gold1",
        padding=(1, 2)
    )
    console.print(header)
    
    budget_eur = FloatPrompt.ask("\nEnter your monthly SIP amount in Euros (€)", default=500.0)
    run_fire_bot(budget_eur)

if __name__ == "__main__":
    main()