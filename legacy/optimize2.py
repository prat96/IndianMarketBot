import yfinance as yf
import pandas as pd
import warnings
from datetime import datetime

warnings.filterwarnings('ignore')

UNIVERSE = [
    "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "ITC.NS",
    "TCS.NS", "LT.NS", "KOTAKBANK.NS", "AXISBANK.NS", "SBIN.NS",
    "BHARTIARTL.NS", "BAJFINANCE.NS", "ASIANPAINT.NS", "MARUTI.NS",
    "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS", "M&M.NS",
    "TATASTEEL.NS", "POWERGRID.NS", "NTPC.NS", "COALINDIA.NS", "ONGC.NS",
    "TRENT.NS", "HAL.NS", "DIXON.NS", "BSE.NS", "CDSL.NS",
    "INDIGO.NS", "DLF.NS", "BAJAJ-AUTO.NS", "EICHERMOT.NS", "HINDALCO.NS"
]

def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def precalc(df):
    df['SMA_20'] = df['Close'].rolling(20).mean()
    df['SMA_50'] = df['Close'].rolling(50).mean()
    df['SMA_200'] = df['Close'].rolling(200).mean()
    df['RSI'] = calculate_rsi(df['Close'], 14)
    df['Prev_RSI'] = df['RSI'].shift(1)
    df['Avg_Vol_20'] = df['Volume'].rolling(20).mean()
    return df

end_date = pd.Timestamp.now(tz='Asia/Kolkata')
start_data = end_date - pd.DateOffset(years=3)

data = {}
for ticker in UNIVERSE + ["^NSEI"]:
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(start=start_data.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
        if not hist.empty:
            hist = precalc(hist)
            data[ticker] = hist
    except: pass

backtest_dates = data["^NSEI"].index[data["^NSEI"].index >= (end_date - pd.DateOffset(years=2))]

for ts in [5, 10]:
    for rsi_thresh in [35, 40]:
        for rr in [2.0, 3.0]:
            cash = 1000000.0
            positions = {}
            wins = 0; losses = 0

            for current_day in backtest_dates:
                nifty = data["^NSEI"].loc[current_day] if current_day in data["^NSEI"].index else None
                is_bull = nifty is not None and nifty['Close'] > nifty['SMA_200']
                
                closed = []
                for t, pos in positions.items():
                    if t not in data or current_day not in data[t].index: continue
                    row = data[t].loc[current_day]
                    
                    pos['days'] += 1
                    sell_px = None
                    
                    if row['Low'] <= pos['stop_loss']:
                        sell_px = min(pos['stop_loss'], row['Open'])
                    elif row['High'] >= pos['target']:
                        sell_px = max(pos['target'], row['Open'])
                    elif pos['days'] >= ts:
                        sell_px = row['Close']
                    
                    if sell_px is not None:
                        rev = pos['qty'] * sell_px
                        cost = pos['qty'] * pos['entry']
                        tax = (rev + cost) * 0.001
                        net = rev - tax
                        profit = net - cost
                        cash += net
                        if profit > 0: wins += 1
                        else: losses += 1
                        closed.append(t)
                        
                for t in closed: del positions[t]
                
                current_eq = cash + sum(p['qty']*data[k].loc[current_day, 'Close'] for k,p in positions.items() if k in data and current_day in data[k].index)
                
                if is_bull and len(positions) < 5:
                    setups = []
                    for t in UNIVERSE:
                        if t in positions or t not in data or current_day not in data[t].index: continue
                        row = data[t].loc[current_day]
                        
                        if pd.isna(row['SMA_200']) or pd.isna(row['Prev_RSI']): continue
                        
                        # Mean reversion setup
                        if row['Close'] > row['SMA_200'] and row['Prev_RSI'] < rsi_thresh and row['RSI'] >= rsi_thresh:
                            sl = row['Close'] * 0.95
                            risk = row['Close'] - sl
                            target = row['Close'] + (risk * rr)
                            setups.append((t, row['Close'], sl, target))
                            
                    for setup in setups:
                        if len(positions) >= 5: break
                        t, px, sl, target = setup
                        trade_cap = min(cash, current_eq * 0.20)
                        qty = int(trade_cap // px)
                        if qty > 0:
                            cost = qty * px
                            tax = cost * 0.001
                            if cash >= cost + tax:
                                cash -= (cost + tax)
                                positions[t] = {
                                    'qty': qty, 'entry': px, 'stop_loss': sl, 'target': target, 'days': 0
                                }

            for t, pos in list(positions.items()):
                final_px = data[t]['Close'].iloc[-1]
                rev = pos['qty'] * final_px
                cost = pos['qty'] * pos['entry']
                tax = (rev + cost) * 0.001
                net = rev - tax
                profit = net - cost
                cash += net

            print(f"TS: {ts}, RSI: {rsi_thresh}, RR: {rr} -> Final Cash: {cash:.2f} | Wins: {wins}, Losses: {losses}")
