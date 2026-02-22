import requests
import time
import os
from datetime import datetime
from colorama import init, Fore, Style

# Initialize Colorama (autoreset on Windows)
init(autoreset=True)

def get_hyperliquid_funding():
    """Simplified Hyperliquid Funding Rate Monitor - Settled Hourly"""
    
    url = "https://api.hyperliquid.xyz/info"
    payload = {"type": "metaAndAssetCtxs"}
    
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()  # Automatically check HTTP errors
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
                    funding = float(ctx['funding']) * 100
                except (KeyError, ValueError):
                    funding = 0.0
                funding_list.append({
                    'coin': coin,
                    'funding': funding
                })
            
            # Sort: highest → lowest
            funding_list.sort(key=lambda x: x['funding'], reverse=True)
            
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"\n{Fore.CYAN}=== Hyperliquid Funding Monitor ==={Style.RESET_ALL}")
            print(f"{Fore.WHITE}Update Time: {now}   (Hourly Settlement){Style.RESET_ALL}")
            print("-" * 50)
            
            # Positive Funding Top 5
            print(f"🟢 Positive Funding Rate Top 5 (Long pays Short):{Style.RESET_ALL}")
            for i, item in enumerate(funding_list[:5], 1):
                sign = '+' if item['funding'] >= 0 else ''
                print(f"{Fore.GREEN}  {i:2d}. {item['coin']:<8} {sign}{item['funding']:8.4f}%{Style.RESET_ALL}")
            
            print()
            
            # Negative Funding Top 5 (most negative first)
            print(f"🔴 Negative Funding Rate Top 5 (Short pays Long):{Style.RESET_ALL}")
            negative_five = [x for x in funding_list if x['funding'] < 0][-5:][::-1]
            if not negative_five:
                print(f"{Fore.YELLOW}  (No significant negative rates at the moment){Style.RESET_ALL}")
            else:
                for i, item in enumerate(negative_five, 1):
                    print(f"{Fore.RED}  {i:2d}. {item['coin']:<8} {item['funding']:8.4f}%{Style.RESET_ALL}")
            
            print("-" * 50)
            print(f"{Fore.CYAN}Next update: 60 seconds   (Ctrl+C to exit){Style.RESET_ALL}")
            print(f"{Fore.WHITE}Note: Hyperliquid funding rates are paid hourly, max ±4%/hr{Style.RESET_ALL}")
            
        except requests.exceptions.RequestException as e:
            print(f"{Fore.RED}Network Error: {e}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}Processing Error: {e}{Style.RESET_ALL}")
        
        time.sleep(60)

if __name__ == "__main__":
    try:
        get_hyperliquid_funding()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Monitoring stopped, goodbye!{Style.RESET_ALL}")