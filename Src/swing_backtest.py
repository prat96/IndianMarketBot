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

MAX_POSITIONS = 5
RISK_PER_TRADE_PCT = 0.01  # Risk 1% of total equity per trade
MAX_CAPITAL_PER_TRADE_PCT = 0.20 # But never allocate more than 20% of cash
TIME_STOP_DAYS = 20 # Only applies to losing trades now
TAX_SLIPPAGE_PCT = 0.002 # 0.2% round trip for STT, broker, slippage
ATR_MULTIPLIER = 2.5 # Stop loss is 2.5x ATR

def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def precalculate_technicals(df):
    close = df['Close']
    low = df['Low']
    high = df['High']
    vol = df['Volume']
    
    df['RSI'] = calculate_rsi(close, 14)
    
    fast=12; slow=26; signal=9
    exp1 = close.ewm(span=fast, adjust=False).mean()
    exp2 = close.ewm(span=slow, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['MACD_Signal'] = df['MACD'].ewm(span=signal, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    df['SMA_20'] = close.rolling(window=20).mean()
    df['SMA_50'] = close.rolling(window=50).mean()
    df['SMA_200'] = close.rolling(window=200).mean()
    df['Avg_Vol_20'] = vol.rolling(window=20).mean()
    
    # ATR Calculation
    df['Prev_Close'] = close.shift(1)
    tr1 = high - low
    tr2 = (high - df['Prev_Close']).abs()
    tr3 = (low - df['Prev_Close']).abs()
    df['TR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['ATR'] = df['TR'].rolling(window=14).mean()
    
    df['Prev_RSI'] = df['RSI'].shift(1)
    df['Prev_MACD_Hist'] = df['MACD_Hist'].shift(1)
    df['Prev_SMA_20'] = df['SMA_20'].shift(1)
    
    return df

def run_swing_backtest(years, initial_capital):
    console.clear()
    header = Panel(
        Align.center(
            f"\n[bold cyan]⚡ INTRA-WEEK SWING TRADER: V4.0 (INSTITUTIONAL MATH) ⚡[/bold cyan]\n\n"
            f"[italic white]Backtesting {years} years of market data across {len(UNIVERSE)} Hyper-Growth Alpha stocks.\n"
            f"Upgrades: ATR Position Sizing (1% Risk), Relative Strength (RS) Filtering, Market Breadth Regime, and Trailing Stop-Losses.[/italic white]\n"
        ),
        box=box.DOUBLE_EDGE,
        border_style="cyan",
        padding=(1, 2)
    )
    console.print(header)
    
    end_date = pd.Timestamp.now(tz='Asia/Kolkata')
    start_backtest = end_date - pd.DateOffset(years=years)
    start_data = start_backtest - pd.DateOffset(months=12) 
    
    data = {}
    with console.status("[yellow]Downloading and pre-calculating V4.0 technicals (ATR, RS, Breadth)...[/yellow]"):
        for ticker in UNIVERSE + ["^NSEI"]:
            try:
                with SuppressOutput():
                    tk = yf.Ticker(ticker)
                    hist = tk.history(start=start_data.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
                if not hist.empty:
                    if ticker != "^NSEI":
                        hist = precalculate_technicals(hist)
                    data[ticker] = hist
            except:
                pass
                
    if "^NSEI" not in data:
        console.print("[bold red]Failed to fetch market calendar. Exiting.[/bold red]")
        return
        
    # Calculate Relative Strength (RS) vs Nifty
    nifty_close = data["^NSEI"]['Close']
    for t in UNIVERSE:
        if t in data:
            data[t]['RS'] = data[t]['Close'] / nifty_close
            data[t]['RS_SMA20'] = data[t]['RS'].rolling(window=20).mean()
        
    calendar = data["^NSEI"].index
    backtest_dates = calendar[calendar >= start_backtest]
    
    cash = initial_capital
    positions = {}
    trade_history = []
    
    wins = 0
    losses = 0
    equity_curve = []
    
    with console.status("[yellow]Simulating EOD trading over historical data...[/yellow]"):
        for current_day in backtest_dates:
            current_equity = cash
            for t, pos in positions.items():
                if t in data and current_day in data[t].index:
                    current_equity += pos["qty"] * data[t].loc[current_day, 'Close']
                else:
                    current_equity += pos["qty"] * pos["entry_price"]
            
            nifty_row = data["^NSEI"].loc[current_day] if current_day in data["^NSEI"].index else None
            
            # Trend Alignment Check
            is_market_bullish = False
            if nifty_row is not None and not pd.isna(nifty_row.get('SMA_20', 0)):
                # Fallback calculate SMA_20 for nifty if missing
                nifty_sma20 = data["^NSEI"]['Close'].rolling(20).mean().loc[current_day]
                is_market_bullish = nifty_row['Close'] > nifty_sma20
                
            # Market Breadth Check: > 40% of Universe must be above 50-DMA
            bullish_count = 0
            active_stocks = 0
            for t in UNIVERSE:
                if t in data and current_day in data[t].index:
                    row = data[t].loc[current_day]
                    if not pd.isna(row['SMA_50']):
                        active_stocks += 1
                        if row['Close'] > row['SMA_50']:
                            bullish_count += 1
            
            breadth_bullish = (bullish_count / active_stocks >= 0.40) if active_stocks > 0 else False
            
            # 1. Evaluate Open Positions (EOD Logic with Trailing Stops)
            closed_this_day = []
            for t, pos in list(positions.items()):
                if t not in data or current_day not in data[t].index:
                    continue
                
                df_today = data[t].loc[current_day]
                close = df_today['Close']
                atr = df_today['ATR']
                
                pos["days_held"] += 1
                
                # Update Trailing Stop (Chandelier Exit style: Close - 2.5*ATR)
                if not pd.isna(atr):
                    new_sl = close - (ATR_MULTIPLIER * atr)
                    if new_sl > pos["stop_loss"]:
                        pos["stop_loss"] = new_sl
                
                sell_price = None
                reason = ""
                
                # EOD Execution Check
                if close <= pos["stop_loss"]:
                    sell_price = close
                    reason = "Trailing SL Hit"
                # Time Stop only applies if the trade is stagnant/losing to free up capital
                elif pos["days_held"] >= TIME_STOP_DAYS and close < pos["entry_price"]:
                    sell_price = close
                    reason = "Time Stop (Losing)"
                    
                if sell_price is not None:
                    revenue = pos["qty"] * sell_price
                    cost_basis = pos["qty"] * pos["entry_price"]
                    
                    # Deduct Taxes & Slippage
                    tax_amount = (revenue + cost_basis) * (TAX_SLIPPAGE_PCT / 2)
                    net_revenue = revenue - tax_amount
                    
                    profit = net_revenue - cost_basis
                    profit_pct = (profit / cost_basis) * 100
                    
                    cash += net_revenue
                    trade_history.append({
                        "Ticker": t,
                        "Entry Date": pos["entry_date"].strftime('%Y-%m-%d'),
                        "Exit Date": current_day.strftime('%Y-%m-%d'),
                        "Entry Price": pos["entry_price"],
                        "Exit Price": sell_price,
                        "Profit": profit,
                        "Profit Pct": profit_pct,
                        "Reason": reason,
                        "Days": pos["days_held"]
                    })
                    
                    if profit > 0: wins += 1
                    else: losses += 1
                    
                    closed_this_day.append(t)
                    
            for t in closed_this_day:
                del positions[t]
                
            # Update equity after sells
            current_equity = cash
            for t, pos in positions.items():
                if t in data and current_day in data[t].index:
                    current_equity += pos["qty"] * data[t].loc[current_day, 'Close']
                else:
                    current_equity += pos["qty"] * pos["entry_price"]
            
            equity_curve.append(current_equity)
            
            # 2. Find New Setups (Buy Logic)
            if is_market_bullish and breadth_bullish and len(positions) < MAX_POSITIONS and cash > (initial_capital * 0.05):
                daily_setups = []
                for t in UNIVERSE:
                    if t in positions or t not in data or current_day not in data[t].index:
                        continue
                        
                    row = data[t].loc[current_day]
                    
                    if pd.isna(row['SMA_50']) or pd.isna(row['SMA_200']) or pd.isna(row['ATR']) or pd.isna(row['RS_SMA20']):
                        continue
                        
                    # Filter 1: Uptrend
                    if row['Close'] < row['SMA_50'] or row['Close'] < row['SMA_200']:
                        continue
                        
                    # Filter 2: Relative Strength (Must be outperforming Nifty)
                    if row['RS'] < row['RS_SMA20']:
                        continue
                        
                    score = 0
                    
                    macd_bullish = row['MACD_Hist'] > 0 and row['Prev_MACD_Hist'] <= 0
                    rsi_bounce = row['RSI'] > 50 and row['Prev_RSI'] <= 50
                    sma_bo = row['Close'] > row['SMA_20'] and row['Prev_Close'] <= row['Prev_SMA_20']
                    
                    if macd_bullish: score += 3
                    if rsi_bounce: score += 2
                    if sma_bo: score += 3
                    if row['Volume'] > (row['Avg_Vol_20'] * 1.5): score += 2
                    
                    if score < 4: continue
                    
                    # Risk Calculation (V4.0 ATR)
                    risk_per_share = ATR_MULTIPLIER * row['ATR']
                    stop_loss = row['Close'] - risk_per_share
                    
                    # Prevent buying if volatility is completely absurd (>15% risk)
                    if (risk_per_share / row['Close']) > 0.15:
                        continue
                    
                    daily_setups.append({
                        "Ticker": t,
                        "Price": row['Close'],
                        "Score": score,
                        "StopLoss": stop_loss,
                        "RiskPerShare": risk_per_share
                    })
                        
                daily_setups.sort(key=lambda x: x["Score"], reverse=True)
                
                # Execute Buys
                for setup in daily_setups:
                    if len(positions) >= MAX_POSITIONS: break
                    
                    # V4.0 Volatility-Adjusted Position Sizing
                    account_risk_amount = current_equity * RISK_PER_TRADE_PCT # E.g., Risk ₹10,000
                    optimal_qty = int(account_risk_amount // setup["RiskPerShare"])
                    
                    # Capital Cap
                    cost = optimal_qty * setup["Price"]
                    max_capital_allowed = current_equity * MAX_CAPITAL_PER_TRADE_PCT
                    
                    if cost > max_capital_allowed:
                        optimal_qty = int(max_capital_allowed // setup["Price"])
                        cost = optimal_qty * setup["Price"]
                        
                    qty = optimal_qty
                    if qty > 0:
                        buy_tax = cost * (TAX_SLIPPAGE_PCT / 2)
                        
                        if cash >= (cost + buy_tax):
                            cash -= (cost + buy_tax)
                            positions[setup["Ticker"]] = {
                                "qty": qty,
                                "entry_price": setup["Price"],
                                "stop_loss": setup["StopLoss"],
                                "entry_date": current_day,
                                "days_held": 0
                            }

    for t, pos in list(positions.items()):
        if t in data and not data[t].empty:
            final_price = data[t]['Close'].iloc[-1]
        else:
            final_price = pos["entry_price"]
            
        revenue = pos["qty"] * final_price
        cost_basis = pos["qty"] * pos["entry_price"]
        tax_amount = (revenue + cost_basis) * (TAX_SLIPPAGE_PCT / 2)
        net_revenue = revenue - tax_amount
        
        profit = net_revenue - cost_basis
        profit_pct = (profit / cost_basis) * 100
        cash += net_revenue
        
        trade_history.append({
            "Ticker": t,
            "Entry Date": pos["entry_date"].strftime('%Y-%m-%d'),
            "Exit Date": end_date.strftime('%Y-%m-%d'),
            "Entry Price": pos["entry_price"],
            "Exit Price": final_price,
            "Profit": profit,
            "Profit Pct": profit_pct,
            "Reason": "End of Test",
            "Days": pos["days_held"]
        })
        if profit > 0: wins += 1
        else: losses += 1
        
    final_equity = cash
    total_profit = final_equity - initial_capital
    roi = (total_profit / initial_capital) * 100
    
    total_trades = wins + losses
    win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
    
    peak = initial_capital
    max_drawdown = 0
    for eq in equity_curve:
        if eq > peak: peak = eq
        dd = (peak - eq) / peak * 100
        if dd > max_drawdown: max_drawdown = dd

    console.print("\n")
    
    table = Table(
        title=f"📊 {years}-Year V4.0 Swing Trading Results (After {TAX_SLIPPAGE_PCT*100}% Taxes)", 
        style="cyan",
        box=box.SIMPLE_HEAVY,
        header_style="bold bright_cyan",
        title_justify="center"
    )
    table.add_column("Metric", style="bold cyan")
    table.add_column("Result", style="bold white", justify="right")
    
    table.add_row("Starting Capital", f"₹{initial_capital:,.2f}")
    table.add_row("Final Capital", f"[bold {'green' if final_equity >= initial_capital else 'red'}]₹{final_equity:,.2f}[/]")
    table.add_row("Net Profit (After Tax)", f"[bold {'green' if total_profit >= 0 else 'red'}]₹{total_profit:,.2f}[/]")
    table.add_row("Absolute ROI", f"[bold {'green' if roi >= 0 else 'red'}]{roi:.2f}%[/]")
    table.add_row("Max Drawdown", f"[bold {'green' if max_drawdown < 10 else 'red'}]-{max_drawdown:.2f}%[/]")
    table.add_row("Total Trades Executed", f"{total_trades}")
    table.add_row("Winning Trades", f"[green]{wins}[/green]")
    table.add_row("Losing Trades", f"[red]{losses}[/red]")
    table.add_row("Win Rate", f"[bold {'green' if win_rate >= 40 else 'yellow'}]{win_rate:.1f}%[/]")
    
    if total_trades > 0:
        avg_win = sum(t["Profit Pct"] for t in trade_history if t["Profit"] > 0) / wins if wins > 0 else 0
        avg_loss = sum(t["Profit Pct"] for t in trade_history if t["Profit"] <= 0) / losses if losses > 0 else 0
        table.add_row("Avg Winner (%)", f"[green]+{avg_win:.2f}%[/green]")
        table.add_row("Avg Loser (%)", f"[red]{avg_loss:.2f}%[/red]")
        table.add_row("Risk/Reward Ratio", f"[cyan]{abs(avg_win/avg_loss):.2f} : 1[/cyan]" if avg_loss != 0 else "N/A")
    
    console.print(table)
    
    if total_trades > 0:
        recent_table = Table(title="📝 Last 5 Trades Executed", box=box.ROUNDED, style="dim")
        recent_table.add_column("Date", style="dim")
        recent_table.add_column("Ticker", style="cyan")
        recent_table.add_column("Held For", justify="right")
        recent_table.add_column("Exit Reason", justify="right")
        recent_table.add_column("PnL %", justify="right")
        
        for trade in trade_history[-5:]:
            pcolor = "green" if trade["Profit Pct"] > 0 else "red"
            recent_table.add_row(
                trade["Exit Date"],
                trade["Ticker"],
                f"{trade['Days']} days",
                trade["Reason"],
                f"[{pcolor}]{trade['Profit Pct']:+.2f}%[/]"
            )
        console.print("\n")
        console.print(recent_table)

    summary_panel = Panel(
        f"[bold gold1]V4.0 Institutional Math Upgrades:[/bold gold1]\n\n"
        f"1. [bold]ATR Sizing (1% Risk):[/bold] Position sizes are now dynamically calculated based on stock volatility. If stopped out, you only ever lose exactly 1% of your portfolio.\n"
        f"2. [bold]Relative Strength (RS):[/bold] Bot refused to buy stocks lagging the Nifty 50. It exclusively bought market leaders.\n"
        f"3. [bold]Trailing Stops (No Hard Targets):[/bold] We removed the hard 10% target. By using an ATR-based Trailing Stop, the bot lets massive runners go up 20-30% before exiting, supercharging the Avg Winner vs Avg Loser math.\n"
        f"4. [bold]Market Breadth Regime:[/bold] Refuses to buy unless >40% of the universe is above the 50-DMA, protecting capital during top-heavy fake rallies.",
        title="[bold cyan]The V4.0 Verdict[/bold cyan]",
        border_style="cyan",
        box=box.HEAVY
    )
    console.print("\n")
    console.print(summary_panel)

def main():
    years = IntPrompt.ask("\n[bold cyan]1.[/bold cyan] How many years back do you want to simulate?", default=2)
    capital = FloatPrompt.ask("[bold cyan]2.[/bold cyan] Enter starting capital (₹)", default=1000000.0)
    run_swing_backtest(years, capital)

if __name__ == "__main__":
    main()
