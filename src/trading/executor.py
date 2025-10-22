"""
Trade execution and order management.
"""

import os
import json
import hmac
import hashlib
import requests
import math
import time
import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta
from functools import lru_cache
from typing import Dict, Optional, Tuple, List

from ..config.settings import api_config, trading_config
from ..utils.helpers import create_optimized_session


class TradeExecutor:
    """Handles trade execution and order management"""
    
    def __init__(self):
        # Improved timestamp sync
        self._time_offset = 0
        self._last_sync_time = 0
        self._sync_interval = 60  # Re-sync every minute
        
        # Market info cache
        self._market_info_cache = {}
        self._cache_ttl = 3600  # 1 hour
        self._max_cache_size = 200
        
        # Async session for parallel execution
        self._session = None
    
    async def sync_time_with_server(self):
        """Synchronize time with Bybit server"""
        current_time = time.time()
        if current_time - self._last_sync_time < self._sync_interval:
            return  # Don't sync too frequently
            
        try:
            if not self._session:
                self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3))
                
            async with self._session.get(f"{api_config.BASE_URL}/v5/public/time") as resp:
                data = await resp.json()
                server_time = int(data["time"])
                local_time = int(datetime.now(timezone.utc).timestamp() * 1000)
                
                self._time_offset = server_time - local_time
                self._last_sync_time = current_time
                
        except Exception:
            # Use cached offset or default to 0
            pass
    
    def get_synchronized_timestamp(self) -> str:
        """Get synchronized timestamp using cached offset"""
        local_time = int(datetime.now(timezone.utc).timestamp() * 1000)
        synchronized_time = local_time + self._time_offset
        return str(synchronized_time)
    
    def generate_signature(self, timestamp: str, recv_window: str, params: Dict = None, body: str = "") -> str:
        """Generate HMAC-SHA256 signature for Bybit API"""
        params = params or {}
        query_string = "&".join(f"{k}={params[k]}" for k in params)
        
        to_sign = f"{timestamp}{api_config.API_KEY}{recv_window}{query_string}{body}"
        
        return hmac.new(
            api_config.API_SECRET.encode(),
            to_sign.encode(),
            hashlib.sha256
        ).hexdigest()
    
    async def fetch_market_info_async(self, symbol: str) -> Dict:
        """Fetch market information asynchronously with caching"""
        current_time = time.time()
        
        # Check cache
        if symbol in self._market_info_cache:
            info, timestamp = self._market_info_cache[symbol]
            if current_time - timestamp < self._cache_ttl:
                return info
        
        # Clean cache if too large
        if len(self._market_info_cache) > self._max_cache_size:
            sorted_cache = sorted(self._market_info_cache.items(), key=lambda x: x[1][1])
            for k, _ in sorted_cache[:10]:  # Remove 10 oldest
                del self._market_info_cache[k]
        
        # Fetch fresh data
        try:
            await self.sync_time_with_server()
            ts = self.get_synchronized_timestamp()
            params = {"category": "linear", "symbol": symbol}
            sig = self.generate_signature(ts, api_config.RECV_WINDOW, params)
            headers = {
                'X-BAPI-API-KEY': api_config.API_KEY,
                'X-BAPI-SIGN': sig,
                'X-BAPI-TIMESTAMP': ts,
                'X-BAPI-RECV-WINDOW': api_config.RECV_WINDOW,
                'Content-Type': 'application/json'
            }
            
            if not self._session:
                self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3))
            
            async with self._session.get(
                f"{api_config.BASE_URL}/v5/market/instruments-info",
                headers=headers,
                params=params
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("retCode") == 0:
                        info = data.get("result", {}).get("list", [{}])[0]
                        self._market_info_cache[symbol] = (info, current_time)
                        return info
                        
        except Exception:
            pass
        
        return {}
    
    async def calculate_order_params_async(self, symbol: str, price: float) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], Optional[float]]:
        """Calculate order parameters asynchronously"""
        info = await self.fetch_market_info_async(symbol)
        if not info:
            return None, None, None, None, None
        
        min_qty = float(info['lotSizeFilter']['minOrderQty'])
        qty_step = float(info['lotSizeFilter']['qtyStep'])
        tick = float(info['priceFilter']['tickSize'])
        min_notional = float(info.get('notionalFilter', {}).get('minNotional', 0))
        
        # Calculate quantity
        raw_qty = trading_config.BASE_POSITION_SIZE_USD / price
        qty = math.floor(raw_qty / qty_step) * qty_step
        
        if qty < min_qty:
            qty = min_qty
        if min_notional and price * qty < min_notional:
            qty = math.ceil(min_notional / price / qty_step) * qty_step
        
        qty = round(qty, len(str(qty_step).split('.')[-1]))
        
        # Calculate prices
        sl_price = round(price * (1 - trading_config.STOPLOSS_PERCENT/100), len(str(tick).split('.')[-1]))
        tp_price = round(price * (1 + trading_config.TAKEPROFIT_PERCENT/100), len(str(tick).split('.')[-1]))
        act_price = round(price * (1 + trading_config.TRAIL_ACTIVATION_PERCENT/100), len(str(tick).split('.')[-1]))
        trail_offset = round(price * (trading_config.TRAIL_OFFSET_PERCENT/100), len(str(tick).split('.')[-1]))
        
        return qty, sl_price, tp_price, act_price, trail_offset
    
    async def execute_market_order_async(self, symbol: str, side: str, quantity: float) -> Dict:
        """Execute a market order asynchronously"""
        entry_order = {
            "category": "linear",
            "symbol": symbol,
            "side": side.capitalize(),
            "orderType": "Market",
            "qty": str(quantity),
            "orderLinkId": os.urandom(16).hex()
        }
        
        await self.sync_time_with_server()
        ts = self.get_synchronized_timestamp()
        payload = json.dumps(entry_order, separators=(',', ':'), sort_keys=True)
        sign = self.generate_signature(ts, api_config.RECV_WINDOW, {}, payload)
        
        headers = {
            'X-BAPI-API-KEY': api_config.API_KEY,
            'X-BAPI-SIGN': sign,
            'X-BAPI-TIMESTAMP': ts,
            'X-BAPI-RECV-WINDOW': api_config.RECV_WINDOW,
            'Content-Type': 'application/json'
        }
        
        if not self._session:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5))
        
        try:
            async with self._session.post(f"{api_config.BASE_URL}/v5/order/create", headers=headers, data=payload) as response:
                return await response.json()
        except Exception as e:
            return {"retCode": -1, "retMsg": f"Network error: {str(e)}"}
    
    async def set_trading_stop_async(self, symbol: str, tp_price: float, sl_price: float, trail_offset: float, act_price: float) -> bool:
        """Set take profit, stop loss, and trailing stop asynchronously"""
        try:
            ts = self.get_synchronized_timestamp()
            ts_payload = {
                "category": "linear",
                "symbol": symbol,
                "positionIdx": 0,
                "takeProfit": str(tp_price),
                "tpTriggerBy": "LastPrice",
                "stopLoss": str(sl_price),
                "slTriggerBy": "LastPrice",
                "trailingStop": str(trail_offset),
                "activePrice": str(act_price),
                "tpslMode": "Full"
            }
            
            data = json.dumps(ts_payload, separators=(',', ':'), sort_keys=True)
            sign = self.generate_signature(ts, api_config.RECV_WINDOW, {}, data)
            
            headers = {
                'X-BAPI-API-KEY': api_config.API_KEY,
                'X-BAPI-SIGN': sign,
                'X-BAPI-TIMESTAMP': ts,
                'X-BAPI-RECV-WINDOW': api_config.RECV_WINDOW,
                'Content-Type': 'application/json'
            }
            
            if not self._session:
                self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5))
            
            async with self._session.post(f"{api_config.BASE_URL}/v5/position/trading-stop", headers=headers, data=data) as response:
                return response.status == 200
                
        except Exception:
            return False
    
    async def open_trade_async(self, symbol: str, side: str, price: float, rule_id: str, position_size_multiplier: float = 1.0) -> Optional[Dict]:
        """Open a complete trade asynchronously with parallel execution"""
        # Get market info for position size adjustment
        info = await self.fetch_market_info_async(symbol)
        if not info:
            return None

        # Calculate order parameters
        order_params = await self.calculate_order_params_async(symbol, price)
        if not order_params or order_params[0] is None:
            return None

        qty, sl_price, tp_price, act_price, trail_offset = order_params

        # Apply position size multiplier (for weekly drawdown protection)
        if position_size_multiplier < 1.0:
            qty_step = float(info['lotSizeFilter']['qtyStep'])
            qty = math.floor((qty * position_size_multiplier) / qty_step) * qty_step
            min_qty = float(info['lotSizeFilter']['minOrderQty'])
            if qty < min_qty:
                print(f"⚠️ Reduced position size below minimum for {symbol}, using minimum")
                qty = min_qty
        
        # Capture entry timestamp
        entry_timestamp = datetime.now(timezone.utc)
        
        # Execute market order
        order_result = await self.execute_market_order_async(symbol, side, qty)
        if order_result.get("retCode") != 0:
            print(f"❌ Entry failed for {symbol}: {order_result}")
            return None
        
        # Set trading stops asynchronously (non-blocking)
        asyncio.create_task(self._set_stops_with_retry(symbol, tp_price, sl_price, trail_offset, act_price))
        
        print(f"✅ Opened {symbol} @ {price} Qty={qty}")
        
        # Return trade data immediately
        return {
            'entry_timestamp': entry_timestamp,
            'entry_price': price,
            'position_size': qty,
            'rule_id': rule_id,
            'expiry_time': entry_timestamp + timedelta(hours=trading_config.TRADE_EXPIRY_HOURS),
            'take_profit': tp_price,
            'stop_loss': sl_price
        }
    
    async def _set_stops_with_retry(self, symbol: str, tp_price: float, sl_price: float, trail_offset: float, act_price: float, max_retries: int = 3):
        """Set trading stops with retry logic"""
        for attempt in range(max_retries):
            if await self.set_trading_stop_async(symbol, tp_price, sl_price, trail_offset, act_price):
                return
            
            if attempt < max_retries - 1:
                await asyncio.sleep(1)  # Brief delay before retry
        
        print(f"⚠️ Warning: Failed to set trading stops for {symbol} after {max_retries} attempts")
    
    def open_trade(self, symbol: str, side: str, price: float, rule_id: str, position_size_multiplier: float = 1.0) -> Optional[Dict]:
        """Synchronous wrapper for backward compatibility - uses sync methods"""
        # Fallback to synchronous implementation for compatibility
        return self._open_trade_sync(symbol, side, price, rule_id, position_size_multiplier)

    def _open_trade_sync(self, symbol: str, side: str, price: float, rule_id: str, position_size_multiplier: float = 1.0) -> Optional[Dict]:
        """Synchronous implementation for compatibility"""
        # Get market info synchronously
        info = self._fetch_market_info_sync(symbol)
        if not info:
            return None
        
        # Calculate order parameters
        order_params = self._calculate_order_params_sync(info, price)
        if not order_params or order_params[0] is None:
            return None

        qty, sl_price, tp_price, act_price, trail_offset = order_params

        # Apply position size multiplier (for weekly drawdown protection)
        if position_size_multiplier < 1.0:
            qty_step = float(info['lotSizeFilter']['qtyStep'])
            qty = math.floor((qty * position_size_multiplier) / qty_step) * qty_step
            min_qty = float(info['lotSizeFilter']['minOrderQty'])
            if qty < min_qty:
                print(f"⚠️ Reduced position size below minimum for {symbol}, using minimum")
                qty = min_qty

        # Capture entry timestamp
        entry_timestamp = datetime.now(timezone.utc)

        # Execute market order synchronously
        order_result = self._execute_market_order_sync(symbol, side, qty)
        if order_result.get("retCode") != 0:
            print(f"❌ Entry failed for {symbol}: {order_result}")
            return None
        
        # Set trading stops synchronously (non-blocking)
        self._set_trading_stop_sync(symbol, tp_price, sl_price, trail_offset, act_price)
        
        print(f"✅ Opened {symbol} @ {price} Qty={qty}")
        
        # Return trade data
        return {
            'entry_timestamp': entry_timestamp,
            'entry_price': price,
            'position_size': qty,
            'rule_id': rule_id,
            'expiry_time': entry_timestamp + timedelta(hours=trading_config.TRADE_EXPIRY_HOURS),
            'take_profit': tp_price,
            'stop_loss': sl_price
        }
    
    def _fetch_market_info_sync(self, symbol: str) -> Dict:
        """Synchronous market info fetch with caching"""
        current_time = time.time()
        
        # Check cache
        if symbol in self._market_info_cache:
            info, timestamp = self._market_info_cache[symbol]
            if current_time - timestamp < self._cache_ttl:
                return info
        
        # Fetch fresh data
        try:
            ts = self._get_sync_timestamp()
            params = {"category": "linear", "symbol": symbol}
            sig = self.generate_signature(ts, api_config.RECV_WINDOW, params)
            headers = {
                'X-BAPI-API-KEY': api_config.API_KEY,
                'X-BAPI-SIGN': sig,
                'X-BAPI-TIMESTAMP': ts,
                'X-BAPI-RECV-WINDOW': api_config.RECV_WINDOW,
                'Content-Type': 'application/json'
            }
            
            resp = requests.get(
                f"{api_config.BASE_URL}/v5/market/instruments-info",
                headers=headers,
                params=params,
                timeout=3
            )
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get("retCode") == 0:
                    info = data.get("result", {}).get("list", [{}])[0]
                    self._market_info_cache[symbol] = (info, current_time)
                    return info
                    
        except Exception:
            pass
        
        return {}
    
    def _get_sync_timestamp(self) -> str:
        """Get synchronized timestamp for sync operations"""
        # Simple sync timestamp - could be enhanced with caching
        try:
            resp = requests.get(f"{api_config.BASE_URL}/v5/public/time", timeout=2)
            return str(resp.json()["time"])
        except:
            return str(int(datetime.now(timezone.utc).timestamp() * 1000))
    
    def _calculate_order_params_sync(self, info: Dict, price: float) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], Optional[float]]:
        """Calculate order parameters synchronously"""
        if not info:
            return None, None, None, None, None
        
        min_qty = float(info['lotSizeFilter']['minOrderQty'])
        qty_step = float(info['lotSizeFilter']['qtyStep'])
        tick = float(info['priceFilter']['tickSize'])
        min_notional = float(info.get('notionalFilter', {}).get('minNotional', 0))
        
        # Calculate quantity
        raw_qty = trading_config.BASE_POSITION_SIZE_USD / price
        qty = math.floor(raw_qty / qty_step) * qty_step
        
        if qty < min_qty:
            qty = min_qty
        if min_notional and price * qty < min_notional:
            qty = math.ceil(min_notional / price / qty_step) * qty_step
        
        qty = round(qty, len(str(qty_step).split('.')[-1]))
        
        # Calculate prices
        sl_price = round(price * (1 - trading_config.STOPLOSS_PERCENT/100), len(str(tick).split('.')[-1]))
        tp_price = round(price * (1 + trading_config.TAKEPROFIT_PERCENT/100), len(str(tick).split('.')[-1]))
        act_price = round(price * (1 + trading_config.TRAIL_ACTIVATION_PERCENT/100), len(str(tick).split('.')[-1]))
        trail_offset = round(price * (trading_config.TRAIL_OFFSET_PERCENT/100), len(str(tick).split('.')[-1]))
        
        return qty, sl_price, tp_price, act_price, trail_offset
    
    def _execute_market_order_sync(self, symbol: str, side: str, quantity: float) -> Dict:
        """Execute market order synchronously"""
        entry_order = {
            "category": "linear",
            "symbol": symbol,
            "side": side.capitalize(),
            "orderType": "Market",
            "qty": str(quantity),
            "orderLinkId": os.urandom(16).hex()
        }
        
        ts = self._get_sync_timestamp()
        payload = json.dumps(entry_order, separators=(',', ':'), sort_keys=True)
        sign = self.generate_signature(ts, api_config.RECV_WINDOW, {}, payload)
        
        headers = {
            'X-BAPI-API-KEY': api_config.API_KEY,
            'X-BAPI-SIGN': sign,
            'X-BAPI-TIMESTAMP': ts,
            'X-BAPI-RECV-WINDOW': api_config.RECV_WINDOW,
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.post(f"{api_config.BASE_URL}/v5/order/create", headers=headers, data=payload, timeout=5)
            return response.json()
        except Exception as e:
            return {"retCode": -1, "retMsg": f"Network error: {str(e)}"}
    
    def _set_trading_stop_sync(self, symbol: str, tp_price: float, sl_price: float, trail_offset: float, act_price: float) -> bool:
        """Set trading stops synchronously"""
        try:
            ts = self._get_sync_timestamp()
            ts_payload = {
                "category": "linear",
                "symbol": symbol,
                "positionIdx": 0,
                "takeProfit": str(tp_price),
                "tpTriggerBy": "LastPrice",
                "stopLoss": str(sl_price),
                "slTriggerBy": "LastPrice",
                "trailingStop": str(trail_offset),
                "activePrice": str(act_price),
                "tpslMode": "Full"
            }
            
            data = json.dumps(ts_payload, separators=(',', ':'), sort_keys=True)
            sign = self.generate_signature(ts, api_config.RECV_WINDOW, {}, data)
            
            headers = {
                'X-BAPI-API-KEY': api_config.API_KEY,
                'X-BAPI-SIGN': sign,
                'X-BAPI-TIMESTAMP': ts,
                'X-BAPI-RECV-WINDOW': api_config.RECV_WINDOW,
                'Content-Type': 'application/json'
            }
            
            response = requests.post(f"{api_config.BASE_URL}/v5/position/trading-stop", headers=headers, data=data, timeout=5)
            return response.status_code == 200
            
        except Exception:
            return False
    
    async def close_session(self):
        """Close the aiohttp session"""
        if self._session:
            await self._session.close()
            self._session = None