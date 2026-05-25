import yfinance as yf
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import track
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

# Hyper-Growth / Alpha Universe
UNIVERSE = [
    "TRENT.NS", "RELIANCE.NS", "VBL.NS", "BSE.NS", "CDSL.NS",
    "HAL.NS", "TATAPOWER.NS", "DIXON.NS", "BAJAJ-AUTO.NS",
    "BHARTIARTL.NS", "ADANIPOWER.NS", "LT.NS", "HDFCBANK.NS",
    "MOMOMENTUM.NS", "TCS.NS", "ZOMATO.NS", "INDIGO.NS", 
    "COALINDIA.NS", "NTPC.NS", "POWERGRID.NS"
]

def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(data, fast=12, slow=26, signal=9):
    exp1 = data.ewm(span=fast, adjust=False).mean()
    exp2 = data.ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line
    return macd, signal_line, histogram

def analyze_stock(ticker):
    try:
        with SuppressOutput():
            tk = yf.Ticker(ticker)
            # Need at least a few months of data for MACD and RSI
            hist = tk.history(period="1y")
            
        if hist.empty or len(hist) < 200:
            return None
            
        close = hist['Close']
        low = hist['Low']
        vol = hist['Volume']
        
        # Calculate Technical Indicators
        rsi = calculate_rsi(close, 14)
        macd, macd_signal, macd_hist = calculate_macd(close)
        
        current_price = close.iloc[-1]
        prev_price = close.iloc[-2]
        
        # Moving Averages
        sma_20 = close.rolling(window=20).mean().iloc[-1]
        sma_50 = close.rolling(window=50).mean().iloc[-1]
        sma_200 = close.rolling(window=200).mean().iloc[-1]
        prev_sma_20 = close.rolling(window=20).mean().iloc[-2]
        
        avg_vol = vol.rolling(window=20).mean().iloc[-1]
        
        # Trend Filter
        if current_price < sma_50 or current_price < sma_200:
            return None
            
        score = 0
        reasons = []
        
        # 1. MACD Momentum
        if macd_hist.iloc[-1] > 0 and macd_hist.iloc[-2] <= 0:
            score += 3
            reasons.append("MACD Bullish Cross")
            
        # 2. RSI Sweet Spot (Room to grow, not overbought)
        if rsi.iloc[-1] > 50 and rsi.iloc[-2] <= 50:
            score += 2
            reasons.append(f"RSI > 50 Bounce")
            
        # 3. Price action vs 20-DMA (Short term trend)
        if current_price > sma_20 and prev_price <= prev_sma_20:
            score += 3
            reasons.append("20-DMA Breakout")
            
        # 4. Volume Expansion
        if vol.iloc[-1] > (avg_vol * 1.5):
            score += 2
            reasons.append("Volume Breakout (>1.5x Avg)")
            
        # Stop Loss: Recent swing low or max 6% risk
        recent_low = low.iloc[-5:].min()
        stop_loss = max(recent_low, current_price * 0.94)
        risk = current_price - stop_loss
        
        # Target: Minimum 2.5x Risk
        target = current_price + (risk * 2.5)
        potential_upside = ((target - current_price) / current_price) * 100
        potential_downside = ((current_price - stop_loss) / current_price) * 100
        
        # Minimum viability for a setup
        if score >= 4 and potential_upside >= 5.0: 
            return {
                "Ticker": ticker.replace('.NS', ''),
                "Price": current_price,
                "Score": score,
                "StopLoss": stop_loss,
                "Target": target,
                "Upside": potential_upside,
                "Downside": potential_downside,
                "Triggers": ", ".join(reasons)
            }
        return None
    except Exception as e:
        return None

def main():
    console.clear()
    header = Panel(
        Align.center(
            "\n[bold cyan]⚡ INTRA-WEEK SWING TRADER BOT (V3.0 ALPHA MOMENTUM) ⚡[/bold cyan]\n\n"
            "[italic white]Scans the top 20 Hyper-Growth Alpha stocks for strict EOD momentum breakouts.\n"
            "Optimized for 15-day holding periods with strict Risk/Reward mechanics & Nifty Trend Alignment.[/italic white]\n"
        ),
        box=box.DOUBLE_EDGE,
        border_style="cyan",
        padding=(1, 2)
    )
    console.print(header)
    
    # Check Nifty Trend
    try:
        with console.status("[yellow]Checking broad market regime...[/yellow]"):
            with SuppressOutput():
                nifty = yf.Ticker("^NSEI").history(period="2mo")
            nifty_price = nifty['Close'].iloc[-1]
            nifty_sma20 = nifty['Close'].rolling(window=20).mean().iloc[-1]
            is_market_bullish = nifty_price > nifty_sma20
    except:
        is_market_bullish = True

    if not is_market_bullish:
        console.print(Panel("[bold red]Market Regime Alert: Nifty 50 is below its 20-DMA. The algorithm recommends holding CASH rather than opening new swing longs.[/bold red]", border_style="red"))
    else:
        console.print("[bold green]Market Regime: Nifty 50 is in a short-term uptrend (>20-DMA). Bullish setups authorized.[/bold green]\n")
        
    setups = []
    for ticker in track(UNIVERSE, description="Scanning Alpha Universe..."):
        result = analyze_stock(ticker)
        if result:
            setups.append(result)
            
    if not setups:
        console.print(Panel("[bold red]No high-probability V3.0 swing setups found today. Cash is a position. Do not force trades.[/bold red]", border_style="red"))
        return
        
    setups.sort(key=lambda x: x["Score"], reverse=True)
    top_setups = setups[:5] # Display Top 5 absolute best setups
    
    table = Table(
        title="🎯 TOP V3.0 SWING SETUPS (Buy EOD / Hold ~15 Days)", 
        style="cyan",
        box=box.SIMPLE_HEAVY,
        header_style="bold bright_yellow",
        title_justify="center"
    )
    table.add_column("Ticker", style="bold cyan")
    table.add_column("Current Price", justify="right", style="white")
    table.add_column("Stop Loss", justify="right", style="bold red")
    table.add_column("Target (RR > 2.5)", justify="right", style="bold green")
    table.add_column("Upside %", justify="right", style="green")
    table.add_column("Score", justify="center", style="bold magenta")
    table.add_column("Technical Triggers", style="italic white")
    
    for setup in top_setups:
        table.add_row(
            setup["Ticker"],
            f"₹{setup['Price']:,.2f}",
            f"₹{setup['StopLoss']:,.2f} (-{setup['Downside']:.1f}%)",
            f"₹{setup['Target']:,.2f}",
            f"+{setup['Upside']:.1f}%",
            str(setup["Score"]),
            setup["Triggers"]
        )
        
    console.print("\n")
    console.print(table)
    
    console.print("\n")
    summary = Panel(
        "[bold gold1]Execution Rules (Real Money Ready):[/bold gold1]\n"
        "1. [bold]EOD Execution:[/bold] ONLY execute these trades between 3:15 PM - 3:25 PM IST to prevent indicator repainting.\n"
        "2. [bold]Strict Stop Loss:[/bold] Place the GTT (Good Till Triggered) Stop Loss order [italic]immediately[/italic] after buying.\n"
        "3. [bold]Taxes & Slippage:[/bold] Ensure your position size accounts for ~0.2% round-trip tax/slippage.\n"
        "4. [bold]Time Stop:[/bold] If the stock doesn't hit target within 15 trading days, close the position and free up capital.",
        title="[bold red]⚠️ Trading Discipline[/bold red]",
        border_style="red",
        box=box.HEAVY
    )
    console.print(summary)

if __name__ == "__main__":
    main()
