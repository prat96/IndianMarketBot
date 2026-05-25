import yfinance as yf
import pandas as pd
import json
import time
import os
import sys
import random
from datetime import datetime, timezone
import pytz
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.align import Align
from rich.text import Text
from rich import box
import warnings

warnings.filterwarnings('ignore')

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "virtual_account_state.json")
MAX_POSITIONS = 10 # Expanded portfolio size
RISK_PER_TRADE_PCT = 0.01  # Risk 1% of total equity per trade
MAX_CAPITAL_PER_TRADE_PCT = 0.20 # Max 20% of cash per trade
TIME_STOP_DAYS = 20
TAX_SLIPPAGE_PCT = 0.002
ATR_MULTIPLIER = 2.5

# Expanded Universe: Top 100+ Highly Liquid F&O Stocks (The True Indian Market)
UNIVERSE = [
    "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "ITC.NS", "TCS.NS", "LT.NS", "KOTAKBANK.NS", 
    "AXISBANK.NS", "SBIN.NS", "BHARTIARTL.NS", "BAJFINANCE.NS", "ASIANPAINT.NS", "MARUTI.NS", "SUNPHARMA.NS", 
    "TITAN.NS", "ULTRACEMCO.NS", "TATAMOTORS.NS", "M&M.NS", "TATASTEEL.NS", "POWERGRID.NS", "NTPC.NS", 
    "COALINDIA.NS", "ONGC.NS", "ZOMATO.NS", "TRENT.NS", "HAL.NS", "DIXON.NS", "BSE.NS", "CDSL.NS", 
    "INDIGO.NS", "DLF.NS", "BAJAJ-AUTO.NS", "EICHERMOT.NS", "HINDALCO.NS", "ADANIENT.NS", "ADANIPORTS.NS",
    "APOLLOHOSP.NS", "BAJAJFINSV.NS", "BPCL.NS", "BRITANNIA.NS", "CIPLA.NS", "DIVISLAB.NS", "DRREDDY.NS",
    "GRASIM.NS", "HCLTECH.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS", "HINDUNILVR.NS", "INDUSINDBK.NS", "JSWSTEEL.NS",
    "LTIM.NS", "NESTLEIND.NS", "TATACOMP.NS", "TECHM.NS", "WIPRO.NS", "BEL.NS", "CHOLAFIN.NS", "PIDILITIND.NS",
    "SHREECEM.NS", "TATACONSUM.NS", "TVSMOTOR.NS", "AMBUJACEM.NS", "AUBANK.NS", "BANKBARODA.NS", "CANBK.NS",
    "CUMMINSIND.NS", "DABUR.NS", "ESCORTS.NS", "GAIL.NS", "GODREJCP.NS", "HAVELLS.NS", "ICICIPRULI.NS", 
    "IRCTC.NS", "JUBLFOOD.NS", "LUPIN.NS", "MARICO.NS", "MUTHOOTFIN.NS", "NAUKRI.NS", "NMDC.NS", "PETRONET.NS",
    "PFC.NS", "PIIND.NS", "PNB.NS", "POLYCAB.NS", "RECLTD.NS", "SAIL.NS", "SIEMENS.NS", "SRF.NS", 
    "TORNTPHARM.NS", "TRENT.NS", "UPL.NS", "VEDL.NS", "VOLTAS.NS"
]

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

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
            if "equity_history" not in state: state["equity_history"] = [1000000.0]
            if "bot_thoughts" not in state: state["bot_thoughts"] = ["System Initialized."]
            for t, p in state["positions"].items():
                if "days_held" not in p: p["days_held"] = 0
            return state
    return {
        "cash": 1000000.0,
        "positions": {},
        "history": [],
        "logs": ["Virtual account initialized with ₹1,000,000.00"],
        "equity_history": [1000000.0],
        "bot_thoughts": ["System Initialized."]
    }

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=4)

def log_event(state, message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"[{timestamp}] {message}"
    state["logs"].insert(0, formatted_msg)
    state["logs"] = state["logs"][:15]

def log_thought(state, message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    state["bot_thoughts"].insert(0, f"[dim]{timestamp}[/dim] {message}")
    state["bot_thoughts"] = state["bot_thoughts"][:10]

def generate_sparkline(data, width=40):
    if not data: return ""
    data = data[-width:]
    bars = " ▂▃▄▅▆▇█"
    min_val, max_val = min(data), max(data)
    if min_val == max_val: return bars[3] * len(data)
    return "".join(bars[int((v - min_val) / (max_val - min_val) * 7)] for v in data)

# --- Technical Analysis Functions ---
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

def get_market_regime(state):
    try:
        log_thought(state, "Scanning Nifty 50 for Market Regime and Broad Breadth...")
        with SuppressOutput():
            # Get Nifty and all Universe history rapidly
            market_data = yf.download(["^NSEI"] + UNIVERSE, period="1y", progress=False)
            
        close_data = market_data['Close']
        if "^NSEI" not in close_data.columns or close_data["^NSEI"].dropna().empty:
            return True, True, None # Fail safe
            
        nifty_close = close_data["^NSEI"].dropna()
        nifty_sma20 = nifty_close.rolling(window=20).mean().iloc[-1]
        nifty_price = nifty_close.iloc[-1]
        
        is_nifty_bullish = nifty_price > nifty_sma20
        
        # Calculate Market Breadth (>40% of Universe > 50-DMA)
        active_stocks = 0
        bullish_stocks = 0
        
        for t in UNIVERSE:
            if t in close_data.columns:
                stock_close = close_data[t].dropna()
                if len(stock_close) >= 50:
                    active_stocks += 1
                    sma50 = stock_close.rolling(window=50).mean().iloc[-1]
                    if stock_close.iloc[-1] > sma50:
                        bullish_stocks += 1
                        
        breadth_bullish = False
        if active_stocks > 0:
            breadth_bullish = (bullish_stocks / active_stocks) >= 0.40
            
        return is_nifty_bullish, breadth_bullish, close_data["^NSEI"]
        
    except Exception as e:
        log_thought(state, f"[red]Regime Scan Error: {e}[/red]")
        return True, True, None

def analyze_stock(ticker, state, nifty_series):
    try:
        log_thought(state, f"Analyzing V4.0 setup for [cyan]{ticker}[/cyan]...")
        with SuppressOutput():
            tk = yf.Ticker(ticker)
            hist = tk.history(period="1y")
            
        if hist.empty or len(hist) < 200: 
            return None
            
        close = hist['Close']
        low = hist['Low']
        high = hist['High']
        vol = hist['Volume']
        
        rsi = calculate_rsi(close, 14)
        macd, macd_signal, macd_hist = calculate_macd(close)
        
        current_price = close.iloc[-1]
        prev_price = close.iloc[-2]
        
        sma_20 = close.rolling(window=20).mean().iloc[-1]
        sma_50 = close.rolling(window=50).mean().iloc[-1]
        sma_200 = close.rolling(window=200).mean().iloc[-1]
        prev_sma_20 = close.rolling(window=20).mean().iloc[-2]
        
        avg_vol = vol.rolling(window=20).mean().iloc[-1]
        
        # ATR
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean().iloc[-1]
        
        # Relative Strength (RS)
        if nifty_series is not None and not nifty_series.empty:
            # Align dates
            aligned_close = close.reindex(nifty_series.index).ffill()
            rs = aligned_close / nifty_series
            rs_sma20 = rs.rolling(window=20).mean()
            if not rs.empty and not rs_sma20.empty and not pd.isna(rs.iloc[-1]) and not pd.isna(rs_sma20.iloc[-1]):
                if rs.iloc[-1] < rs_sma20.iloc[-1]:
                    # Underperforming Nifty
                    return None
        
        # Trend Filter V4.0
        if current_price < sma_50 or current_price < sma_200:
            return None
            
        score = 0
        reasons = []
        
        if macd_hist.iloc[-1] > 0 and macd_hist.iloc[-2] <= 0:
            score += 3
            reasons.append("MACD Cross")
            
        if rsi.iloc[-1] > 50 and rsi.iloc[-2] <= 50:
            score += 3
            reasons.append("RSI > 50 BO")
            
        if current_price > sma_20 and prev_price <= prev_sma_20:
            score += 3
            reasons.append("20-DMA BO")
            
        if vol.iloc[-1] > (avg_vol * 1.5):
            score += 2
            reasons.append("Vol BO")
            
        if score < 4: return None
        
        # V4.0 Risk Management
        risk_per_share = ATR_MULTIPLIER * atr
        stop_loss = current_price - risk_per_share
        
        # Prevent absurd volatility
        if (risk_per_share / current_price) > 0.15:
            return None
        
        log_thought(state, f"[green]Found V4.0 setup on {ticker}![/green] Score: {score}")
        return {
            "Ticker": ticker,
            "Price": current_price,
            "Score": score,
            "StopLoss": stop_loss,
            "RiskPerShare": risk_per_share,
            "ATR": atr,
            "Triggers": ", ".join(reasons)
        }
    except Exception as e:
        return None

def fetch_current_prices(tickers):
    prices = {}
    try:
        with SuppressOutput():
            # Get current prices rapidly
            data = yf.download(tickers, period="1d", progress=False)['Close']
            if isinstance(data, pd.Series): # Only 1 ticker
                prices[tickers[0]] = float(data.iloc[-1])
            else:
                for ticker in tickers:
                    if ticker in data.columns and not pd.isna(data[ticker].iloc[-1]):
                        prices[ticker] = float(data[ticker].iloc[-1])
    except:
        pass
    return prices

def generate_layout(state, current_prices):
    total_equity = state["cash"]
    invested = 0.0
    for t, pos in state["positions"].items():
        cp = current_prices.get(t, pos["entry_price"])
        val = pos["qty"] * cp
        total_equity += val
        invested += val
        
    pnl_pct = ((total_equity - 1000000.0) / 1000000.0) * 100
    pnl_color = "green" if pnl_pct >= 0 else "red"
    
    if not state["equity_history"] or state["equity_history"][-1] != total_equity:
        state["equity_history"].append(total_equity)
        if len(state["equity_history"]) > 100:
            state["equity_history"] = state["equity_history"][-100:]
            
    sparkline = generate_sparkline(state["equity_history"], width=40)
    
    # Check Market Hours
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    is_market_open = (now.weekday() < 5) and (now.hour > 9 or (now.hour == 9 and now.minute >= 15)) and (now.hour < 15 or (now.hour == 15 and now.minute <= 30))
    status_str = "[bold green]LIVE MARKET[/bold green]" if is_market_open else "[bold yellow]MARKET CLOSED (Simulating)[/bold yellow]"
    
    header = Panel(
        Align.center(
            f"[bold gold1]⚡ 24/7 ALGORITHMIC PAPER TRADING SIMULATOR (V4.0 INSTITUTIONAL) ⚡[/bold gold1]\n"
            f"[italic white]Status: {status_str} | Cache: [bold cyan]ON[/bold cyan] | Slippage: [bold red]0.2%[/bold red] | Risk Mgt: [bold green]ATR Sizing[/bold green][/italic white]"
        ),
        box=box.DOUBLE_EDGE,
        border_style="gold1"
    )
    
    summary_text = (
        f"[bold]Total Equity (Net):[/bold] [bold {pnl_color}]₹{total_equity:,.2f}[/] ({pnl_pct:+.2f}%)\n"
        f"[bold]Available Cash:[/bold] [bold cyan]₹{state['cash']:,.2f}[/]\n"
        f"[bold]Capital Invested:[/bold] [bold magenta]₹{invested:,.2f}[/]\n"
        f"[bold]Open Positions:[/bold] {len(state['positions'])} / {MAX_POSITIONS}\n"
        f"[bold]Completed Trades:[/bold] {len(state['history'])}\n\n"
        f"[bold gold1]Equity Curve:[/bold gold1]\n[bold {pnl_color}]{sparkline}[/]"
    )
    summary_panel = Panel(summary_text, title="[bold blue]🏦 Account Overview[/bold blue]", border_style="blue", box=box.ROUNDED)
    
    pos_table = Table(box=box.SIMPLE_HEAVY, header_style="bold bright_cyan", expand=True)
    pos_table.add_column("Ticker", style="cyan")
    pos_table.add_column("Qty", justify="right")
    pos_table.add_column("Entry", justify="right")
    pos_table.add_column("Current Live", justify="right", style="bold white")
    pos_table.add_column("Trail SL", justify="right", style="red")
    pos_table.add_column("Days", justify="right")
    pos_table.add_column("Net PnL %", justify="right")
    
    for t, pos in state["positions"].items():
        cp = current_prices.get(t, pos["entry_price"])
        revenue = pos["qty"] * cp
        cost_basis = pos["qty"] * pos["entry_price"]
        tax = (revenue + cost_basis) * (TAX_SLIPPAGE_PCT / 2)
        net_revenue = revenue - tax
        
        pnl = ((net_revenue - cost_basis) / cost_basis) * 100
        pnl_str = f"[{'green' if pnl >= 0 else 'red'}]{pnl:+.2f}%[/]"
        
        pos_table.add_row(
            t.replace('.NS', ''),
            str(pos["qty"]),
            f"₹{pos['entry_price']:,.2f}",
            f"₹{cp:,.2f}",
            f"₹{pos['stop_loss']:,.2f}",
            str(pos.get("days_held", 0)),
            pnl_str
        )
        
    if not state["positions"]:
        pos_table.add_row("No Active Trades", "-", "-", "-", "-", "-", "-")
        
    pos_panel = Panel(pos_table, title="[bold green]📊 Live Portfolio Positions[/bold green]", border_style="green", box=box.ROUNDED)
    
    thoughts_text = "\n".join(state["bot_thoughts"])
    thoughts_panel = Panel(thoughts_text, title="[bold magenta]🧠 Bot Brain (V4.0 Scanner)[/bold magenta]", border_style="magenta", box=box.ROUNDED)
    
    log_text = "\n".join(state["logs"]) if state["logs"] else "No executions yet."
    log_panel = Panel(log_text, title="[bold yellow]📝 Order Execution Logs[/bold yellow]", border_style="yellow", box=box.ROUNDED)
    
    layout = Layout()
    layout.split_column(
        Layout(header, size=5),
        Layout(name="main", ratio=1)
    )
    layout["main"].split_row(
        Layout(name="left", ratio=1),
        Layout(name="right", ratio=2)
    )
    layout["left"].split_column(
        Layout(summary_panel, size=11),
        Layout(thoughts_panel, size=14),
        Layout(log_panel, ratio=1)
    )
    layout["right"].update(pos_panel)
    
    return layout

def trade_loop():
    state = load_state()
    console = Console()
    console.clear()
    
    last_processed_date = datetime.now().strftime("%Y-%m-%d")
    
    with Live(generate_layout(state, {}), refresh_per_second=2, screen=True) as live:
        loop_counter = 0
        while True:
            try:
                today_str = datetime.now().strftime("%Y-%m-%d")
                if today_str != last_processed_date:
                    for t in state["positions"]:
                        state["positions"][t]["days_held"] = state["positions"][t].get("days_held", 0) + 1
                    last_processed_date = today_str
                    save_state(state)

                open_tickers = list(state["positions"].keys())
                current_prices = {}
                if open_tickers:
                    log_thought(state, "[bold blue]Updating live quotes & Trailing Stops...[/bold blue]")
                    current_prices = fetch_current_prices(open_tickers)
                    
                    # Update Trailing Stops for active positions
                    for t, pos in state["positions"].items():
                        cp = current_prices.get(t)
                        if cp and "atr" in pos:
                            new_sl = cp - (ATR_MULTIPLIER * pos["atr"])
                            if new_sl > pos["stop_loss"]:
                                pos["stop_loss"] = new_sl
                                
                    live.update(generate_layout(state, current_prices))
                    
                positions_to_close = []
                for t, pos in state["positions"].items():
                    cp = current_prices.get(t)
                    if cp:
                        if cp <= pos["stop_loss"]:
                            positions_to_close.append((t, cp, "Trailing SL Hit"))
                        elif pos.get("days_held", 0) >= TIME_STOP_DAYS and cp < pos["entry_price"]:
                            positions_to_close.append((t, cp, "Time Stop (Losing)"))
                            
                for t, cp, reason in positions_to_close:
                    pos = state["positions"][t]
                    revenue = pos["qty"] * cp
                    cost_basis = pos["qty"] * pos["entry_price"]
                    tax_amount = (revenue + cost_basis) * (TAX_SLIPPAGE_PCT / 2)
                    net_revenue = revenue - tax_amount
                    
                    profit = net_revenue - cost_basis
                    profit_pct = (profit / cost_basis) * 100
                    
                    state["cash"] += net_revenue
                    state["history"].append({
                        "ticker": t,
                        "entry": pos["entry_price"],
                        "exit": cp,
                        "profit": profit,
                        "profit_pct": profit_pct,
                        "reason": reason,
                        "date": datetime.now().strftime("%Y-%m-%d")
                    })
                    del state["positions"][t]
                    
                    color = "green" if profit >= 0 else "red"
                    log_event(state, f"[{color}]{reason}:[/] Sold {pos['qty']} {t} @ ₹{cp:,.2f} | Net PnL: ₹{profit:,.2f} ({profit_pct:+.2f}%)")
                    log_thought(state, f"[{color}]Executed SELL order for {t}.[/]")
                    
                loop_counter += 1
                if loop_counter % 3 == 0 and len(state["positions"]) < MAX_POSITIONS and state["cash"] > 10000:
                    
                    # Nifty Trend & Breadth Alignment Check
                    is_bull_market, breadth_bullish, nifty_series = get_market_regime(state)
                    
                    if not is_bull_market:
                        log_thought(state, "[yellow]Nifty < 20-DMA (Bear Regime). New longs paused.[/yellow]")
                    elif not breadth_bullish:
                        log_thought(state, "[yellow]Market Breadth < 40%. Top-Heavy Rally. Pausing.[/yellow]")
                    else:
                        # Scan a random batch of 5 stocks from the expanded universe
                        scan_batch = random.sample([x for x in UNIVERSE if x not in state["positions"]], 5)
                        log_thought(state, f"Initiating scan on batch: {', '.join([x.replace('.NS', '') for x in scan_batch])}")
                        live.update(generate_layout(state, current_prices))
                        
                        best_setup = None
                        for ticker in scan_batch:
                            result = analyze_stock(ticker, state, nifty_series)
                            live.update(generate_layout(state, current_prices))
                            if result:
                                if not best_setup or result["Score"] > best_setup["Score"]:
                                    best_setup = result
                                    
                        if best_setup:
                            t = best_setup["Ticker"]
                            price = best_setup["Price"]
                            
                            total_equity = state["cash"] + sum([p["qty"]*current_prices.get(k, p["entry_price"]) for k, p in state["positions"].items()])
                            
                            # V4.0 Volatility-Adjusted Position Sizing
                            account_risk_amount = total_equity * RISK_PER_TRADE_PCT
                            optimal_qty = int(account_risk_amount // best_setup["RiskPerShare"])
                            
                            cost = optimal_qty * price
                            max_capital_allowed = total_equity * MAX_CAPITAL_PER_TRADE_PCT
                            
                            if cost > max_capital_allowed:
                                optimal_qty = int(max_capital_allowed // price)
                                cost = optimal_qty * price
                                
                            qty = optimal_qty
                            
                            if qty > 0:
                                buy_tax = cost * (TAX_SLIPPAGE_PCT / 2)
                                
                                if state["cash"] >= (cost + buy_tax):
                                    state["cash"] -= (cost + buy_tax)
                                    state["positions"][t] = {
                                        "qty": qty,
                                        "entry_price": price,
                                        "stop_loss": best_setup["StopLoss"],
                                        "atr": best_setup["ATR"],
                                        "date": datetime.now().strftime("%Y-%m-%d"),
                                        "days_held": 0
                                    }
                                    log_event(state, f"[bold cyan]BUY EXECUTED:[/] {qty} {t} @ ₹{price:,.2f} | Reason: {best_setup['Triggers']}")
                                    log_thought(state, f"[bold green]Allocated {cost/total_equity*100:.1f}% capital to {t} (Risk: 1%)[/bold green]")
                else:
                    if len(state["positions"]) >= MAX_POSITIONS:
                        log_thought(state, "[yellow]Portfolio FULL. Monitoring Trailing Stops...[/yellow]")
                    elif loop_counter % 3 != 0:
                        log_thought(state, "Awaiting next scan cycle... (Cache/API cooldown)")
                            
                save_state(state)
                live.update(generate_layout(state, current_prices))
                
                # 10 second loop
                time.sleep(10)
                
            except Exception as e:
                log_thought(state, f"[red]System Error: {str(e)}[/red]")
                time.sleep(10)

if __name__ == "__main__":
    try:
        trade_loop()
    except KeyboardInterrupt:
        print("\nPaper Trader stopped gracefully. State saved.")