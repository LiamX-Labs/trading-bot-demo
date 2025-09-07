# main.py - AWS EC2 Free Tier Optimized Version

import aiohttp
import asyncio
import pandas as pd
import websockets
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK
import json
import math
import time
from datetime import datetime, timedelta, timezone
from collections import deque
from ta.momentum import RSIIndicator
import nest_asyncio
import requests
from concurrent.futures import ThreadPoolExecutor
import settings
import order_manager
from order_manager import has_open_positions, reconcile_positions_with_tracking
from risk_manager import RiskManager
from telegram_alerts import send_telegram_message
from trade_tracker import (
    trade_tracker, 
    enhance_active_trades_structure, 
    get_trade_age_hours,
    get_trade_expiry
)
import gc  # Added for garbage collection

nest_asyncio.apply()

USE_DEMO        = settings.USE_DEMO
BASE_URL        = settings.BASE_URL
WS_URL          = "wss://stream.bybit.com/v5/public/linear"
PUMP_LOOKBACK   = settings.PUMP_LOOKBACK
PUMP_THRESHOLD  = settings.PUMP_THRESHOLD

history = {}
active_trades = {}
processed_bars = set()
processed_signals = set()

# Global variables for symbol management
current_symbols = set()
symbol_last_refresh = 0
SYMBOL_REFRESH_INTERVAL = 4 * 3600  # 4 hours in seconds

# Global variables for WebSocket management
ws_connection = None
ws_symbols_subscribed = set()

# Global variables for trade restrictions
MAX_ACTIVE_TRADES = 30
symbol_last_trade_time = {}  # Track last trade time per symbol

def get_current_4h_interval():
    """Get current 4-hour interval starting from 3am UTC"""
    now_utc = datetime.now(timezone.utc)
    
    # Calculate hours since 3am today
    today_3am = now_utc.replace(hour=3, minute=0, second=0, microsecond=0)
    
    # If current time is before 3am today, use yesterday's 3am
    if now_utc < today_3am:
        today_3am -= timedelta(days=1)
    
    # Calculate which 4-hour interval we're in
    hours_since_3am = (now_utc - today_3am).total_seconds() / 3600
    interval_number = int(hours_since_3am // 4)
    
    return today_3am + timedelta(hours=interval_number * 4)

def can_trade_symbol(symbol):
    """Check if symbol can be traded based on 4-hour interval cooldown"""
    if symbol not in symbol_last_trade_time:
        return True
    
    current_interval = get_current_4h_interval()
    last_trade_interval = symbol_last_trade_time[symbol]
    
    return current_interval > last_trade_interval

def record_trade_for_symbol(symbol):
    """Record that a trade was executed for this symbol in current interval"""
    symbol_last_trade_time[symbol] = get_current_4h_interval()

# Instantiate RiskManager and global timestamp tracker
risk_mgr = RiskManager(lambda: active_trades)
last_update_ts = time.time()

def fetch_symbols():
    """Fetch USDT symbols with 10M volume minimum filter"""
    resp = requests.get(f"{BASE_URL}/v5/market/tickers?category=linear").json()
    syms = []
    for it in resp.get("result", {}).get("list", []):
        # Apply 10M volume minimum filter
        if float(it.get("turnover24h",0)) > 10_000_000 and it["symbol"].endswith("USDT"):
            syms.append(it["symbol"])
    
    # Sort by volume (highest first) but don't limit count
    syms = sorted(syms, key=lambda x: float(next(
        it.get("turnover24h", 0) for it in resp.get("result", {}).get("list", []) 
        if it["symbol"] == x
    )), reverse=True)
    
    return syms

async def fetch_historical_klines_async(session, symbol, interval="5", limit=200):
    """Async version with proper error handling and timeouts"""
    try:
        url = f"{BASE_URL}/v5/market/kline"
        params = {
            "category": "linear", 
            "symbol": symbol, 
            "interval": interval, 
            "limit": limit
        }
        
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=3)) as resp:
            if resp.status != 200:
                # REMOVED: Debug print
                return []
                
            data = await resp.json()
            if data.get("retCode") != 0:
                # REMOVED: Debug print
                return []
            
            bars = []
            for x in data.get("result", {}).get("list", []):
                bars.append({
                    "timestamp": x[0],
                    "open": float(x[1]),
                    "high": float(x[2]),
                    "low": float(x[3]),
                    "close": float(x[4]),
                    "volume": float(x[5]),
                })
            bars.sort(key=lambda b: b["timestamp"])
            return bars
            
    except asyncio.TimeoutError:
        return []
    except Exception as e:
        return []

async def load_all_historical_data(symbols):
    """OPTIMIZED: Reduced concurrent connections for low memory"""
    print(f"📊 Loading historical data for {len(symbols)} symbols...")
    start_time = time.time()
    
    # OPTIMIZED: Increased limits for 3-core 8GB server
    connector = aiohttp.TCPConnector(limit=20, limit_per_host=10)
    timeout = aiohttp.ClientTimeout(total=5)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        # OPTIMIZED: Increased concurrent requests for better server
        semaphore = asyncio.Semaphore(8)
        
        async def fetch_with_semaphore(symbol):
            async with semaphore:
                data = await fetch_historical_klines_async(session, symbol, "5", 200)
                return symbol, data
        
        tasks = [fetch_with_semaphore(symbol) for symbol in symbols]
        
        completed = 0
        results = {}
        
        for coro in asyncio.as_completed(tasks):
            symbol, data = await coro
            results[symbol] = data
            completed += 1
            
            if completed % 20 == 0 or completed == len(symbols):
                elapsed = time.time() - start_time
                print(f"📈 Progress: {completed}/{len(symbols)} symbols loaded ({elapsed:.1f}s)")
    
    total_time = time.time() - start_time
    print(f"✅ Historical data loaded in {total_time:.1f}s")
    return results

async def update_websocket_subscription():
    """Update WebSocket subscription when symbols change"""
    global ws_connection, ws_symbols_subscribed, current_symbols
    
    if ws_connection is None:
        return
    
    try:
        # Calculate symbols to add and remove
        symbols_to_add = current_symbols - ws_symbols_subscribed
        symbols_to_remove = ws_symbols_subscribed - current_symbols
        
        if symbols_to_add:
            add_msg = json.dumps({"op": "subscribe", "args": [f"kline.5.{s}" for s in symbols_to_add]})
            await ws_connection.send(add_msg)
            ws_symbols_subscribed.update(symbols_to_add)
            print(f"🔵 Added {len(symbols_to_add)} symbols to WebSocket subscription")
        
        if symbols_to_remove:
            remove_msg = json.dumps({"op": "unsubscribe", "args": [f"kline.5.{s}" for s in symbols_to_remove]})
            await ws_connection.send(remove_msg)
            ws_symbols_subscribed.difference_update(symbols_to_remove)
            print(f"🔵 Removed {len(symbols_to_remove)} symbols from WebSocket subscription")
            
    except Exception as e:
        print(f"❌ Error updating WebSocket subscription: {e}")

async def refresh_symbols_and_data():
    """Refresh symbols every 4 hours and load data for new symbols"""
    global current_symbols, symbol_last_refresh
    
    while True:
        try:
            await asyncio.sleep(SYMBOL_REFRESH_INTERVAL)
            
            print(f"🔄 [{datetime.now().strftime('%H:%M:%S')}] Refreshing symbols (4-hour cycle)...")
            
            # Fetch new symbols
            new_symbols_list = fetch_symbols()
            new_symbols_set = set(new_symbols_list)
            
            print(f"📊 Fetched {len(new_symbols_list)} symbols")
            
            # Find new symbols that weren't being monitored
            new_symbols = new_symbols_set - current_symbols
            removed_symbols = current_symbols - new_symbols_set
            
            if new_symbols:
                print(f"🆕 New symbols to monitor: {list(new_symbols)}")
                
                # Load historical data for new symbols
                new_symbols_data = await load_all_historical_data(list(new_symbols))
                
                # Add new symbols to history and current_symbols
                for symbol, data in new_symbols_data.items():
                    if symbol not in history:
                        history[symbol] = deque(maxlen=200)  # Updated for 144-period indicators
                    if data:
                        history[symbol].extend(data)
                    current_symbols.add(symbol)
                
                print(f"✅ Loaded data for {len([s for s, d in new_symbols_data.items() if d])} new symbols")
                
                # Update WebSocket subscription
                await update_websocket_subscription()
                
                # Send notification about new symbols
                if len(new_symbols) > 0:
                    send_telegram_message(f"🔄 Symbol refresh: Added {len(new_symbols)} new symbols to monitoring")
            
            if removed_symbols:
                print(f"🗑️ Removed symbols from monitoring: {list(removed_symbols)}")
                
                # Clean up removed symbols from history
                for symbol in removed_symbols:
                    if symbol in history:
                        del history[symbol]
                
                # Update WebSocket subscription
                await update_websocket_subscription()
                
                # Send notification about removed symbols
                send_telegram_message(f"🔄 Symbol refresh: Removed {len(removed_symbols)} symbols from monitoring")
            
            # Update current symbols set
            current_symbols = new_symbols_set
            symbol_last_refresh = time.time()
            
            print(f"✅ [{datetime.now().strftime('%H:%M:%S')}] Symbol refresh completed. Monitoring {len(current_symbols)} symbols")
            
        except Exception as e:
            print(f"❌ Error during symbol refresh: {e}")
            await asyncio.sleep(300)  # Wait 5 minutes before retrying

def apply_indicators(df):
    """Indicator calculation converted from 30min bars to 5min bars equivalent"""
    # RSI: Convert 14 periods of 30min to 5min equivalent
    # 14 * 6 = 84 periods (maintains same time window: 7 hours)
    df["rsi"] = RSIIndicator(df["close"], window=84).rsi()
    
    returns = df["close"].pct_change() * 100
    # Convert 24-period rolling window from 30min to 5min bars
    # 24 * 6 = 144 periods (maintains same time window: 12 hours)
    df["volatility"] = returns.rolling(144).std()
    df["spread"] = (df["high"] - df["low"]) / df["close"] * 100
    
    # Convert 24-period lookback from 30min to 5min bars
    # 24 * 6 = 144 periods (maintains same time window: 12 hours)
    price_change = df["close"].pct_change(144) * 100
    volume_change = df["volume"].pct_change(144) * 100
    
    df["score"] = (
        (df["rsi"] > 60).astype(int) +
        (volume_change > 50).astype(int) +
        (df["spread"] < 3).astype(int) +
        (df["volatility"] > 0.005).astype(int) +
        (price_change > 5).astype(int)
    )
    
    return df

async def recover_existing_positions():
    """Enhanced position recovery with trade log integration"""
    print("🔄 Recovering positions and trade history...")
    
    try:
        # Step 1: Get active trades from log file
        logged_trades = trade_tracker.get_active_trades_from_log(max_age_hours=168)  # 7 days
        print(f"📖 Found {len(logged_trades)} trades in log")
        
        # Step 2: Get current positions from exchange
        ts = order_manager.fetch_server_timestamp()
        params = {"category": "linear", "settleCoin": "USDT"}
        sig = order_manager.generate_signature(ts, settings.RECV_WINDOW, params)
        headers = {
            'X-BAPI-API-KEY':     settings.API_KEY,
            'X-BAPI-SIGN':        sig,
            'X-BAPI-TIMESTAMP':   ts,
            'X-BAPI-RECV-WINDOW': settings.RECV_WINDOW
        }
        
        resp = requests.get(
            f"{settings.BASE_URL}/v5/position/list",
            headers=headers,
            params=params
        )
        
        data = resp.json()
        if data.get("retCode") != 0:
            print(f"❌ Error fetching positions: {data.get('retMsg')}")
            return
        
        # Step 3: Process actual positions
        positions = data.get("result", {}).get("list", [])
        exchange_positions = {}
        
        for pos in positions:
            symbol = pos.get("symbol")
            size = abs(float(pos.get("size", 0)))
            
            if size == 0 or not symbol or not symbol.endswith("USDT"):
                continue
                
            exchange_positions[symbol] = {
                'size': size,
                'side': pos.get("side"),
                'avg_price': float(pos.get("avgPrice", 0)),
                'mark_price': float(pos.get("markPrice", 0)),
                'created_time_ms': int(pos.get("createdTime", 0)),
                'updated_time_ms': int(pos.get("updatedTime", 0))
            }
        
        print(f"📊 Found {len(exchange_positions)} open positions on exchange")
        
        # Step 4: Reconcile logged trades with exchange positions
        recovered_count = 0
        current_time = datetime.now(timezone.utc)
        
        # Process logged trades that still have positions
        for trade_key, trade_data in logged_trades.items():
            symbol, rule_id = trade_key
            
            if symbol in exchange_positions:
                # Trade exists in both log and exchange - perfect match
                active_trades[trade_key] = trade_data
                
                # Set up auto-expiry
                expiry_time = trade_data['expiry_time']
                asyncio.create_task(auto_expire_trade(symbol, rule_id, expiry_time))
                
                entry_time = trade_data['entry_timestamp']
                trade_age = (current_time - entry_time).total_seconds() / 3600
                
                pos_data = exchange_positions[symbol]
                avg_price = pos_data['avg_price']
                mark_price = pos_data['mark_price']
                pnl_pct = ((mark_price - avg_price) / avg_price * 100) if avg_price > 0 else 0
                
                print(f"✅ Recovered: {symbol} ({rule_id}) - {trade_age:.1f}h old, PnL: {pnl_pct:+.2f}%")
                recovered_count += 1
                
                # Remove from exchange_positions so we don't process it again
                del exchange_positions[symbol]
            else:
                # Trade in log but no position - was closed externally
                trade_tracker.log_trade_closed(symbol, rule_id, "external_close_during_downtime")
        
        # Step 5: Handle positions without log entries (manual trades or very old)
        for symbol, pos_data in exchange_positions.items():
            created_time_ms = pos_data['created_time_ms']
            updated_time_ms = pos_data['updated_time_ms']
            
            # Use the more recent timestamp as position reference
            ref_time_ms = max(created_time_ms, updated_time_ms)
            ref_time = datetime.fromtimestamp(ref_time_ms / 1000, timezone.utc)
            
            position_age = current_time - ref_time
            hours_since_ref = position_age.total_seconds() / 3600
            
            # If position is very old (>72h), close it immediately
            if hours_since_ref >= 72:
                order_manager.close_trade(symbol, None, "stale_position")
                send_telegram_message(f"🔄 Closed stale position: {symbol} ({hours_since_ref:.1f}h old)")
                continue
            
            # FIXED: Unknown positions get standardized 48-hour hold time from now
            rule_id = "Recovered-Unknown"
            trade_key = (symbol, rule_id)
            
            # Set entry time to current time (conservative assumption)
            entry_time = current_time
            # Set expiry to 48 hours from now (standardized for unknown trades)
            expiry_time = current_time + timedelta(hours=48)
            
            active_trades[trade_key] = {
                'entry_timestamp': entry_time,
                'entry_price': pos_data['avg_price'],
                'position_size': pos_data['size'],
                'rule_id': rule_id,
                'expiry_time': expiry_time
            }
            
            # Log this unknown position recovery
            trade_tracker.log_trade_opened(
                symbol=symbol,
                rule_id=rule_id,
                entry_price=pos_data['avg_price'],
                position_size=pos_data['size'],
                entry_timestamp=entry_time
            )
            
            # Set up auto-expiry for 48 hours
            asyncio.create_task(auto_expire_trade(symbol, rule_id, expiry_time))
            
            avg_price = pos_data['avg_price']
            mark_price = pos_data['mark_price']
            pnl_pct = ((mark_price - avg_price) / avg_price * 100) if avg_price > 0 else 0
            
            print(f"🔄 Unknown position: {symbol} @ {avg_price:.6f} ({pnl_pct:+.2f}%) - 48h hold time assigned")
            send_telegram_message(
                f"🔄 Unknown Position: {symbol} @ {avg_price:.6f} "
                f"({pnl_pct:+.2f}%) - 48h hold time assigned"
            )
            recovered_count += 1
        
        # Step 6: Clean up old trade log entries
        trade_tracker.cleanup_old_events(max_age_days=30)
        
    except Exception as e:
        print(f"❌ Error during recovery: {e}")

async def auto_expire_trade(symbol, rule_id, expiry_time):
    """Enhanced auto-expiry with logging"""
    delay = (expiry_time - datetime.now(timezone.utc)).total_seconds()
    if delay > 0:
        await asyncio.sleep(delay)
    
    key = (symbol, rule_id)
    if key in active_trades:
        print(f"⏰ [{datetime.now().strftime('%H:%M:%S')}] Auto-expiring {symbol} ({rule_id})")
        # Close the trade and log it
        success = order_manager.close_trade(symbol, rule_id, "expiry")
        if success:
            send_telegram_message(f"⏹️ Trade expired: {symbol} ({rule_id})")
        
        # Remove from active tracking
        del active_trades[key]
        print(f"📝 [{datetime.now().strftime('%H:%M:%S')}] Removed {symbol} ({rule_id}) from active_trades. Total: {len(active_trades)}")

async def process_kline(msg):
    """OPTIMIZED: Enhanced with proper trade data structure"""
    global last_update_ts
    try:
        last_update_ts = time.time()

        topic = msg.get("topic", "")
        data  = msg.get("data")

        if not topic.startswith("kline.5.") or not isinstance(data, list):
            return

        entry = next(
            (e for e in data if isinstance(e, dict) and e.get("confirm") is True),
            None
        )
        if entry is None:
            return

        symbol = topic.split(".")[-1]
        ts     = entry.get("timestamp")
        if ts is None:
            return

        key_bar = (symbol, ts)
        if key_bar in processed_bars:
            return
        processed_bars.add(key_bar)
        
        # ADDED: Periodic cleanup of processed data
        if len(processed_bars) > 1000:
            processed_bars.clear()
        if len(processed_signals) > 1000:
            processed_signals.clear()

        try:
            bar = {
                "open":   float(entry["open"]),
                "high":   float(entry["high"]),
                "low":    float(entry["low"]),
                "close":  float(entry["close"]),
                "volume": float(entry["volume"]),
                "timestamp": ts
            }
        except (KeyError, TypeError, ValueError):
            return

        history[symbol].append(bar)
        df = pd.DataFrame(history[symbol])
        
        # Minimum data requirement for 144-period indicators (need at least 150 bars for stability)
        if len(df) < 150:
            return

        if len(df) > PUMP_LOOKBACK:
            old_close = df["open"].iloc[-1 - PUMP_LOOKBACK]
            new_close = df["close"].iloc[-1]
            pump_pct = (new_close - old_close) / old_close * 100
            
            if pump_pct < PUMP_THRESHOLD:
                return
        else:
            return

        df = apply_indicators(df)
        row = df.iloc[-1]
        
        rule_id = None
        if row["score"] >= 2 and row["spread"] < 4:
            rule_id = "Rule 8"
            print(f"🎯 Signal: {symbol} - Rule 8")
        elif row["rsi"] > 55 and row["volatility"] > 0.008:
            rule_id = "Rule 6"
            print(f"🎯 Signal: {symbol} - Rule 6")
        
        if not rule_id:
            return

        sig_key = (symbol, rule_id, ts)
        if sig_key in processed_signals:
            return
        processed_signals.add(sig_key)

        trade_key = (symbol, rule_id)
        
        if trade_key in active_trades:
            return
        
        # Check if max trades limit reached
        if len(active_trades) >= MAX_ACTIVE_TRADES:
            return
        
        # Check if symbol is in cooldown period
        if not can_trade_symbol(symbol):
            return
            
        if order_manager.has_open_positions([symbol]):
            await risk_mgr.check_unrealized_drawdown()
            return

        price = row["close"]
        print(f"✅ SIGNAL: {symbol} | {rule_id} @ {price:.6f}")
        
        # MODIFIED: Handle enhanced trade data structure
        trade_data = order_manager.open_trade(symbol, "buy", price, row, rule_id)
        if trade_data:
            # Record trade for cooldown tracking
            record_trade_for_symbol(symbol)
            
            # Store the enhanced trade data (not just expiry time)
            active_trades[trade_key] = trade_data
            print(f"📝 [{datetime.now().strftime('%H:%M:%S')}] Added {symbol} ({rule_id}) to active_trades. Total: {len(active_trades)}")
            
            # Set up auto-expiry using the expiry time from trade data
            expiry_time = trade_data['expiry_time']
            asyncio.create_task(auto_expire_trade(symbol, rule_id, expiry_time))

    except Exception as e:
        print(f"⚠️ Error in process_kline: {e}")

async def monitor_symbols(symbols):
    """WebSocket monitoring with dynamic symbol updates"""
    global current_symbols, ws_connection, ws_symbols_subscribed
    
    while True:
        try:
            # Get current symbols for subscription
            symbols_to_monitor = list(current_symbols) if current_symbols else symbols
            
            if not symbols_to_monitor:
                print("⚠️ No symbols to monitor, waiting for refresh...")
                await asyncio.sleep(60)
                continue
            
            sub_msg = json.dumps({"op": "subscribe", "args": [f"kline.5.{s}" for s in symbols_to_monitor]})
            
            async with websockets.connect(WS_URL) as ws:
                # Store connection reference for dynamic updates
                ws_connection = ws
                ws_symbols_subscribed = set(symbols_to_monitor)
                
                print(f"🔵 Connected to WebSocket ({len(symbols_to_monitor)} symbols)")
                await ws.send(sub_msg)
                
                async for raw in ws:
                    if raw and raw.startswith("{"):
                        try:
                            msg = json.loads(raw)
                            if msg.get("op") == "ping":
                                await ws.send(json.dumps({"op": "pong"}))
                            elif msg.get("topic", "").startswith("kline."):
                                asyncio.create_task(process_kline(msg))
                        except Exception as e:
                            pass
                            
        except Exception as e:
            print(f"🔴 WS error, reconnecting in 5s…")
            ws_connection = None
            ws_symbols_subscribed.clear()
            await asyncio.sleep(5)

async def balance_monitor():
    """OPTIMIZED: Reduced frequency for free tier"""
    global last_update_ts
    while True:
        await asyncio.sleep(180)  # OPTIMIZED: 3 min for better server
        try:
            await risk_mgr.check_daily_balance_drawdown()
            last_update_ts = time.time()
        except Exception as e:
            print(f"⚠️ balance_monitor error: {e}")

async def pnl_fallback_monitor():
    global last_update_ts
    while True:
        await asyncio.sleep(5)  # OPTIMIZED: Back to 5s for better server
        try:
            await risk_mgr.check_unrealized_drawdown()
            last_update_ts = time.time()
        except Exception as e:
            print(f"⚠️ pnl_fallback error: {e}")

async def watchdog():
    while True:
        await asyncio.sleep(10)
        if time.time() - last_update_ts > 60:
            print("⚠️ Watchdog: no updates >60s, liquidating.")
            order_manager.close_all_positions(active_trades)
            send_telegram_message("🛡️ Watchdog triggered — liquidating all positions.")
            break

async def breakeven_monitor():
    """DEBUGGING: Added debug logging to monitor breakeven checks"""
    print("🔧 Breakeven monitor started")
    
    while True:
        if len(active_trades) == 0:
            print("🔍 No active trades, sleeping 5 minutes...")
            await asyncio.sleep(300)  # 5 min when no trades
        else:
            print(f"🔍 {len(active_trades)} active trades, checking breakeven in 2 minutes...")
            await asyncio.sleep(120)  # 2 minutes when trades active
            try:
                print(f"🔍 [{datetime.now().strftime('%H:%M:%S')}] Running breakeven check...")
                await risk_mgr.check_break_even()
                print(f"🔍 [{datetime.now().strftime('%H:%M:%S')}] Breakeven check completed")
            except Exception as e:
                print(f"⚠️ BE monitor error: {e}")

async def memory_cleanup():
    """ADDED: Periodic memory cleanup for free tier"""
    while True:
        await asyncio.sleep(3600)  # Every hour
        gc.collect()
        # Clear old history data
        for symbol in history:
            if len(history[symbol]) > 200:
                history[symbol] = deque(list(history[symbol])[-200:], maxlen=200)

async def market_diagnostic():
    """OPTIMIZED: Reduced analysis scope"""
    while True:
        await asyncio.sleep(3600)  # CHANGED: 30min -> 60min
        
        # Only analyze top 10 symbols
        symbols_with_data = [(s, len(h)) for s, h in history.items() if len(h) > 30][:10]
        
        if symbols_with_data:
            print(f"📊 Market check: {len(active_trades)} active trades, "
                  f"{len(symbols_with_data)} symbols ready")
            
async def position_reconciliation_monitor():
    """Periodic check to reconcile tracked trades with actual positions"""
    print("🔧 Position reconciliation monitor started")
    
    while True:
        await asyncio.sleep(180)  # Check every 3 minutes (better server)
        try:
            if len(active_trades) > 0:
                externally_closed = reconcile_positions_with_tracking(active_trades)
                
                if externally_closed:
                    for symbol, rule_id in externally_closed:
                        send_telegram_message(f"🔄 Position closed externally: {symbol} ({rule_id})")
                        
        except Exception as e:
            print(f"⚠️ Reconciliation error: {e}")

async def negative_pnl_monitor():
    """Monitor for trades with negative PnL after 8 hours and auto-close them"""
    print("🔧 8-hour negative PnL monitor started")
    
    while True:
        await asyncio.sleep(180)  # Check every 3 minutes (better server)
        try:
            if len(active_trades) == 0:
                await asyncio.sleep(300)  # Sleep longer when no trades
                continue
                
            current_time = datetime.now(timezone.utc)
            trades_to_close = []
            
            for trade_key, trade_data in active_trades.items():
                symbol, rule_id = trade_key
                
                # Check if trade is older than 8 hours
                entry_time = trade_data.get('entry_timestamp')
                if not entry_time:
                    continue
                    
                trade_age = (current_time - entry_time).total_seconds() / 3600
                
                if trade_age >= 8.0:
                    # Check PnL for this trade
                    try:
                        # Get current position for this symbol
                        ts = order_manager.fetch_server_timestamp()
                        params = {"category": "linear", "symbol": symbol}
                        sig = order_manager.generate_signature(ts, settings.RECV_WINDOW, params)
                        headers = {
                            'X-BAPI-API-KEY': settings.API_KEY,
                            'X-BAPI-SIGN': sig,
                            'X-BAPI-TIMESTAMP': ts,
                            'X-BAPI-RECV-WINDOW': settings.RECV_WINDOW
                        }
                        
                        import requests
                        resp = requests.get(f"{settings.BASE_URL}/v5/position/list", headers=headers, params=params)
                        data = resp.json()
                        
                        if data.get("retCode") == 0:
                            positions = data.get("result", {}).get("list", [])
                            for pos in positions:
                                if pos.get("symbol") == symbol and float(pos.get("size", 0)) > 0:
                                    unrealized_pnl = float(pos.get("unrealisedPnl", 0))
                                    
                                    if unrealized_pnl < 0:
                                        trades_to_close.append((symbol, rule_id, trade_age, unrealized_pnl))
                                        print(f"⏰ Trade {symbol} ({rule_id}) - {trade_age:.1f}h old with negative PnL: {unrealized_pnl:.2f} USDT - marking for closure")
                                    break
                    except Exception as e:
                        print(f"⚠️ Error checking PnL for {symbol}: {e}")
            
            # Close trades marked for closure
            for symbol, rule_id, trade_age, pnl in trades_to_close:
                print(f"🔄 Auto-closing negative PnL trade: {symbol} ({rule_id}) - {trade_age:.1f}h old, PnL: {pnl:.2f} USDT")
                success = order_manager.close_trade(symbol, rule_id, "8h_negative_pnl")
                
                if success:
                    trade_key = (symbol, rule_id)
                    if trade_key in active_trades:
                        del active_trades[trade_key]
                    send_telegram_message(f"📉 8h Negative PnL Close: {symbol} ({rule_id}) - {pnl:.2f} USDT after {trade_age:.1f}h")
                        
        except Exception as e:
            print(f"⚠️ Negative PnL monitor error: {e}")


# ADD utility functions for backward compatibility
def get_active_trade_age(symbol, rule_id):
    """Get the age of a specific trade in hours"""
    trade_key = (symbol, rule_id)
    if trade_key in active_trades:
        trade_data = active_trades[trade_key]
        return get_trade_age_hours(trade_data)
    return 0.0


def get_active_trade_count():
    """Get count of currently active trades"""
    return len(active_trades)


def get_oldest_trade_info():
    """Get info about the oldest active trade"""
    if not active_trades:
        return None
    
    oldest_trade = None
    oldest_age = 0
    
    for trade_key, trade_data in active_trades.items():
        age = get_trade_age_hours(trade_data)
        if age > oldest_age:
            oldest_age = age
            oldest_trade = {
                'symbol': trade_key[0],
                'rule_id': trade_key[1],
                'age_hours': age,
                'trade_data': trade_data
            }
    
    return oldest_trade

async def main():
    try:
        global current_symbols, symbol_last_refresh
        
        # Initial symbol fetch
        symbols = fetch_symbols()
        print(f"📊 Fetched {len(symbols)} symbols")
        
        # Initialize current_symbols set
        current_symbols = set(symbols)
        symbol_last_refresh = time.time()
        
        historical_data = await load_all_historical_data(symbols)
        
        for symbol, data in historical_data.items():
            history[symbol] = deque(maxlen=200)  # Increased for 144-period indicators on 5min bars
            if data:
                history[symbol].extend(data)
        
        print(f"✅ Loaded data for {len([s for s, d in historical_data.items() if d])} symbols")
        
        # ENHANCED: Recovery with trade log integration
        await recover_existing_positions()
        
        # ENHANCED: Ensure active_trades uses enhanced structure
        global active_trades
        active_trades = enhance_active_trades_structure(active_trades)
        
        try:
            if risk_mgr.daily_balance_ref is None:
                risk_mgr.daily_balance_ref = risk_mgr.get_account_balance()
                print(f"⚡️ Startup snapshot: {risk_mgr.daily_balance_ref}")
        except Exception as e:
            print(f"⚠️ Startup balance error: {e}")

        # ENHANCED: Start monitors with reconciliation and 8h negative PnL monitor
        monitor_tasks = [
            asyncio.create_task(balance_monitor()),
            asyncio.create_task(pnl_fallback_monitor()),
            asyncio.create_task(breakeven_monitor()),
            asyncio.create_task(watchdog()),
            asyncio.create_task(market_diagnostic()),
            asyncio.create_task(memory_cleanup()),
            asyncio.create_task(position_reconciliation_monitor()),  # NEW
            asyncio.create_task(negative_pnl_monitor()),  # NEW: 8h negative PnL auto-close
            asyncio.create_task(refresh_symbols_and_data()) # NEW
        ]
        
        print(f"🚀 All systems ready! Monitoring {len(symbols)} symbols...")
        
        startup_msg = (
            f"🤖 Bot Started - {len(symbols)} symbols, "
            f"{len(active_trades)} active trades, "
            f"Balance: {risk_mgr.daily_balance_ref:.2f} USDT\n"
            f"🔄 Symbol refresh: Every 4 hours"
        )
        send_telegram_message(startup_msg)
        
        await monitor_symbols(symbols)
        
    except Exception as e:
        print(f"❌ Bot crashed: {e}")
        send_telegram_message(f"❌ Bot crashed: {str(e)}")
        raise
if __name__ == "__main__":
    print("🚀 Starting Live Trading Bot (AWS Optimized)…")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        import sys
        sys.exit(1)