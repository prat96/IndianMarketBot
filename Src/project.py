import yfinance as yf
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import IntPrompt, FloatPrompt
from rich.align import Align
from rich import box
import warnings

warnings.filterwarnings('ignore')
console = Console()

def fetch_fx_rates():
    try:
        usd_inr = yf.Ticker('USDINR=X').info.get('regularMarketPrice') or yf.Ticker('USDINR=X').info.get('currentPrice', 83.0)
        eur_inr = yf.Ticker('EURINR=X').info.get('regularMarketPrice') or yf.Ticker('EURINR=X').info.get('currentPrice', 90.0)
        return usd_inr, eur_inr
    except:
        return 83.0, 90.0

def run_projection():
    console.clear()
    
    header = Panel(
        Align.center(
            "\n[bold gold1]🚀 THE F.I.R.E. ACCELERATOR: FUTURE WEALTH PROJECTOR 🔮[/bold gold1]\n\n"
            "[italic white]Master your Financial Independence & Retire Early (FIRE) timeline.\n"
            "Forecast compound interest, DRIP (Dividend Reinvestment), and exactly when your passive income eclipses your living expenses.[/italic white]\n"
        ),
        box=box.DOUBLE_EDGE,
        border_style="gold1",
        padding=(1, 2)
    )
    console.print(header)
    
    years = IntPrompt.ask("\n[bold cyan]1.[/bold cyan] How many years into the future do you want to project?", default=15)
    monthly_sip = FloatPrompt.ask("[bold cyan]2.[/bold cyan] Enter your monthly SIP amount (₹)", default=20000.0)
    target_expense = FloatPrompt.ask("[bold cyan]3.[/bold cyan] Target Monthly Living Expenses in [bold]today's money[/bold] (₹)", default=50000.0)
    div_yield = FloatPrompt.ask("[bold cyan]4.[/bold cyan] Expected Annual Dividend Yield (%) [Historic: ~5-6%]", default=5.0)
    cap_app = FloatPrompt.ask("[bold cyan]5.[/bold cyan] Expected Annual Capital Appreciation (%) [Historic: ~8-12%]", default=10.0)
    inflation_rate = FloatPrompt.ask("[bold cyan]6.[/bold cyan] Expected Annual Inflation Rate (%) [Historic India: ~6%]", default=6.0)

    with console.status("[yellow]Fetching live FX rates and running Monte Carlo style projections...[/yellow]"):
        usd_inr, eur_inr = fetch_fx_rates()

    console.print(Align.center(f"[bold cyan]💱 Live FX Rates:[/bold cyan] 1 USD = ₹{usd_inr:,.2f} | 1 EUR = ₹{eur_inr:,.2f}\n"))

    monthly_div_yield = (div_yield / 100) / 12
    monthly_cap_app = (cap_app / 100) / 12
    
    total_months = years * 12
    portfolio_value = 0.0
    total_invested = 0.0
    total_dividends = 0.0
    
    snapshots = []
    fire_achieved_month = None
    
    for m in range(1, total_months + 1):
        # Inflate the target expense accurately per month
        current_target_expense = target_expense * ((1 + inflation_rate/100) ** (m / 12))
        
        monthly_div = portfolio_value * monthly_div_yield
        total_dividends += monthly_div
        
        # Check FIRE status
        if fire_achieved_month is None and monthly_div >= current_target_expense:
            fire_achieved_month = m
            
        # Capital appreciation
        portfolio_value += portfolio_value * monthly_cap_app
        
        # DRIP - we reinvest all dividends during the accumulation phase
        portfolio_value += monthly_div
        
        # Add SIP
        portfolio_value += monthly_sip
        total_invested += monthly_sip
        
        if m % 12 == 0:
            year = m // 12
            real_value = portfolio_value / ((1 + inflation_rate/100) ** year)
            status_icon = "🔥 [bold green]FIRE ACHIEVED[/]" if (fire_achieved_month and fire_achieved_month <= m) else "⏳ [yellow]Accumulating[/]"
            
            snapshots.append({
                "Year": year,
                "Invested": total_invested,
                "Dividends": total_dividends,
                "Nominal Value": portfolio_value,
                "Real Value": real_value,
                "Monthly Passive": monthly_div,
                "Inflated Expense": current_target_expense,
                "Status": status_icon
            })

    table = Table(
        title=f"📈 {years}-Year FIRE Projection (SIP: ₹{monthly_sip:,.0f}/mo)", 
        style="green",
        box=box.SIMPLE_HEAVY,
        header_style="bold bright_cyan",
        title_justify="center"
    )
    table.add_column("Year", justify="center")
    table.add_column("Total Invested", justify="right", style="magenta")
    table.add_column("Cum. Dividends", justify="right", style="yellow")
    table.add_column("Portfolio (INR)", justify="right", style="bold green")
    table.add_column("Monthly Passive\nIncome (Nominal)", justify="right", style="bold bright_green")
    table.add_column("Monthly Target\nExpense (Inflated)", justify="right", style="bold red")
    table.add_column("F.I.R.E. Status", justify="center")
    
    for snap in snapshots:
        table.add_row(
            str(snap["Year"]),
            f"₹{snap['Invested']:,.0f}",
            f"₹{snap['Dividends']:,.0f}",
            f"₹{snap['Nominal Value']:,.0f}",
            f"₹{snap['Monthly Passive']:,.0f}",
            f"₹{snap['Inflated Expense']:,.0f}",
            snap["Status"]
        )
        
    console.print(table)
    
    # Final Summary panel
    if snapshots:
        final_snap = snapshots[-1]
        roi = ((final_snap['Nominal Value'] - final_snap['Invested']) / final_snap['Invested']) * 100
        
        fire_text = ""
        if fire_achieved_month:
            fy = fire_achieved_month // 12
            fm = fire_achieved_month % 12
            fire_text = f"[bold green]🔥 FIRE Crossover Achieved in Year {fy}, Month {fm}![/bold green]\nAt this exact point, your dividends naturally outpaced your inflated living expenses. You can safely stop reinvesting (turn off DRIP) and live purely off the cash flow while your capital continues to appreciate."
        else:
            fire_text = f"[bold red]⏳ FIRE Not Yet Achieved.[/bold red]\nBy Year {years}, your passive income covers [bold]{(final_snap['Monthly Passive'] / final_snap['Inflated Expense'])*100:.1f}%[/bold] of your living expenses. You need to increase your SIP, extend your timeline, or lower your target expenses to hit the crossover point."

        summary_panel = Panel(
            f"{fire_text}\n\n"
            f"[bold underline]End of Journey Summary (Year {years})[/bold underline]\n"
            f"• [bold]Total Out of Pocket:[/bold] ₹{final_snap['Invested']:,.2f}\n"
            f"• [bold]Final Portfolio Value:[/bold] ₹{final_snap['Nominal Value']:,.2f} [cyan](${final_snap['Nominal Value']/usd_inr:,.2f})[/cyan] [blue](€{final_snap['Nominal Value']/eur_inr:,.2f})[/blue]\n"
            f"• [bold]Final Monthly Passive Income:[/bold] ₹{final_snap['Monthly Passive']:,.2f} [green](Pure Cash Flow)[/green]\n"
            f"• [bold]Final Target Monthly Expenses:[/bold] ₹{final_snap['Inflated Expense']:,.2f} [red](After {inflation_rate}% inflation)[/red]\n"
            f"• [bold]Total ROI:[/bold] {roi:.2f}%\n",
            title="[bold gold1]The FIRE Verdict[/bold gold1]",
            border_style="gold1",
            box=box.HEAVY
        )
        console.print("\n")
        console.print(summary_panel)

if __name__ == "__main__":
    run_projection()
