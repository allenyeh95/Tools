import threading
import curses
import datetime
import time
import eth_account
import requests
import sys
import os
import random
from colorama import Fore, init
init(autoreset=True)

from hyperliquid.utils import constants
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info

# ============ 基礎配置（金庫模式） ============
PRIVATE_KEY = " "
ACCOUNT_ADDRESS = " "
TG_TOKEN = " "
TG_CHAT_ID = " "
COIN = "PAXG"

# ============ 參數 ============
POSITION_SIZE_USDC = 200  # 每次開倉200 USDC等值
MIN_SWAP_INTERVAL = 60     # 最小換倉間隔（秒）
MAX_SWAP_INTERVAL = 180    # 最大換倉間隔（秒）
PROFIT_THRESHOLD = 0.2     # 浮盈超過0.2 USDC立即換倉
PRICE_DECIMALS = 1         # PAXG 精度
UPDATE_INTERVAL = 1        # 每秒檢查
REPORT_INTERVAL = 1800     # 半小時報告
last_report_time = 0
last_swap_time = 0
next_swap_interval = 0
current_direction = None   # 當前方向: 'long' 或 'short'

# ============ 全域狀態 ============
status_data = {
    "position": 0.0, "pnl": 0.0, "pnl_pct": 0.0,
    "price": 0.0, "account_value": 0.0, "entry_px": 0.0,
    "direction": "無", "next_swap": 0
}
status_lock = threading.Lock()
log_lines = []
log_max_lines = 50
running = True

# ============ TG 通知 ============
def send_tg_msg(msg):
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TG_CHAT_ID, "text": msg}, timeout=30)
    except Exception as e:
        print(f"TG發送失敗: {e}")

# ============ 更新狀態（金庫模式） ============
def update_status(info, coin):
    try:
        all_mids = info.all_mids()
        if coin not in all_mids or all_mids[coin] is None:
            add_log("無法從 all_mids 獲取價格")
            return False
        price = float(all_mids[coin])

        user_state = info.user_state(ACCOUNT_ADDRESS)
        margin_summary = user_state.get('marginSummary', {})
        account_value = float(margin_summary.get('accountValue', 0.0))
        unrealized_pnl = float(margin_summary.get('unrealizedPnl', 0.0))

        pos_size = entry_px = position_pnl = 0.0
        asset_positions = user_state.get('assetPositions', [])
        for pos in asset_positions:
            position = pos.get('position', {})
            if position.get('coin') == coin:
                pos_size = float(position.get('szi', '0'))
                entry_px = float(position.get('entryPx', '0'))
                position_pnl = float(position.get('unrealizedPnl', '0'))
                break

        if unrealized_pnl == 0.0 and position_pnl != 0.0:
            unrealized_pnl = position_pnl

        if pos_size != 0 and entry_px != 0:
            base_cost = abs(pos_size) * entry_px
            pnl_pct = (unrealized_pnl / base_cost) * 100 if base_cost > 0 else 0.0
        else:
            pnl_pct = 0.0

        with status_lock:
            status_data.update({
                "position": pos_size,
                "pnl": unrealized_pnl,
                "pnl_pct": pnl_pct,
                "price": price,
                "account_value": account_value,
                "entry_px": entry_px
            })
        return True

    except Exception as e:
        add_log(f"狀態更新失敗: {type(e).__name__}: {e}")
        return False

# ============ 日誌系統 ============
def add_log(msg):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    log_msg = f"[{timestamp}] {msg}"
    log_lines.append(log_msg)
    if len(log_lines) > log_max_lines:
        log_lines.pop(0)
    print(log_msg)

# ============ 繪製畫面 ============
def draw_screen(stdscr):
    global running
    curses.curs_set(0)
    curses.start_color()
    curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    curses.init_pair(5, curses.COLOR_YELLOW, curses.COLOR_BLACK)

    while running:
        h, w = stdscr.getmaxyx()
        stdscr.erase()

        time_str = datetime.datetime.now().strftime("%A-%B-%p")
        title = f" {COIN} 多空換倉策略 [{time_str}] "
        stdscr.attron(curses.color_pair(5) | curses.A_BOLD)
        stdscr.addstr(0, 0, title.center(w))
        stdscr.attroff(curses.color_pair(5) | curses.A_BOLD)

        with status_lock:
            data = status_data.copy()
            direction = current_direction
            next_swap = next_swap_interval

        pnl_color = 1 if data["pnl"] >= 0 else 2
        pos_color = 3 if data["position"] > 0 else (2 if data["position"] < 0 else 1)

        # 第一行
        line1 = f"PnL: {data['pnl']:+.2f} USD ({data['pnl_pct']:+.2f}%)".ljust(30)
        line1 += f"POS: {data['position']:.3f} {COIN}".ljust(25)
        line1 += f"PRICE: {data['price']:.{PRICE_DECIMALS}f}".ljust(20)
        line1 += f"Account Value: {data['account_value']:.2f} USDC"
        stdscr.addstr(1, 2, line1)
        stdscr.attron(curses.color_pair(pnl_color) | curses.A_BOLD)
        stdscr.addstr(1, 7, f"{data['pnl']:+.2f} USD ({data['pnl_pct']:+.2f}%)")
        stdscr.attroff(curses.color_pair(pnl_color) | curses.A_BOLD)
        stdscr.attron(curses.color_pair(pos_color))
        stdscr.addstr(1, 37, f"{data['position']:.3f} {COIN}")
        stdscr.attroff(curses.color_pair(pos_color))

        # 第二行 - 策略資訊
        direction_display = f"多頭 ({data['position']:+.3f})" if direction == 'long' else (f"空頭 ({data['position']:+.3f})" if direction == 'short' else "無持倉")
        swap_info = f"下次換倉: {next_swap} 秒後 | 觸發條件: >+{PROFIT_THRESHOLD} USD 或 時間到"
        
        stdscr.addstr(2, 2, f"當前方向: {direction_display}".ljust(30))
        stdscr.addstr(2, 32, swap_info)

        stdscr.hline(3, 0, curses.ACS_HLINE, w)
        stdscr.addstr(4, 0, f"每次開倉: {POSITION_SIZE_USDC} USDC 等值 {COIN}", curses.color_pair(5) | curses.A_BOLD)

        stdscr.addstr(5, 0, "record log:".ljust(w))
        stdscr.hline(6, 0, curses.ACS_HLINE, w)

        start_line = max(0, len(log_lines) - (h - 7))
        for i, log in enumerate(log_lines[start_line:]):
            if 7 + i < h:
                stdscr.addstr(7 + i, 0, log[:w-1])

        stdscr.refresh()
        time.sleep(0.5)

# ============ 取消訂單 ============
def cancel_all_orders(exchange, info, coin):
    try:
        orders = info.open_orders(ACCOUNT_ADDRESS)
        cancel_count = 0
        for o in orders:
            if o.get('coin') == coin:
                oid = int(o['oid'])
                exchange.cancel(coin, oid)
                add_log(f"取消訂單 {oid}")
                cancel_count += 1
                time.sleep(0.05)
        return cancel_count
    except Exception as e:
        add_log(f"取消訂單錯誤: {e}")
        return 0

# ============ 平倉 ============
def close_position(exchange, info, coin):
    try:
        cancel_all_orders(exchange, info, coin)
        time.sleep(0.5)
        response = exchange.market_close(coin)
        time.sleep(1)
        update_status(info, coin)
        with status_lock:
            new_pos = status_data["position"]
        if abs(new_pos) < 0.001:
            add_log("✅ 平倉成功")
            return True
        else:
            add_log(f"⚠️ 平倉後仍有持倉: {new_pos}")
            return False
    except Exception as e:
        add_log(f"平倉失敗: {e}")
        return False

# ============ 開倉 ============
def open_position(exchange, info, coin, is_long):
    """開倉，is_long=True 表示做多，False 表示做空"""
    try:
        # 獲取當前價格
        all_mids = info.all_mids()
        if coin not in all_mids:
            add_log("無法獲取價格")
            return False
        
        price = float(all_mids[coin])
        
        # 計算開倉數量 (200 USDC 等值)
        quantity = POSITION_SIZE_USDC / price
        # 根據PAXG精度調整
        quantity = round(quantity, 3)  # PAXG 通常小數3位
        
        if quantity <= 0:
            add_log(f"開倉數量無效: {quantity}")
            return False
        
        direction = "買入" if is_long else "賣出"
        add_log(f"嘗試開倉: {direction} {quantity} {coin} @ ~{price:.{PRICE_DECIMALS}f}")
        
        # 下市價單
        if is_long:
            response = exchange.market_open(coin, True, quantity, None, 0.01)
        else:
            response = exchange.market_open(coin, False, quantity, None, 0.01)
        
        time.sleep(1)
        update_status(info, coin)
        
        with status_lock:
            new_pos = status_data["position"]
            entry = status_data["entry_px"]
        
        if abs(new_pos) > 0:
            add_log(f"✅ 開倉成功: {direction} {new_pos:+.3f} @ {entry:.{PRICE_DECIMALS}f}")
            return True
        else:
            add_log(f"⚠️ 開倉後無持倉")
            return False
            
    except Exception as e:
        add_log(f"開倉失敗: {e}")
        return False

# ============ 隨機選擇初始方向 ============
def choose_initial_direction():
    return random.choice(['long', 'short'])

# ============ 生成隨機間隔 ============
def generate_random_interval():
    return random.randint(MIN_SWAP_INTERVAL, MAX_SWAP_INTERVAL)

# ============ 反向換倉 ============
def swap_position(exchange, info, coin, reason):
    global current_direction, last_swap_time, next_swap_interval
    
    with status_lock:
        old_pos = status_data["position"]
        old_pnl = status_data["pnl"]
        old_direction = current_direction
    
    add_log(f"🔄 觸發換倉: {reason}")
    
    # 平倉
    if not close_position(exchange, info, coin):
        add_log("❌ 平倉失敗，取消換倉")
        return False
    
    # 隨機選擇新方向
    new_direction = 'long' if old_direction == 'short' else 'short'  # 反向
    add_log(f"🔄 新方向: {'多頭' if new_direction == 'long' else '空頭'}")
    
    # 開新倉
    if open_position(exchange, info, coin, new_direction == 'long'):
        # 更新狀態
        current_direction = new_direction
        last_swap_time = time.time()
        next_swap_interval = generate_random_interval()
        
        with status_lock:
            new_pos = status_data["position"]
            new_pnl = status_data["pnl"]
        
        # 發送TG通知
        send_tg_msg(
            f"🔄 {coin} 換倉完成\n"
            f"原因: {reason}\n"
            f"舊方向: {'多頭' if old_direction == 'long' else '空頭'} ({old_pos:+.3f})\n"
            f"新方向: {'多頭' if new_direction == 'long' else '空頭'} ({new_pos:+.3f})\n"
            f"換倉盈虧: {old_pnl:+.2f} USD\n"
            f"當前盈虧: {new_pnl:+.2f} USD"
        )
        
        return True
    else:
        add_log("❌ 開倉失敗，進入無持倉狀態")
        current_direction = None
        last_swap_time = time.time()
        next_swap_interval = generate_random_interval()
        return False

# ============ 主交易邏輯 ============
def run_trading_bot(exchange, info, coin):
    global current_direction, last_swap_time, next_swap_interval, last_report_time
    
    if not update_status(info, coin):
        return
    
    with status_lock:
        mid_price = status_data["price"]
        current_pos = status_data["position"]
        pnl = status_data["pnl"]
        account_value = status_data["account_value"]
    
    if mid_price == 0:
        return
    
    now = time.time()
    
    # ===== 初始化 =====
    if current_direction is None:
        # 隨機選擇初始方向
        current_direction = choose_initial_direction()
        last_swap_time = now
        next_swap_interval = generate_random_interval()
        add_log(f"🎲 隨機選擇初始方向: {'多頭' if current_direction == 'long' else '空頭'}")
        
        # 開倉
        open_position(exchange, info, coin, current_direction == 'long')
        return
    
    # ===== 檢查是否需要換倉 =====
    swap_reason = None
    
    # 1. 檢查浮盈條件
    if pnl >= PROFIT_THRESHOLD:
        swap_reason = f"浮盈達標 (+{pnl:.2f} >= +{PROFIT_THRESHOLD} USD)"
    
    # 2. 檢查時間條件 (如果沒有浮盈觸發)
    if swap_reason is None and (now - last_swap_time) >= next_swap_interval:
        swap_reason = f"時間到 (已過 {int(now - last_swap_time)} 秒)"
    
    # 執行換倉
    if swap_reason:
        swap_position(exchange, info, coin, swap_reason)
        return
    
    # ===== 更新下次換倉倒數 =====
    with status_lock:
        status_data["next_swap"] = max(0, int(next_swap_interval - (now - last_swap_time)))
    
    # ===== 定期報告 =====
    if now - last_report_time >= REPORT_INTERVAL:
        next_swap_in = max(0, int(next_swap_interval - (now - last_swap_time)))
        
        send_tg_msg(
            f"📊 {coin} 策略報告\n"
            f"方向: {'多頭' if current_direction == 'long' else '空頭'}\n"
            f"持倉: {current_pos:+.3f} {coin}\n"
            f"價格: {mid_price:.{PRICE_DECIMALS}f}\n"
            f"浮盈: {pnl:+.2f} USD ({status_data['pnl_pct']:+.2f}%)\n"
            f"下次換倉: {next_swap_in} 秒後\n"
            f"帳戶價值: {account_value:.2f} USDC"
        )
        last_report_time = now

# ============ 主程式 ============
def main_logic():
    global running, last_report_time, last_swap_time, next_swap_interval, current_direction
    
    add_log(f"🚀 {COIN} 多空換倉策略啟動")
    add_log(f"📊 每次開倉: {POSITION_SIZE_USDC} USDC 等值")
    add_log(f"⚡ 換倉條件: 浮盈 >+{PROFIT_THRESHOLD} USD 或 {MIN_SWAP_INTERVAL}-{MAX_SWAP_INTERVAL} 秒")
    
    last_report_time = 0
    last_swap_time = 0
    next_swap_interval = generate_random_interval()
    current_direction = None

    account = eth_account.Account.from_key(PRIVATE_KEY.strip())
    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    exchange = Exchange(
        account, 
        constants.MAINNET_API_URL,
        account_address=ACCOUNT_ADDRESS
    )

    while running:
        try:
            run_trading_bot(exchange, info, COIN)
            time.sleep(UPDATE_INTERVAL)
        except KeyboardInterrupt:
            running = False
            add_log("👋 手動結束")
        except Exception as e:
            add_log(f"❌ 主程式錯誤: {e}")
            time.sleep(60)

if __name__ == "__main__":
    if 'PYTHONANYWHERE' in os.environ or not sys.stdout.isatty():
        main_logic()
    else:
        def curses_main(stdscr):
            draw_thread = threading.Thread(target=draw_screen, args=(stdscr,), daemon=True)
            draw_thread.start()
            main_logic()
        curses.wrapper(curses_main)