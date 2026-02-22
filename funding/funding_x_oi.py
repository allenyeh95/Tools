import requests
import time
import os
from datetime import datetime
from colorama import init, Fore, Style

# Initialize Colorama (autoreset on Windows)
init(autoreset=True)

def get_hyperliquid_funding():
    """Enhanced Hyperliquid Funding Rate Monitor with Open Interest (USD)"""
    
    url = "https://api.hyperliquid.xyz/info"
    payload = {"type": "metaAndAssetCtxs"}
    
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if not isinstance(data, list) or len(data) < 2:
                raise ValueError("Abnormal API response format")
                
            meta = data[0]
            asset_ctxs = data[1]
            
            funding_list = []
            for i, ctx in enumerate(asset_ctxs):
                if i >= len(meta['universe']):
                    continue
                coin = meta['universe'][i]['name']
                try:
                    funding = float(ctx['funding']) * 100  # Convert to percentage
                    
                    # Correct OI calculation: coins * mark price = USD value
                    oi_coins = float(ctx.get('openInterest', 0))
                    mark_px = float(ctx.get('markPx', 0))
                    oi_usd = oi_coins * mark_px if mark_px > 0 else 0.0
                    
                except (KeyError, ValueError):
                    funding = 0.0
                    oi_coins = 0.0
                    oi_usd = 0.0
                    mark_px = 0.0
                
                funding_list.append({
                    'coin': coin,
                    'funding': funding,
                    'oi_usd': oi_usd,              # USD value (for comparison)
                    'oi_coins': oi_coins,           # Coin units (raw data)
                    'mark_px': mark_px,              # Current mark price
                    'weighted_score': abs(funding) * oi_usd  # % × USD (meaningful across coins)
                })
            
            # Sort by weighted score (most significant markets first)
            funding_list.sort(key=lambda x: x['weighted_score'], reverse=True)
            
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"\n{Fore.CYAN}=== Hyperliquid Funding Monitor (USD Open Interest) ==={Style.RESET_ALL}")
            print(f"{Fore.WHITE}Update Time: {now}   (Hourly Settlement){Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Sorting by: Funding Rate × Open Interest (USD) - Market Significance{Style.RESET_ALL}")
            print("-" * 90)
            
            # Positive Funding Top 5 (by weighted score)
            print(f"🟢 Positive Funding Rate Top 5 (by Market Significance):{Style.RESET_ALL}")
            positive = [x for x in funding_list if x['funding'] > 0]
            for i, item in enumerate(positive[:5], 1):
                sign = '+' if item['funding'] >= 0 else ''
                oi_display = format_usd(item['oi_usd'])
                score_display = format_score(item['weighted_score'])
                print(f"{Fore.GREEN}  {i:2d}. {item['coin']:<8} {sign}{item['funding']:7.4f}%  | OI: {oi_display:>12}  | Score: {score_display:>10}  | Price: ${item['mark_px']:<8.4f}{Style.RESET_ALL}")
            
            print()
            
            # Negative Funding Top 5 (by weighted score)
            print(f"🔴 Negative Funding Rate Top 5 (by Market Significance):{Style.RESET_ALL}")
            negative = [x for x in funding_list if x['funding'] < 0]
            negative.sort(key=lambda x: x['weighted_score'], reverse=True)
            
            if not negative:
                print(f"{Fore.YELLOW}  (No significant negative rates at the moment){Style.RESET_ALL}")
            else:
                for i, item in enumerate(negative[:5], 1):
                    oi_display = format_usd(item['oi_usd'])
                    score_display = format_score(item['weighted_score'])
                    print(f"{Fore.RED}  {i:2d}. {item['coin']:<8} {item['funding']:7.4f}%  | OI: {oi_display:>12}  | Score: {score_display:>10}  | Price: ${item['mark_px']:<8.4f}{Style.RESET_ALL}")
            
            print("-" * 90)
            
            # Show highest OI markets (USD value)
            print(f"{Fore.CYAN}📊 Highest Open Interest Markets (USD):{Style.RESET_ALL}")
            oi_sorted = sorted(funding_list, key=lambda x: x['oi_usd'], reverse=True)
            for i, item in enumerate(oi_sorted[:5], 1):
                funding_color = Fore.GREEN if item['funding'] > 0 else Fore.RED if item['funding'] < 0 else Fore.WHITE
                oi_display = format_usd(item['oi_usd'])
                print(f"  {i:2d}. {item['coin']:<8} | OI: {oi_display:>12}  | {funding_color}Funding: {item['funding']:7.4f}%{Style.RESET_ALL}  | Coins: {item['oi_coins']:>12,.0f}")
            
            print("-" * 90)
            print(f"{Fore.CYAN}Next update: 60 seconds   (Ctrl+C to exit){Style.RESET_ALL}")
            print(f"{Fore.WHITE}Note: OI (USD) = Coin OI × Mark Price | Score = |Funding%| × OI(USD){Style.RESET_ALL}")
            print(f"{Fore.WHITE}Score represents total dollar-weighted market sentiment{Style.RESET_ALL}")
            
        except requests.exceptions.RequestException as e:
            print(f"{Fore.RED}Network Error: {e}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}Processing Error: {e}{Style.RESET_ALL}")
        
        time.sleep(60)

def format_usd(value):
    """Format USD values with K/M/B suffixes"""
    if value >= 1e9:
        return f"${value/1e9:.2f}B"
    elif value >= 1e6:
        return f"${value/1e6:.2f}M"
    elif value >= 1e3:
        return f"${value/1e3:.2f}K"
    else:
        return f"${value:.0f}"

def format_score(value):
    """Format score values with K/M/B suffixes"""
    if value >= 1e9:
        return f"{value/1e9:.2f}B"
    elif value >= 1e6:
        return f"{value/1e6:.2f}M"
    elif value >= 1e3:
        return f"{value/1e3:.2f}K"
    else:
        return f"{value:.0f}"

if __name__ == "__main__":
    try:
        get_hyperliquid_funding()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Monitoring stopped, goodbye!{Style.RESET_ALL}")