"""
Market data management for historical and real-time data.
"""

import asyncio
import aiohttp
import requests
import time
from collections import deque
from datetime import datetime, timezone
from typing import List, Dict, Optional

from ..config.settings import api_config, data_config, system_config, trading_config


class MarketDataManager:
    """Manages market data fetching and storage"""
    
    def __init__(self):
        self.history: Dict[str, deque] = {}
        
    def fetch_symbols(self) -> List[str]:
        """Fetch USDT symbols with volume filtering"""
        try:
            resp = requests.get(f"{api_config.BASE_URL}/v5/market/tickers?category=linear").json()
            syms = []
            
            for ticker in resp.get("result", {}).get("list", []):
                volume = float(ticker.get("turnover24h", 0))
                symbol = ticker.get("symbol", "")
                
                if volume > trading_config.VOLUME_FILTER_USD and symbol.endswith("USDT"):
                    syms.append(symbol)
            
            # Sort by volume (highest first)
            syms = sorted(syms, key=lambda x: float(next(
                ticker.get("turnover24h", 0) 
                for ticker in resp.get("result", {}).get("list", []) 
                if ticker["symbol"] == x
            )), reverse=True)
            
            return syms
            
        except Exception as e:
            print(f"❌ Error fetching symbols: {e}")
            return []
    
    async def fetch_historical_klines_async(
        self, 
        session: aiohttp.ClientSession, 
        symbol: str
    ) -> List[Dict]:
        """Fetch historical kline data for a symbol"""
        try:
            url = f"{api_config.BASE_URL}/v5/market/kline"
            params = {
                "category": "linear",
                "symbol": symbol,
                "interval": data_config.TIMEFRAME,
                "limit": data_config.HISTORY_LIMIT
            }
            
            timeout = aiohttp.ClientTimeout(total=system_config.HTTP_TIMEOUT)
            async with session.get(url, params=params, timeout=timeout) as resp:
                if resp.status != 200:
                    return []
                    
                data = await resp.json()
                if data.get("retCode") != 0:
                    return []
                
                bars = []
                for kline in data.get("result", {}).get("list", []):
                    bars.append({
                        "timestamp": kline[0],
                        "open": float(kline[1]),
                        "high": float(kline[2]),
                        "low": float(kline[3]),
                        "close": float(kline[4]),
                        "volume": float(kline[5]),
                    })
                
                # Sort by timestamp (oldest first)
                bars.sort(key=lambda b: b["timestamp"])
                return bars
                
        except Exception:
            return []
    
    async def load_all_historical_data(self, symbols: List[str]) -> Dict[str, List[Dict]]:
        """Load historical data for all symbols"""
        print(f"📊 Loading historical data for {len(symbols)} symbols...")
        start_time = time.time()
        
        connector = aiohttp.TCPConnector(
            limit=system_config.HTTP_CONNECTION_LIMIT,
            limit_per_host=system_config.HTTP_CONNECTION_LIMIT_PER_HOST
        )
        timeout = aiohttp.ClientTimeout(total=system_config.HTTP_TIMEOUT)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            semaphore = asyncio.Semaphore(system_config.CONCURRENT_REQUESTS)
            
            async def fetch_with_semaphore(symbol):
                async with semaphore:
                    data = await self.fetch_historical_klines_async(session, symbol)
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
    
    def initialize_history(self, historical_data: Dict[str, List[Dict]]):
        """Initialize history deques with historical data"""
        for symbol, data in historical_data.items():
            self.history[symbol] = deque(maxlen=data_config.HISTORY_BUFFER_SIZE)
            if data:
                self.history[symbol].extend(data)
    
    def add_symbol_history(self, symbol: str):
        """Add a new symbol to history tracking"""
        if symbol not in self.history:
            self.history[symbol] = deque(maxlen=data_config.HISTORY_BUFFER_SIZE)
    
    def update_bar(self, symbol: str, bar_data: Dict):
        """Update history with new bar data"""
        if symbol in self.history:
            self.history[symbol].append(bar_data)
    
    def get_symbol_data(self, symbol: str) -> Optional[deque]:
        """Get history data for a symbol"""
        return self.history.get(symbol)
    
    def cleanup_old_symbols(self, active_symbols: set):
        """Clean up history for symbols no longer being tracked"""
        symbols_to_remove = set(self.history.keys()) - active_symbols
        for symbol in symbols_to_remove:
            del self.history[symbol]
    
    def memory_cleanup(self):
        """Perform memory cleanup on history data"""
        for symbol in self.history:
            if len(self.history[symbol]) > data_config.HISTORY_BUFFER_SIZE:
                # Keep only the most recent bars
                recent_data = list(self.history[symbol])[-data_config.HISTORY_BUFFER_SIZE:]
                self.history[symbol] = deque(recent_data, maxlen=data_config.HISTORY_BUFFER_SIZE)