"""
WebSocket connection and data streaming management.
"""

import asyncio
import json
import websockets
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK
from datetime import datetime
from typing import Set, Callable, Optional

from ..config.settings import api_config, system_config, data_config


class WebSocketManager:
    """Manages WebSocket connections and subscriptions"""
    
    def __init__(self, message_handler: Callable):
        self.connection: Optional[websockets.WebSocketServerProtocol] = None
        self.subscribed_symbols: Set[str] = set()
        self.message_handler = message_handler
        self.current_symbols: Set[str] = set()
        
    async def connect_and_monitor(self, initial_symbols: Set[str]):
        """Main WebSocket connection loop with automatic reconnection"""
        self.current_symbols = initial_symbols.copy()
        
        while True:
            try:
                symbols_to_monitor = list(self.current_symbols) if self.current_symbols else []
                
                if not symbols_to_monitor:
                    print("⚠️ No symbols to monitor, waiting for refresh...")
                    await asyncio.sleep(60)
                    continue
                
                # Create subscription message
                sub_msg = json.dumps({
                    "op": "subscribe", 
                    "args": [f"kline.{data_config.TIMEFRAME}.{s}" for s in symbols_to_monitor]
                })
                
                async with websockets.connect(api_config.WS_URL) as ws:
                    self.connection = ws
                    self.subscribed_symbols = set(symbols_to_monitor)
                    
                    print(f"🔵 Connected to WebSocket ({len(symbols_to_monitor)} symbols)")
                    await ws.send(sub_msg)
                    
                    # Message processing loop
                    async for raw_message in ws:
                        if raw_message and raw_message.startswith("{"):
                            try:
                                message = json.loads(raw_message)
                                await self._handle_message(message)
                            except Exception:
                                pass
                                
            except (ConnectionClosedError, ConnectionClosedOK):
                print("🔴 WebSocket connection closed, reconnecting...")
            except Exception:
                print("🔴 WebSocket error, reconnecting...")
            finally:
                self.connection = None
                self.subscribed_symbols.clear()
                
            await asyncio.sleep(system_config.WS_RECONNECT_DELAY)
    
    async def _handle_message(self, message: dict):
        """Handle incoming WebSocket messages"""
        if message.get("op") == "ping":
            if self.connection:
                await self.connection.send(json.dumps({"op": "pong"}))
        elif message.get("topic", "").startswith("kline."):
            await self.message_handler(message)
    
    async def update_subscription(self, new_symbols: Set[str]):
        """Update WebSocket subscription when symbols change"""
        if not self.connection:
            self.current_symbols = new_symbols.copy()
            return
        
        try:
            symbols_to_add = new_symbols - self.subscribed_symbols
            symbols_to_remove = self.subscribed_symbols - new_symbols
            
            if symbols_to_add:
                add_msg = json.dumps({
                    "op": "subscribe",
                    "args": [f"kline.{data_config.TIMEFRAME}.{s}" for s in symbols_to_add]
                })
                await self.connection.send(add_msg)
                self.subscribed_symbols.update(symbols_to_add)
                print(f"🔵 Added {len(symbols_to_add)} symbols to WebSocket subscription")
            
            if symbols_to_remove:
                remove_msg = json.dumps({
                    "op": "unsubscribe",
                    "args": [f"kline.{data_config.TIMEFRAME}.{s}" for s in symbols_to_remove]
                })
                await self.connection.send(remove_msg)
                self.subscribed_symbols.difference_update(symbols_to_remove)
                print(f"🔵 Removed {len(symbols_to_remove)} symbols from WebSocket subscription")
            
            self.current_symbols = new_symbols.copy()
            
        except Exception as e:
            print(f"❌ Error updating WebSocket subscription: {e}")
    
    def is_connected(self) -> bool:
        """Check if WebSocket is currently connected"""
        return self.connection is not None
    
    def get_subscribed_symbols(self) -> Set[str]:
        """Get currently subscribed symbols"""
        return self.subscribed_symbols.copy()