import time
import threading
from eth_account import Account
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_EVEN

# ===================== 配置區域 =====================
MAINNET_URL = constants.MAINNET_API_URL
PRIVATE_KEY = "    "
ACCOUNT_ADDRESS = "    "
COIN = "BTC"
QUANTITY_RAW = 0.0002
PRICE_OFFSET = 50.0          # 加大偏移，避免太接近 mid 被吃掉
INTERVAL_SECONDS = 60
TIMEOUT_SECONDS = 10
# =================================================================

wallet = Account.from_key(PRIVATE_KEY)
info = Info(MAINNET_URL, skip_ws=True)
exchange = Exchange(wallet, MAINNET_URL, account_address=ACCOUNT_ADDRESS)

SZ_STEP = Decimal('0.00001')  # BTC szDecimals=5

def snap_price(px: float) -> Decimal:
    """強制 round 到整數，避免 tick size 錯誤"""
    px_dec = Decimal(str(px))
    return px_dec.quantize(Decimal('1'), rounding=ROUND_HALF_EVEN)

def snap_qty(qty: float) -> Decimal:
    q_dec = Decimal(str(qty))
    multiple = (q_dec / SZ_STEP).to_integral_value(rounding=ROUND_DOWN)
    return (multiple * SZ_STEP).quantize(SZ_STEP)

def place_maker_orders():
    all_mids = info.all_mids()
    mid_px_str = all_mids.get(COIN)
    if not mid_px_str:
        print(f"無法獲取 {COIN} mid price，跳過本次")
        return

    mid_px = float(mid_px_str)
    print(f"[{time.strftime('%H:%M:%S')}] mid price: {mid_px:.1f}")

    buy_px_raw = mid_px - PRICE_OFFSET
    sell_px_raw = mid_px + PRICE_OFFSET

    buy_px = snap_price(buy_px_raw)
    sell_px = snap_price(sell_px_raw)
    qty = snap_qty(QUANTITY_RAW)

    print(f"掛單價格 → 買: {buy_px} | 賣: {sell_px} | 數量: {qty}")

    # 先取消該幣種所有 open orders
    try:
        open_orders = info.open_orders(ACCOUNT_ADDRESS)
        print(f"目前 open orders 數量: {len(open_orders)}")
        for order in open_orders:
            if order.get('coin') == COIN:
                try:
                    res = exchange.cancel(COIN, order['oid'])
                    print(f"取消舊訂單 {order['oid']}: {res.get('status', '未知')}")
                except Exception as ce:
                    print(f"取消失敗 {order['oid']}: {ce}")
    except Exception as e:
        print(f"查詢/取消 open orders 失敗: {e}")

    buy_oid = None
    sell_oid = None

    # 多頭買單 (post only)
    try:
        buy_result = exchange.order(
            COIN,
            is_buy=True,
            sz=float(qty),
            limit_px=float(buy_px),
            order_type={"limit": {"tif": "Alo"}},
            reduce_only=False
        )
        print(f"買單回傳: {buy_result}")

        statuses = buy_result.get("response", {}).get("data", {}).get("statuses", [])
        if statuses:
            item = statuses[0] if isinstance(statuses, list) else statuses
            if "error" in item:
                print(f"買單被拒絕: {item['error']}")
            elif "resting" in item:
                buy_oid = item["resting"].get("oid")
                if buy_oid:
                    print(f"買單成功 resting | OID: {buy_oid}")
                    threading.Timer(TIMEOUT_SECONDS, check_and_cancel, args=(buy_oid, COIN, "買單")).start()
                else:
                    print("買單 resting 但無 oid")
    except Exception as e:
        print(f"買單下單異常: {e}")

    # 空頭賣單
    try:
        sell_result = exchange.order(
            COIN,
            is_buy=False,
            sz=float(qty),
            limit_px=float(sell_px),
            order_type={"limit": {"tif": "Alo"}},
            reduce_only=False
        )
        print(f"賣單回傳: {sell_result}")

        statuses = sell_result.get("response", {}).get("data", {}).get("statuses", [])
        if statuses:
            item = statuses[0] if isinstance(statuses, list) else statuses
            if "error" in item:
                print(f"賣單被拒絕: {item['error']}")
            elif "resting" in item:
                sell_oid = item["resting"].get("oid")
                if sell_oid:
                    print(f"賣單成功 resting | OID: {sell_oid}")
                    threading.Timer(TIMEOUT_SECONDS, check_and_cancel, args=(sell_oid, COIN, "賣單")).start()
                else:
                    print("賣單 resting 但無 oid")
    except Exception as e:
        print(f"賣單下單異常: {e}")

def check_and_cancel(oid, coin, side_name):
    print(f"[{time.strftime('%H:%M:%S')}] Timer 觸發 - {side_name} OID {oid} 檢查是否需撤單")
    try:
        open_orders = info.open_orders(ACCOUNT_ADDRESS)
        print(f"目前 open orders 數量: {len(open_orders)}")
        is_open = any(o.get("oid") == oid for o in open_orders)

        if is_open:
            print(f"OID {oid} 仍 open → 執行撤單")
            cancel_res = exchange.cancel(coin, oid)
            print(f"撤單結果: {cancel_res}")
        else:
            print(f"OID {oid} 已非 open（可能已成交或已撤）")
    except Exception as e:
        print(f"檢查/撤單失敗 OID {oid}: {e}")

def main():
    print("=== 主網 BTC Maker Bot 啟動（完整版） ===")
    print(f"間隔: {INTERVAL_SECONDS}s | 超時撤單: {TIMEOUT_SECONDS}s")
    print(f"價格偏移: ±{PRICE_OFFSET} | 數量: {QUANTITY_RAW}")
    print("每輪會先取消舊訂單，再掛新多空 maker 單")
    print("-" * 50)

    while True:
        try:
            place_maker_orders()
        except Exception as e:
            print(f"主循環異常: {e}")
        time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    main()