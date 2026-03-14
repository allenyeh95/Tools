# ================================================
# Hyperliquid ATR 顯示器
# ================================================
import pandas as pd
import numpy as np
import mplfinance as mpf
import matplotlib.pyplot as plt
import requests
import time

# ====================== 設定區 ======================
API_URL = "https://api.hyperliquid.xyz/info"
COIN = "BTC"
INTERVAL = "30m"          
NUM_CANDLES = 300

# ====================== 拉取 K 線 ======================
def fetch_hyperliquid_candles(coin=COIN, interval=INTERVAL, num_candles=NUM_CANDLES):
    end_time = int(time.time() * 1000)
    
    interval_ms_map = {
        "1m": 60000, "5m": 300000, "15m": 900000, "30m": 1800000,
        "1h": 3600000, "4h": 14400000, "1d": 86400000
    }
    interval_ms = interval_ms_map.get(interval, 3600000)
    
    start_time = int(end_time - (num_candles * interval_ms))
    
    payload = {
        "type": "candleSnapshot",
        "req": {
            "coin": coin,
            "interval": interval,
            "startTime": start_time,
            "endTime": end_time
        }
    }
    
    print("Sending payload:", payload)
    resp = requests.post(API_URL, json=payload, timeout=10)
    
    if resp.status_code != 200:
        print("Error response:", resp.text)
        raise Exception(f"API 錯誤 {resp.status_code}: {resp.text}")
    
    data = resp.json()
    print(f"抓到 {len(data)} 根 K 線")
    return data

# ====================== ATR 計算 ======================
def calculate_atr(df, period=14):
    high = df['High']
    low = df['Low']
    prev_close = df['Close'].shift(1)
    
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    atr = true_range.copy()
    atr.iloc[:period] = true_range.iloc[:period].mean()
    
    for i in range(period, len(atr)):
        atr.iloc[i] = (atr.iloc[i-1] * (period - 1) + true_range.iloc[i]) / period
    return atr

# ====================== 主程式 ======================
if __name__ == "__main__":
    try:
        raw_candles = fetch_hyperliquid_candles()
        
        df = pd.DataFrame(raw_candles)
        df['Open']  = pd.to_numeric(df['o'])
        df['High']  = pd.to_numeric(df['h'])
        df['Low']   = pd.to_numeric(df['l'])
        df['Close'] = pd.to_numeric(df['c'])
        df['Volume']= pd.to_numeric(df['v'])
        
        df['timestamp'] = pd.to_datetime(df['t'], unit='ms')
        df = df.set_index('timestamp').sort_index()
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        
        # 計算 ATR
        df['ATR_14'] = calculate_atr(df, period=14)
        df['ATR_7']  = calculate_atr(df, period=7)
        
        atr14_plot = mpf.make_addplot(
            df['ATR_14'], panel=1, color='#ff9800', ylabel='ATR', label='ATR 14'
        )
        atr7_plot = mpf.make_addplot(
            df['ATR_7'], panel=1, color='#2196f3', label='ATR 7'
        )
        
        apds = [atr14_plot, atr7_plot]
        
        mpf.plot(
            df,
            type='candle',
            style='binance',
            addplot=apds,
            title=f'Hyperliquid {COIN} {INTERVAL} + ATR',
            ylabel='價格 (USDC)',
            ylabel_lower='ATR',
            panel_ratios=(4, 1.5),
            figscale=1.6,              
            figratio=(16, 9),           
            datetime_format='%m-%d %H:%M',  
            xrotation=0,                
            volume=True,
            show_nontrading=False,
            tight_layout=True
        )
        
        plt.show()
        
    except Exception as e:
        print(f"執行失敗: {e}")