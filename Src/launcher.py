"""
Indian Market Bot — unified launcher.

Run this and pick a bot from a menu. Saves you remembering the script names.

    python Src/launcher.py
"""
import os
import sys
import subprocess
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.align import Align
from rich.prompt import IntPrompt
from rich import box

console = Console()
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

BOTS = [
    {
        "key": "1",
        "script": "fire_builder_bot.py",
        "title": "F.I.R.E. Wealth Builder (Hybrid Index + Momentum)",
        "tag": "[bold green]LIVE[/bold green]",
        "blurb": "Monthly SIP allocator. 40/60 Core/Alpha in bull, 80/20 in bear. EUR-denominated.",
    },
    {
        "key": "2",
        "script": "dividend_bot.py",
        "title": "Dividend Snowball Screener (Core + Satellite)",
        "tag": "[bold green]LIVE[/bold green]",
        "blurb": "High-yield Indian stocks with 200-DMA momentum filter to avoid value traps.",
    },
    {
        "key": "3",
        "script": "swing_trade_bot.py",
        "title": "Intra-Week Swing Trader (15-day holds)",
        "tag": "[bold green]LIVE[/bold green]",
        "blurb": "EOD scanner. MACD + RSI + 20-DMA breakout + volume confirmation.",
    },
    {
        "key": "4",
        "script": "paper_trader.py",
        "title": "Paper Trader (Live virtual account)",
        "tag": "[bold yellow]LOOP[/bold yellow]",
        "blurb": "Continuous virtual trading during NSE hours. Persists state across runs.",
    },
    {
        "key": "5",
        "script": "backtest.py",
        "title": "Geo-Arbitrage Backtester (Dividend Snowball)",
        "tag": "[bold cyan]BACKTEST[/bold cyan]",
        "blurb": "EUR -> INR historical simulation with dynamic FX & XIRR computation.",
    },
    {
        "key": "6",
        "script": "swing_backtest.py",
        "title": "Swing Strategy Backtester (V4.0 — ATR sizing)",
        "tag": "[bold cyan]BACKTEST[/bold cyan]",
        "blurb": "1%-risk ATR position sizing, RS filter, market breadth regime.",
    },
    {
        "key": "7",
        "script": "project.py",
        "title": "Cross-Border F.I.R.E. Projector",
        "tag": "[bold magenta]PROJECT[/bold magenta]",
        "blurb": "Forward-looking projection of EUR portfolio under Indian returns + INR drift.",
    },
]


def banner():
    console.clear()
    console.print(
        Panel(
            Align.center(
                "\n[bold gold1]🇮🇳  INDIAN MARKET BOT — UNIFIED LAUNCHER  🇮🇳[/bold gold1]\n\n"
                "[italic white]One menu, every strategy. Pick a bot and go.[/italic white]\n"
            ),
            box=box.DOUBLE_EDGE,
            border_style="gold1",
            padding=(1, 2),
        )
    )


def menu():
    table = Table(
        title="Available Bots",
        box=box.SIMPLE_HEAVY,
        header_style="bold bright_cyan",
        title_justify="center",
        show_lines=False,
    )
    table.add_column("#", justify="center", style="bold")
    table.add_column("Kind", justify="center")
    table.add_column("Bot", style="bold white")
    table.add_column("What it does", style="dim")

    for bot in BOTS:
        table.add_row(bot["key"], bot["tag"], bot["title"], bot["blurb"])
    table.add_row("0", "[red]EXIT[/red]", "Quit launcher", "")
    console.print(table)


def main():
    while True:
        banner()
        menu()
        try:
            choice = IntPrompt.ask("\n[bold cyan]Pick a bot[/bold cyan]", default=1)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye.[/dim]")
            return

        if choice == 0:
            console.print("\n[dim]Goodbye.[/dim]")
            return

        match = next((b for b in BOTS if int(b["key"]) == choice), None)
        if not match:
            console.print(f"[red]No bot at #{choice}. Try again.[/red]")
            continue

        script_path = os.path.join(SCRIPT_DIR, match["script"])
        if not os.path.exists(script_path):
            console.print(f"[red]Missing script: {script_path}[/red]")
            continue

        console.print(
            f"\n[bold green]>> launching[/bold green] [cyan]{match['script']}[/cyan]\n"
        )
        try:
            subprocess.run([sys.executable, script_path], cwd=SCRIPT_DIR, check=False)
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted.[/yellow]")

        console.input("\n[dim]press Enter to return to menu...[/dim]")


if __name__ == "__main__":
    main()
