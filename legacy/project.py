import yfinance as yf
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import IntPrompt, FloatPrompt
from rich.align import Align
from rich import box
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

def fetch_fx_rates():
    try:
        with SuppressOutput():
            usd_inr = yf.Ticker('USDINR=X').info.get('regularMarketPrice') or yf.Ticker('USDINR=X').info.get('currentPrice', 83.0)
            eur_inr = yf.Ticker('EURINR=X').info.get('regularMarketPrice') or yf.Ticker('EURINR=X').info.get('currentPrice', 90.0)
        return usd_inr, eur_inr
    except:
        return 83.0, 90.0

def run_projection():
    console.clear()
    
    header = Panel(
        Align.center(
            "\n[bold gold1]🌍 CROSS-BORDER F.I.R.E. PROJECTOR (EU -> INDIA) 🚀[/bold gold1]\n\n"
            "[italic white]Master your Financial Independence timeline as a Euro-resident investing in India.\n"
            "This model balances high Indian market returns against INR depreciation and low European inflation.[/italic white]\n"
        ),
        box=box.DOUBLE_EDGE,
        border_style="gold1",
        padding=(1, 2)
    )
    console.print(header)
    
    years = IntPrompt.ask("\n[bold cyan]1.[/bold cyan] How many years into the future do you want to project?", default=15)
    monthly_sip_eur = FloatPrompt.ask("[bold cyan]2.[/bold cyan] Enter your monthly SIP amount in Euros (€)", default=500.0)
    target_expense_eur = FloatPrompt.ask("[bold cyan]3.[/bold cyan] Target Monthly Living Expenses in [bold]today's Euros[/bold] (€)", default=2500.0)
    swr = FloatPrompt.ask("[bold cyan]4.[/bold cyan] Safe Withdrawal Rate (%) [Standard: 3.0 to 4.0%]", default=3.5)
    inr_return = FloatPrompt.ask("[bold cyan]5.[/bold cyan] Expected Indian Market Annual Return (INR %) [Hybrid Avg: 15-20%]", default=16.0)
    inr_depreciation = FloatPrompt.ask("[bold cyan]6.[/bold cyan] Expected Annual INR Depreciation vs EUR (%) [Historic Avg: ~3%]", default=3.0)
    eu_inflation = FloatPrompt.ask("[bold cyan]7.[/bold cyan] Expected European Annual Inflation Rate (%) [Historic Avg: ~2.5%]", default=2.5)

    with console.status("[yellow]Calculating cross-border arbitrage models...[/yellow]"):
        usd_inr, eur_inr = fetch_fx_rates()

    console.print(Align.center(f"[bold cyan]💱 Live FX Rates:[/bold cyan] 1 USD = ₹{usd_inr:,.2f} | 1 EUR = ₹{eur_inr:,.2f}\n"))

    # Cross-Border Math
    # Effective EUR Annual Return = ((1 + INR Return) / (1 + INR Depreciation)) - 1
    effective_eur_return = ((1 + inr_return/100) / (1 + inr_depreciation/100)) - 1
    
    monthly_return = effective_eur_return / 12
    monthly_swr = (swr / 100) / 12
    
    total_months = years * 12
    portfolio_value_eur = 0.0
    total_invested_eur = 0.0
    
    snapshots = []
    fire_achieved_month = None
    
    for m in range(1, total_months + 1):
        # Inflate the target expense accurately per month using EU Inflation
        current_target_expense = target_expense_eur * ((1 + eu_inflation/100) ** (m / 12))
        
        # Calculate how much monthly income the portfolio can generate at the SWR
        safe_monthly_withdrawal = portfolio_value_eur * monthly_swr
        
        # Check FIRE status
        if fire_achieved_month is None and safe_monthly_withdrawal >= current_target_expense:
            fire_achieved_month = m
            
        # Add effective EUR return
        portfolio_value_eur += portfolio_value_eur * monthly_return
        
        # Add EUR SIP
        portfolio_value_eur += monthly_sip_eur
        total_invested_eur += monthly_sip_eur
        
        if m % 12 == 0:
            year = m // 12
            real_value_eur = portfolio_value_eur / ((1 + eu_inflation/100) ** year)
            status_icon = "🔥 [bold green]FIRE ACHIEVED[/]" if (fire_achieved_month and fire_achieved_month <= m) else "⏳ [yellow]Accumulating[/]"
            
            snapshots.append({
                "Year": year,
                "Invested": total_invested_eur,
                "Nominal Value": portfolio_value_eur,
                "Real Value": real_value_eur,
                "Safe Withdrawal": safe_monthly_withdrawal,
                "Inflated Expense": current_target_expense,
                "Status": status_icon
            })

    table = Table(
        title=f"📈 {years}-Year Euro-FIRE Projection (SIP: €{monthly_sip_eur:,.0f}/mo)", 
        style="blue",
        box=box.SIMPLE_HEAVY,
        header_style="bold bright_cyan",
        title_justify="center"
    )
    table.add_column("Year", justify="center")
    table.add_column("Total Invested", justify="right", style="magenta")
    table.add_column("Portfolio (EUR)", justify="right", style="bold green")
    table.add_column(f"Safe Monthly\nWithdrawal ({swr}%)", justify="right", style="bold bright_green")
    table.add_column("Monthly Target\nExpense (Inflated)", justify="right", style="bold red")
    table.add_column("F.I.R.E. Status", justify="center")
    
    for snap in snapshots:
        table.add_row(
            str(snap["Year"]),
            f"€{snap['Invested']:,.0f}",
            f"€{snap['Nominal Value']:,.0f}",
            f"€{snap['Safe Withdrawal']:,.0f}",
            f"€{snap['Inflated Expense']:,.0f}",
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
            fire_text = f"[bold green]🔥 FIRE Crossover Achieved in Year {fy}, Month {fm}![/bold green]\nAt this exact point, your high Indian returns outpaced both currency depreciation and EU inflation. You can safely start withdrawing €{final_snap['Safe Withdrawal']:,.0f}/month to live anywhere in Europe."
        else:
            fire_text = f"[bold red]⏳ FIRE Not Yet Achieved.[/bold red]\nBy Year {years}, your Safe Withdrawal Rate covers [bold]{(final_snap['Safe Withdrawal'] / final_snap['Inflated Expense'])*100:.1f}%[/bold] of your European living expenses."

        summary_panel = Panel(
            f"{fire_text}\n\n"
            f"[bold underline]Cross-Border Summary (Year {years})[/bold underline]\n"
            f"• [bold]Total Out of Pocket:[/bold] €{final_snap['Invested']:,.2f}\n"
            f"• [bold]Final Portfolio Value (EUR):[/bold] €{final_snap['Nominal Value']:,.2f} [cyan](₹{final_snap['Nominal Value']*eur_inr:,.2f})[/cyan]\n"
            f"• [bold]Final Safe Monthly Withdrawal ({swr}% SWR):[/bold] €{final_snap['Safe Withdrawal']:,.2f} [green](Liquid Cash in Europe)[/green]\n"
            f"• [bold]Final Target Monthly Expenses:[/bold] €{final_snap['Inflated Expense']:,.2f} [red](After {eu_inflation}% EU inflation)[/red]\n"
            f"• [bold]Effective EUR Annual Return:[/bold] {effective_eur_return*100:.2f}%\n"
            f"• [bold]Total ROI (in EUR terms):[/bold] {roi:.2f}%\n",
            title="[bold gold1]The Geo-Arbitrage Verdict[/bold gold1]",
            border_style="gold1",
            box=box.HEAVY
        )
        console.print("\n")
        console.print(summary_panel)

if __name__ == "__main__":
    run_projection()
