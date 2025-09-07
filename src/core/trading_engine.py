"""
Core trading engine that coordinates all trading activities.
"""

import asyncio
import pandas as pd
import time
from collections import deque
from datetime import datetime, timezone
from typing import Dict, Set, Optional, Tuple

from ..config.settings import trading_config, data_config, system_config
from ..data.market_data import MarketDataManager
from ..data.indicators import TechnicalAnalyzer
from ..data.websocket import WebSocketManager
from ..trading.executor import TradeExecutor
from ..utils.helpers import TradingRestrictions, format_timestamp


class TradingEngine:
    """Core trading engine that coordinates all components"""
    
    def __init__(self, risk_manager, trade_tracker, telegram_alerts):
        # External dependencies
        self.risk_manager = risk_manager
        self.trade_tracker = trade_tracker
        self.telegram_alerts = telegram_alerts
        
        # Core components
        self.market_data = MarketDataManager()
        self.analyzer = TechnicalAnalyzer()
        self.executor = TradeExecutor()
        self.restrictions = TradingRestrictions()
        
        # State management
        self.active_trades = {}
        self.processed_bars = set()
        self.processed_signals = set()
        self.current_symbols = set()
        self.symbol_last_refresh = 0
        
        # WebSocket manager (initialized after message handler is set)
        self.websocket_manager = None
        
        # Performance tracking
        self.last_update_timestamp = time.time()
    
    async def initialize(self):
        """Initialize the trading engine"""
        print("🚀 Initializing trading engine...")
        
        # Fetch initial symbols
        symbols = self.market_data.fetch_symbols()
        print(f"📊 Fetched {len(symbols)} symbols")
        
        self.current_symbols = set(symbols)
        self.symbol_last_refresh = time.time()
        
        # Load historical data
        historical_data = await self.market_data.load_all_historical_data(symbols)
        self.market_data.initialize_history(historical_data)
        
        successful_loads = len([s for s, d in historical_data.items() if d])
        print(f"✅ Loaded data for {successful_loads} symbols")
        
        # Initialize WebSocket manager with message handler
        self.websocket_manager = WebSocketManager(self._handle_websocket_message)
        
        # Recover existing positions
        await self._recover_existing_positions()
        
        # Set daily balance reference
        try:
            if self.risk_manager.daily_balance_ref is None:
                self.risk_manager.daily_balance_ref = self.risk_manager.get_account_balance()
                print(f"⚡️ Startup snapshot: {self.risk_manager.daily_balance_ref}")
        except Exception as e:
            print(f"⚠️ Startup balance error: {e}")
        
        print("✅ Trading engine initialized")
    
    async def _handle_websocket_message(self, message: dict):
        """Handle incoming WebSocket messages"""
        await self._process_kline(message)
    
    async def _process_kline(self, message: dict):
        """Process incoming kline data and generate signals"""
        try:
            self.last_update_timestamp = time.time()
            
            topic = message.get("topic", "")
            data = message.get("data")
            
            if not topic.startswith(f"kline.{data_config.TIMEFRAME}.") or not isinstance(data, list):
                return
            
            # Find confirmed bar
            entry = next(
                (e for e in data if isinstance(e, dict) and e.get("confirm") is True),
                None
            )
            if entry is None:
                return
            
            symbol = topic.split(".")[-1]
            timestamp = entry.get("timestamp")
            if timestamp is None:
                return
            
            # Check if already processed
            bar_key = (symbol, timestamp)
            if bar_key in self.processed_bars:
                return
            self.processed_bars.add(bar_key)
            
            # Periodic cleanup
            if len(self.processed_bars) > 1000:
                self.processed_bars.clear()
            if len(self.processed_signals) > 1000:
                self.processed_signals.clear()
            
            # Parse bar data
            try:
                bar = {
                    "open": float(entry["open"]),
                    "high": float(entry["high"]),
                    "low": float(entry["low"]),
                    "close": float(entry["close"]),
                    "volume": float(entry["volume"]),
                    "timestamp": timestamp
                }
            except (KeyError, TypeError, ValueError):
                return
            
            # Update market data
            self.market_data.update_bar(symbol, bar)
            
            # Get symbol data for analysis
            symbol_data = self.market_data.get_symbol_data(symbol)
            if not symbol_data or len(symbol_data) < data_config.MIN_DATA_BARS:
                return
            
            # Convert to DataFrame for analysis
            df = pd.DataFrame(symbol_data)
            
            # Generate signal
            signal_rule = self.analyzer.generate_signal(df)
            if not signal_rule:
                return
            
            # Check if signal already processed
            signal_key = (symbol, signal_rule, timestamp)
            if signal_key in self.processed_signals:
                return
            self.processed_signals.add(signal_key)
            
            # Attempt to execute trade
            await self._attempt_trade_execution(symbol, signal_rule, bar["close"], df)
            
        except Exception as e:
            print(f"⚠️ Error in _process_kline: {e}")
    
    async def _attempt_trade_execution(self, symbol: str, rule_id: str, price: float, df: pd.DataFrame):
        """Attempt to execute a trade based on signal"""
        trade_key = (symbol, rule_id)
        
        # Check if already have active trade for this symbol/rule
        if trade_key in self.active_trades:
            return
        
        # Check max trades limit
        if len(self.active_trades) >= trading_config.MAX_ACTIVE_TRADES:
            return
        
        # Check symbol cooldown
        if not self.restrictions.can_trade_symbol(symbol):
            return
        
        # Check for existing positions
        if await self._has_open_positions([symbol]):
            await self.risk_manager.check_unrealized_drawdown()
            return
        
        print(f"✅ SIGNAL: {symbol} | {rule_id} @ {price:.6f}")
        
        # Execute trade
        trade_data = self.executor.open_trade(symbol, "buy", price, rule_id)
        if trade_data:
            # Record trade for cooldown tracking
            self.restrictions.record_trade_for_symbol(symbol)
            
            # Log trade
            self.trade_tracker.log_trade_opened(
                symbol=symbol,
                rule_id=rule_id,
                entry_price=price,
                position_size=trade_data['position_size'],
                entry_timestamp=trade_data['entry_timestamp']
            )
            
            # Store active trade
            self.active_trades[trade_key] = trade_data
            print(f"📝 [{format_timestamp(datetime.now(timezone.utc))}] Added {symbol} ({rule_id}) to active_trades. Total: {len(self.active_trades)}")
            
            # Set up auto-expiry
            asyncio.create_task(self._auto_expire_trade(symbol, rule_id, trade_data['expiry_time']))
            
            # Add to batch notification instead of sending individual message
            try:
                from telegram_alerts import batch_notifier
                
                # Safely extract TP/SL prices
                if isinstance(trade_data, dict):
                    tp_price = trade_data.get('take_profit', price * 1.3)  # Default 30% TP
                    sl_price = trade_data.get('stop_loss', price * 0.9)    # Default 10% SL
                else:
                    print(f"⚠️ Unexpected trade_data format: {type(trade_data)} - {trade_data}")
                    tp_price = price * 1.3  # Default 30% TP
                    sl_price = price * 0.9   # Default 10% SL
                
                batch_notifier.add_trade_alert(
                    symbol, 
                    price, 
                    tp_price, 
                    sl_price, 
                    rule_id
                )
                
            except Exception as batch_error:
                print(f"⚠️ Batch notification error: {batch_error}")
                # Send individual message as fallback
                msg = (
                    f"🚨 Trade Alert: {symbol}\n"
                    f"Entry: {price} | Rule: {rule_id}"
                )
                self.telegram_alerts.send_message(msg)
    
    async def _auto_expire_trade(self, symbol: str, rule_id: str, expiry_time: datetime):
        """Auto-expire trade after specified time"""
        delay = (expiry_time - datetime.now(timezone.utc)).total_seconds()
        if delay > 0:
            await asyncio.sleep(delay)
        
        trade_key = (symbol, rule_id)
        if trade_key in self.active_trades:
            print(f"⏰ [{format_timestamp(datetime.now(timezone.utc))}] Auto-expiring {symbol} ({rule_id})")
            
            # Close trade (implementation would call order_manager.close_trade)
            # For now, just remove from tracking
            del self.active_trades[trade_key]
            
            self.telegram_alerts.send_message(f"⏹️ Trade expired: {symbol} ({rule_id})")
            print(f"📝 [{format_timestamp(datetime.now(timezone.utc))}] Removed {symbol} ({rule_id}) from active_trades. Total: {len(self.active_trades)}")
    
    async def _recover_existing_positions(self):
        """Recover existing positions from trade log"""
        print("🔄 Recovering positions and trade history...")
        
        try:
            # Get active trades from log
            logged_trades = self.trade_tracker.get_active_trades_from_log(max_age_hours=168)  # 7 days
            print(f"📖 Found {len(logged_trades)} trades in log")
            
            # For now, just print recovery info
            # Full implementation would reconcile with exchange positions
            for trade_key, trade_data in logged_trades.items():
                try:
                    symbol, rule_id = trade_key
                    
                    # Ensure trade_data is in expected format
                    if not isinstance(trade_data, dict):
                        print(f"⚠️ Skipping invalid trade data for {symbol}: {type(trade_data)} - {trade_data}")
                        continue
                    
                    self.active_trades[trade_key] = trade_data
                    
                    # Set up auto-expiry
                    expiry_time = trade_data.get('expiry_time')
                    if expiry_time and isinstance(expiry_time, datetime):
                        asyncio.create_task(self._auto_expire_trade(symbol, rule_id, expiry_time))
                    elif expiry_time:
                        print(f"⚠️ Invalid expiry_time format for {symbol}: {expiry_time}")
                        
                except Exception as trade_error:
                    print(f"⚠️ Error processing trade recovery for {trade_key}: {trade_error}")
                    continue
            
            print(f"✅ Recovered {len(logged_trades)} active trades")
            
        except Exception as e:
            print(f"❌ Error during recovery: {e}")
    
    async def _has_open_positions(self, symbols: list) -> bool:
        """Check if there are open positions for given symbols"""
        # Simplified implementation - in full version would check exchange
        return False
    
    async def start_websocket_monitoring(self):
        """Start WebSocket monitoring"""
        await self.websocket_manager.connect_and_monitor(self.current_symbols)
    
    async def refresh_symbols_and_data(self):
        """Refresh symbols periodically"""
        while True:
            try:
                await asyncio.sleep(system_config.SYMBOL_REFRESH_INTERVAL)
                
                print(f"🔄 [{format_timestamp(datetime.now(timezone.utc))}] Refreshing symbols (4-hour cycle)...")
                
                # Fetch new symbols
                new_symbols_list = self.market_data.fetch_symbols()
                new_symbols_set = set(new_symbols_list)
                
                print(f"📊 Fetched {len(new_symbols_list)} symbols")
                
                # Find changes
                new_symbols = new_symbols_set - self.current_symbols
                removed_symbols = self.current_symbols - new_symbols_set
                
                if new_symbols:
                    print(f"🆕 New symbols to monitor: {list(new_symbols)}")
                    
                    # Load data for new symbols
                    new_data = await self.market_data.load_all_historical_data(list(new_symbols))
                    
                    # Add to history
                    for symbol, data in new_data.items():
                        self.market_data.add_symbol_history(symbol)
                        if data:
                            for bar in data:
                                self.market_data.update_bar(symbol, bar)
                    
                    # Update WebSocket subscription
                    await self.websocket_manager.update_subscription(new_symbols_set)
                    
                    self.telegram_alerts.send_message(f"🔄 Symbol refresh: Added {len(new_symbols)} new symbols to monitoring")
                
                if removed_symbols:
                    print(f"🗑️ Removed symbols from monitoring: {list(removed_symbols)}")
                    
                    # Clean up data
                    self.market_data.cleanup_old_symbols(new_symbols_set)
                    
                    # Update WebSocket subscription
                    await self.websocket_manager.update_subscription(new_symbols_set)
                    
                    self.telegram_alerts.send_message(f"🔄 Symbol refresh: Removed {len(removed_symbols)} symbols from monitoring")
                
                # Update current symbols
                self.current_symbols = new_symbols_set
                self.symbol_last_refresh = time.time()
                
                print(f"✅ [{format_timestamp(datetime.now(timezone.utc))}] Symbol refresh completed. Monitoring {len(self.current_symbols)} symbols")
                
            except Exception as e:
                print(f"❌ Error during symbol refresh: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes before retrying
    
    def get_active_trades(self) -> Dict:
        """Get current active trades"""
        return self.active_trades.copy()
    
    def get_trading_stats(self) -> Dict:
        """Get current trading statistics"""
        return {
            "active_trades": len(self.active_trades),
            "symbols_monitored": len(self.current_symbols),
            "processed_bars": len(self.processed_bars),
            "processed_signals": len(self.processed_signals),
            "last_update": self.last_update_timestamp
        }