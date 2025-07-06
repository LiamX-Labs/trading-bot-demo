# order_manager.py - AWS EC2 Free Tier Optimized Version

import os
import json
import hmac
import hashlib
import requests
import math
import time
from datetime import datetime, timezone, timedelta
from telegram_alerts import send_telegram_message
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from functools import lru_cache
from trade_tracker import trade_tracker, enhance_active_trades_structure, get_trade_age_hours

import settings

# Constants & credentials from settings
USE_DEMO                = settings.USE_DEMO
BASE_URL                = settings.BASE_URL

API_KEY                 = settings.API_KEY
API_SECRET              = settings.API_SECRET
RECV_WINDOW             = settings.RECV_WINDOW

# Strategy sizing parameters from settings
BASE_POSITION_SIZE_USD   = settings.BASE_POSITION_SIZE_USD
STOPLOSS_PERCENT         = settings.STOPLOSS_PERCENT
TRAIL_ACTIVATION_PERCENT = settings.TRAIL_ACTIVATION_PERCENT
TRAIL_OFFSET_PERCENT     = settings.TRAIL_OFFSET_PERCENT

# ─── Helpers ─────────────────────────────────────────────────────────────────

# Global cache for server time offset
_time_offset_cache = None
_last_sync_time = 0
SYNC_INTERVAL = 300  # Re-sync every 5 minutes

def fetch_server_timestamp():
    """Get server timestamp with better error handling and sync"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Get Bybit server time
            resp = requests.get(f"{BASE_URL}/v5/public/time", timeout=5)
            server_time = str(resp.json()["time"])
            
            # Calculate time difference
            local_time = str(int(datetime.now(timezone.utc).timestamp() * 1000))
            time_diff = abs(int(server_time) - int(local_time))
            
            # If difference is too large, use server time directly
            if time_diff > 5000:  # More than 5 seconds difference
                # REMOVED: Debug print
                return server_time
            
            return local_time
            
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(0.5)
                continue
            # Fallback to local time
            return str(int(datetime.now(timezone.utc).timestamp() * 1000))

def generate_signature(timestamp: str, recv_window: str, params: dict = None, body: str = "") -> str:
    """
    Bybit V5 HMAC_SHA256 signature for demo (and live):
      signature = HMAC_SHA256(secret, timestamp + apiKey + recvWindow + queryString + body)
    """
    params = params or {}
    # Build query string in insertion order (preserves dict literal order)
    qs = "&".join(f"{k}={params[k]}" for k in params)

    # Concatenate components
    to_sign = f"{timestamp}{API_KEY}{recv_window}{qs}{body}"

    # Compute HMAC-SHA256 and return hex digest
    return hmac.new(
        API_SECRET.encode(),
        to_sign.encode(),
        hashlib.sha256
    ).hexdigest()

# Create a session with connection pooling
def create_optimized_session():
    session = requests.Session()
    
    # Configure retries
    retry_strategy = Retry(
        total=2,
        backoff_factor=0.1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    
    # OPTIMIZED: Reduced pool size for t2.micro
    adapter = HTTPAdapter(
        pool_connections=5,  # Reduced from 10
        pool_maxsize=10,     # Reduced from 20
        max_retries=retry_strategy
    )
    
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

# Global session for reuse
_global_session = None

def get_session():
    global _global_session
    if _global_session is None:
        _global_session = create_optimized_session()
    return _global_session

# OPTIMIZED: Increased cache TTL and added size limit
_market_info_cache = {}
_cache_ttl = 7200  # Increased to 2 hours
_max_cache_size = 50  # Limit cache size

def fetch_market_info(symbol):
    """Fetch market info with caching to reduce API calls"""
    current_time = time.time()
    
    # Check cache first
    if symbol in _market_info_cache:
        info, timestamp = _market_info_cache[symbol]
        if current_time - timestamp < _cache_ttl:
            return info
    
    # Clean cache if too large
    if len(_market_info_cache) > _max_cache_size:
        # Remove oldest entries
        sorted_cache = sorted(_market_info_cache.items(), key=lambda x: x[1][1])
        for k, _ in sorted_cache[:10]:  # Remove 10 oldest
            del _market_info_cache[k]
    
    # Fetch fresh data
    ts = fetch_server_timestamp()
    params = {"category": "linear", "symbol": symbol}
    sig = generate_signature(ts, RECV_WINDOW, params)
    headers = {
        'X-BAPI-API-KEY': API_KEY,
        'X-BAPI-SIGN': sig,
        'X-BAPI-TIMESTAMP': ts,
        'X-BAPI-RECV-WINDOW': RECV_WINDOW,
        'Content-Type': 'application/json'
    }
    
    try:
        session = get_session()
        resp = session.get(
            f"{BASE_URL}/v5/market/instruments-info",
            headers=headers,
            params=params,
            timeout=3
        )
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("retCode") == 0:
                info = data.get("result", {}).get("list", [{}])[0]
                # Cache the result
                _market_info_cache[symbol] = (info, current_time)
                return info
    except Exception as e:
        # REMOVED: Debug print
        pass
    
    return {}

def has_open_positions(symbols=None):
    """Check for any open positions (faster than individual checks)"""
    try:
        ts = fetch_server_timestamp()
        params = {"category": "linear", "settleCoin": "USDT"}
        sig = generate_signature(ts, RECV_WINDOW, params)
        headers = {
            'X-BAPI-API-KEY': API_KEY,
            'X-BAPI-SIGN': sig,
            'X-BAPI-TIMESTAMP': ts,
            'X-BAPI-RECV-WINDOW': RECV_WINDOW,
            'Content-Type': 'application/json'
        }
        
        session = get_session()
        resp = session.get(
            f"{BASE_URL}/v5/position/list",
            headers=headers,
            params=params,
            timeout=3
        )
        
        if resp.status_code == 200:
            data = resp.json()
            positions = data.get("result", {}).get("list", [])
            
            if symbols:
                # Check specific symbols
                for pos in positions:
                    if pos.get("symbol") in symbols and float(pos.get("size", 0)) != 0:
                        return True
            else:
                # Check any positions
                for pos in positions:
                    if float(pos.get("size", 0)) != 0:
                        return True
                        
        return False
    except Exception as e:
        # REMOVED: Debug print
        return False

def close_trade(symbol, rule_id=None, reason="manual"):
    """
    Enhanced close_trade with logging support.
    rule_id can be passed to log the specific trade closure.
    """
    ts = fetch_server_timestamp()
    params = {"category":"linear","symbol":symbol}
    sig = generate_signature(ts, RECV_WINDOW, params)
    headers = {
        'X-BAPI-API-KEY': API_KEY,
        'X-BAPI-SIGN': sig,
        'X-BAPI-TIMESTAMP': ts,
        'X-BAPI-RECV-WINDOW': RECV_WINDOW,
        'Content-Type': 'application/json'
    }
    resp = requests.get(
        f"{BASE_URL}/v5/position/list",
        headers=headers,
        params=params
    )
    try:
        data = resp.json()
    except ValueError:
        return False
        
    trade_closed = False
    for pos in data.get("result", {}).get("list", []):
        size = float(pos.get("size", 0))
        side = pos.get("side")
        if size != 0 and side in ("Buy","Sell"):
            close_side = "Sell" if side == "Buy" else "Buy"
            order = {
                "category": "linear",
                "symbol": symbol,
                "side": close_side,
                "orderType": "Market",
                "qty": str(size),
                "orderLinkId": os.urandom(8).hex()
            }
            ts2 = fetch_server_timestamp()
            payload = json.dumps(order, separators=(',', ':'), sort_keys=True)
            sig2 = generate_signature(ts2, RECV_WINDOW, {}, payload)
            headers2 = headers.copy()
            headers2.update({
                'X-BAPI-SIGN': sig2,
                'X-BAPI-TIMESTAMP': ts2
            })
            res = requests.post(f"{BASE_URL}/v5/order/create", headers=headers2, data=payload)
            try:
                result = res.json()
                if result.get("retCode") == 0:
                    print(f"🔒 Closed {symbol}")
                    trade_closed = True
                    
                    # LOG TRADE CLOSURE
                    if rule_id:
                        trade_tracker.log_trade_closed(symbol, rule_id, reason)
                    
            except ValueError:
                pass
            break
    
    return trade_closed

def close_all_positions(active_trades, reason="risk_management"):
    """
    Enhanced close_all_positions with logging support.
    """
    ts = fetch_server_timestamp()
    params = {"category": "linear", "settleCoin": "USDT"}
    sig = generate_signature(ts, RECV_WINDOW, params)
    headers = {
        'X-BAPI-API-KEY':     API_KEY,
        'X-BAPI-SIGN':        sig,
        'X-BAPI-TIMESTAMP':   ts,
        'X-BAPI-RECV-WINDOW': RECV_WINDOW,
        'Content-Type':       'application/json'
    }
    resp = requests.get(
        f"{BASE_URL}/v5/position/list",
        headers=headers,
        params=params
    )
    data = resp.json().get("result", {}).get("list", [])

    # Close each non-zero position and log closure
    for pos in data:
        symbol = pos.get("symbol")
        size = abs(float(pos.get("size", 0)))
        if size > 0:
            # Find corresponding rule_id from active_trades
            rule_id = None
            for (trade_symbol, trade_rule), trade_data in active_trades.items():
                if trade_symbol == symbol:
                    if isinstance(trade_data, dict):
                        rule_id = trade_data.get('rule_id', trade_rule)
                    else:
                        rule_id = trade_rule
                    break
            
            # Close the trade with logging
            close_trade(symbol, rule_id, reason)

    # Clear active_trades dict entirely
    active_trades.clear()
    print("✅ All positions closed.")

def open_trade(symbol, side, price, row, rule_id):
    info = fetch_market_info(symbol)
    if not info:
        return False

    min_qty  = float(info['lotSizeFilter']['minOrderQty'])
    qty_step = float(info['lotSizeFilter']['qtyStep'])
    tick     = float(info['priceFilter']['tickSize'])
    min_not  = float(info.get('notionalFilter',{}).get('minNotional',0))

    raw_qty = BASE_POSITION_SIZE_USD / price
    qty     = math.floor(raw_qty / qty_step) * qty_step
    if qty < min_qty:
        qty = min_qty
    if min_not and price*qty < min_not:
        qty = math.ceil(min_not / price / qty_step) * qty_step
    qty = round(qty, len(str(qty_step).split('.')[-1]))

    sl_price     = round(price * (1 - STOPLOSS_PERCENT/100), len(str(tick).split('.')[-1]))
    act_price    = round(price * (1 + TRAIL_ACTIVATION_PERCENT/100), len(str(tick).split('.')[-1]))
    trail_offset = round(price * (TRAIL_OFFSET_PERCENT/100), len(str(tick).split('.')[-1]))

    # CAPTURE ENTRY TIMESTAMP BEFORE API CALL
    entry_timestamp = datetime.now(timezone.utc)

    entry = {
        "category":"linear","symbol":symbol,
        "side":side.capitalize(),
        "orderType":"Market","qty":str(qty),
        "orderLinkId":os.urandom(16).hex()
    }
    ts = fetch_server_timestamp()
    payload = json.dumps(entry, separators=(',',':'), sort_keys=True)
    sign = generate_signature(ts, RECV_WINDOW, {}, payload)
    headers = {
        'X-BAPI-API-KEY':     API_KEY,
        'X-BAPI-SIGN':        sign,
        'X-BAPI-TIMESTAMP':   ts,
        'X-BAPI-RECV-WINDOW': RECV_WINDOW,
        'Content-Type':       'application/json'
    }
    res = requests.post(f"{BASE_URL}/v5/order/create", headers=headers, data=payload).json()
    if res.get("retCode") != 0:
        print(f"❌ Entry failed for {symbol}: {res}")
        return False

    # TRADE OPENED SUCCESSFULLY - LOG IT
    trade_tracker.log_trade_opened(
        symbol=symbol,
        rule_id=rule_id,
        entry_price=price,
        position_size=qty,
        entry_timestamp=entry_timestamp
    )

    # Set stop-loss and trailing stop
    ts2 = fetch_server_timestamp()
    ts_payload = {
        "category":"linear","symbol":symbol,"positionIdx":0,
        "stopLoss":str(sl_price),"slTriggerBy":"LastPrice",
        "trailingStop":str(trail_offset),"activePrice":str(act_price),
        "tpslMode":"Full"
    }
    data_ts = json.dumps(ts_payload, separators=(',',':'), sort_keys=True)
    sign_ts = generate_signature(ts2, RECV_WINDOW, {}, data_ts)
    headers_ts = {
        'X-BAPI-API-KEY':     API_KEY,
        'X-BAPI-SIGN':        sign_ts,
        'X-BAPI-TIMESTAMP':   ts2,
        'X-BAPI-RECV-WINDOW': RECV_WINDOW,
        'Content-Type':       'application/json'
    }
    requests.post(f"{BASE_URL}/v5/position/trading-stop", headers=headers_ts, data=data_ts)

    print(f"✅ Opened {symbol} @ {price} Qty={qty}")

    # OPTIMIZED: Shorter Telegram message
    msg = (
        f"🚨 Trade Alert: {symbol}\n"
        f"Entry: {price} | SL: {sl_price}\n"
        f"Rule: {rule_id}"
    )
    send_telegram_message(msg)
    
    # RETURN ENHANCED TRADE DATA for active_trades
    return {
        'entry_timestamp': entry_timestamp,
        'entry_price': price,
        'position_size': qty,
        'rule_id': rule_id,
        'expiry_time': entry_timestamp + timedelta(hours=72)
    }

def move_sl_to_breakeven(symbol: str) -> dict:
    """
    OPTIMIZED: Minimal logging version
    """
    # Get current position
    ts = fetch_server_timestamp()
    params = {"category": "linear", "symbol": symbol}
    sig = generate_signature(ts, RECV_WINDOW, params)
    headers = {
        'X-BAPI-API-KEY':     API_KEY,
        'X-BAPI-SIGN':        sig,
        'X-BAPI-TIMESTAMP':   ts,
        'X-BAPI-RECV-WINDOW': RECV_WINDOW,
        'Content-Type':       'application/json'
    }
    
    resp = requests.get(f"{BASE_URL}/v5/position/list", headers=headers, params=params)
    resp_data = resp.json()
    
    positions = resp_data.get("result", {}).get("list", [])
    if not positions:
        return {"retCode": -1, "retMsg": "No position found"}

    pos = positions[0]
    
    # Get entry price - use avgPrice
    avg_price = float(pos.get("avgPrice", 0))
    if avg_price <= 0:
        avg_price = float(pos.get("entryPrice", 0))
    
    current_sl = float(pos.get("stopLoss", 0))
    
    if avg_price <= 0:
        return {"retCode": -1, "retMsg": "Invalid entry price"}
    
    if abs(current_sl - avg_price) < 0.00001:
        return {"retCode": 0, "retMsg": "Already at breakeven"}

    # Build SL-only update payload
    update = {
        "category":    "linear",
        "symbol":      symbol,
        "positionIdx": 0,
        "stopLoss":    str(avg_price),
        "slTriggerBy": "LastPrice"
    }
    body = json.dumps(update, separators=(",", ":"), sort_keys=True)

    # Sign & send
    ts2 = fetch_server_timestamp()
    sig2 = generate_signature(ts2, RECV_WINDOW, {}, body)
    headers.update({
        'X-BAPI-SIGN':      sig2,
        'X-BAPI-TIMESTAMP': ts2
    })
    
    result = requests.post(f"{BASE_URL}/v5/position/trading-stop", headers=headers, data=body)
    result_data = result.json()
    
    if result_data.get("retCode") == 0:
        send_telegram_message(f"🔄 SL→BE: {symbol} @ {avg_price:.6f}")
    
    return result_data

def reconcile_positions_with_tracking(active_trades):
    """
    Compare tracked trades with actual exchange positions.
    Remove trades from tracking if position no longer exists.
    Returns list of externally closed trades.
    """
    try:
        ts = fetch_server_timestamp()
        params = {"category": "linear", "settleCoin": "USDT"}
        sig = generate_signature(ts, RECV_WINDOW, params)
        headers = {
            'X-BAPI-API-KEY': API_KEY,
            'X-BAPI-SIGN': sig,
            'X-BAPI-TIMESTAMP': ts,
            'X-BAPI-RECV-WINDOW': RECV_WINDOW,
            'Content-Type': 'application/json'
        }
        
        resp = requests.get(
            f"{BASE_URL}/v5/position/list",
            headers=headers,
            params=params
        )
        
        if resp.status_code != 200:
            return []
            
        data = resp.json()
        if data.get("retCode") != 0:
            return []
        
        # Get symbols with actual open positions
        open_positions = set()
        positions = data.get("result", {}).get("list", [])
        for pos in positions:
            size = abs(float(pos.get("size", 0)))
            if size > 0:
                open_positions.add(pos.get("symbol"))
        
        # Check tracked trades against actual positions
        externally_closed = []
        trades_to_remove = []
        
        for trade_key, trade_data in active_trades.items():
            symbol, rule_id = trade_key
            
            # If we're tracking this trade but position doesn't exist
            if symbol not in open_positions:
                externally_closed.append((symbol, rule_id))
                trades_to_remove.append(trade_key)
                
                # Log the external closure
                trade_tracker.log_trade_closed(symbol, rule_id, "external_close")
        
        # Remove externally closed trades from tracking
        for trade_key in trades_to_remove:
            del active_trades[trade_key]
            
        if externally_closed:
            print(f"🔄 Detected {len(externally_closed)} externally closed positions")
            
        return externally_closed
        
    except Exception as e:
        print(f"⚠️ Error reconciling positions: {e}")
        return []