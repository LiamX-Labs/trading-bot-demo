"""
Main application entry point for the CFT Prop trading bot.
Restructured for better modularity and maintainability.
"""

import asyncio
import gc
import time
from datetime import datetime, timezone

# Import original modules that we'll keep
from risk_manager import RiskManager
from trade_tracker import trade_tracker
from telegram_alerts import send_telegram_message
from system_logger import system_logger
import settings

# Import new modular components
from .core.trading_engine import TradingEngine
from .config.settings import trading_config, system_config
from .config.bridge import sync_legacy_settings


class TelegramAlertsWrapper:
    """Wrapper for telegram alerts to match interface expected by TradingEngine"""
    
    @staticmethod
    def send_message(message: str):
        send_telegram_message(message)


class CFTPropBot:
    """Main bot application class"""
    
    def __init__(self):
        # Initialize telegram alerts first
        self.telegram_alerts = TelegramAlertsWrapper()
        
        # Initialize new trading engine
        self.trading_engine = TradingEngine(
            risk_manager=None,  # Will be set after risk manager creation
            trade_tracker=trade_tracker,
            telegram_alerts=self.telegram_alerts
        )
        
        # Initialize risk manager with trading engine reference
        self.risk_manager = RiskManager(
            lambda: self.trading_engine.get_active_trades(),
            trading_engine=self.trading_engine
        )
        
        # Set the risk manager reference in trading engine
        self.trading_engine.risk_manager = self.risk_manager
        
        # Monitor tasks
        self.monitor_tasks = []
    
    async def start(self):
        """Start the trading bot"""
        system_logger.log_system_event("startup", "Starting CFT Prop Trading Bot")
        print("🚀 Starting CFT Prop Trading Bot...")
        
        # Sync any user modifications from legacy settings
        sync_legacy_settings()
        
        # Initialize trading engine
        await self.trading_engine.initialize()
        
        # Start all monitoring tasks
        await self._start_monitors()
        
        # Start automatic log cleanup
        asyncio.create_task(self._log_cleanup_task())
        
        # Start WebSocket monitoring (this runs indefinitely)
        await self.trading_engine.start_websocket_monitoring()
    
    async def _start_monitors(self):
        """Start all monitoring tasks"""
        print("🔧 Starting monitoring systems...")
        
        self.monitor_tasks = [
            asyncio.create_task(self._balance_monitor()),
            asyncio.create_task(self._pnl_monitor()),
            asyncio.create_task(self._equity_drawdown_monitor()),  # NEW: Equity-based drawdown
            asyncio.create_task(self._breakeven_monitor()),
            asyncio.create_task(self._watchdog_monitor()),
            asyncio.create_task(self._market_diagnostic_monitor()),
            asyncio.create_task(self._memory_cleanup_monitor()),
            asyncio.create_task(self._position_reconciliation_monitor()),
            asyncio.create_task(self._negative_pnl_monitor()),
            asyncio.create_task(self.trading_engine.refresh_symbols_and_data())
        ]
        
        # ─── STARTUP POSITION RECONCILIATION ───────────────────────────────────────
        # Perform bidirectional reconciliation to detect untracked positions
        print("🔍 Performing startup position reconciliation...")
        await self._perform_startup_reconciliation()

        # Send startup message
        active_trades = self.trading_engine.get_active_trades()
        symbols_count = len(self.trading_engine.current_symbols)

        startup_msg = (
            f"🤖 Bot Started - {symbols_count} symbols, "
            f"{len(active_trades)} active trades, "
            f"Balance: {self.risk_manager.daily_balance_ref:.2f} USDT\n"
            f"🔄 Symbol refresh: Every 4 hours"
        )
        self.telegram_alerts.send_message(startup_msg)
        system_logger.log_system_event("startup_complete",
                                      f"Monitoring {symbols_count} symbols, {len(active_trades)} active trades")

        print(f"🚀 All systems ready! Monitoring {symbols_count} symbols...")
    
    async def _balance_monitor(self):
        """Monitor account balance and drawdown"""
        while True:
            await asyncio.sleep(system_config.BALANCE_CHECK_INTERVAL)
            try:
                await self.risk_manager.check_daily_balance_drawdown()
            except Exception as e:
                print(f"⚠️ Balance monitor error: {e}")
    
    async def _pnl_monitor(self):
        """Monitor unrealized PnL"""
        while True:
            await asyncio.sleep(system_config.PNL_CHECK_INTERVAL)
            try:
                await self.risk_manager.check_unrealized_drawdown()
            except Exception as e:
                print(f"⚠️ PnL monitor error: {e}")

    async def _equity_drawdown_monitor(self):
        """Monitor equity-based drawdowns (daily 2%, weekly 4%/6%)"""
        while True:
            await asyncio.sleep(settings.EQUITY_DRAWDOWN_CHECK_INTERVAL)
            try:
                await self.risk_manager.check_equity_drawdowns()
            except Exception as e:
                print(f"⚠️ Equity drawdown monitor error: {e}")
    
    async def _breakeven_monitor(self):
        """Monitor breakeven conditions"""
        print("🔧 Breakeven monitor started")
        
        while True:
            active_trades = self.trading_engine.get_active_trades()
            
            if len(active_trades) == 0:
                print("🔍 No active trades, sleeping 5 minutes...")
                await asyncio.sleep(300)
            else:
                print(f"🔍 {len(active_trades)} active trades, checking breakeven in 2 minutes...")
                await asyncio.sleep(system_config.BREAKEVEN_CHECK_INTERVAL)
                try:
                    print(f"🔍 [{datetime.now().strftime('%H:%M:%S')}] Running breakeven check...")
                    await self.risk_manager.check_break_even()
                    print(f"🔍 [{datetime.now().strftime('%H:%M:%S')}] Breakeven check completed")
                except Exception as e:
                    print(f"⚠️ Breakeven monitor error: {e}")
    
    async def _watchdog_monitor(self):
        """Watchdog to ensure system is responsive"""
        while True:
            await asyncio.sleep(system_config.WATCHDOG_CHECK_INTERVAL)
            
            stats = self.trading_engine.get_trading_stats()
            time_since_update = time.time() - stats["last_update"]
            
            if time_since_update > system_config.WATCHDOG_TIMEOUT:
                print("⚠️ Watchdog: no updates >60s, system may be stuck.")
                self.telegram_alerts.send_message("🛡️ Watchdog triggered — system monitoring alert.")
                # In a full implementation, might take corrective action here
    
    async def _market_diagnostic_monitor(self):
        """Periodic market diagnostics"""
        while True:
            await asyncio.sleep(system_config.MARKET_DIAGNOSTIC_INTERVAL)
            
            try:
                stats = self.trading_engine.get_trading_stats()
                print(f"📊 Market check: {stats['total_positions']} total positions "
                      f"({stats['active_trades']} active, {stats['breakeven_trades']} breakeven), "
                      f"{stats['symbols_monitored']} symbols monitored")
                
            except Exception as e:
                print(f"⚠️ Market diagnostic error: {e}")
    
    async def _memory_cleanup_monitor(self):
        """Periodic memory cleanup"""
        while True:
            await asyncio.sleep(system_config.MEMORY_CLEANUP_INTERVAL)
            
            try:
                gc.collect()
                self.trading_engine.market_data.memory_cleanup()
                
                # Clean up old cooldown records
                self.trading_engine.restrictions.cleanup_old_records()
                
                print("🧹 Memory cleanup completed")
                
            except Exception as e:
                print(f"⚠️ Memory cleanup error: {e}")

    async def _perform_startup_reconciliation(self):
        """
        Perform bidirectional position reconciliation on startup.
        Detects:
        1. Tracked trades that were externally closed
        2. Untracked positions that need monitoring
        """
        try:
            from order_manager import reconcile_positions_with_tracking
            from datetime import datetime, timezone, timedelta
            from .config.settings import trading_config

            # Combine all tracked trades
            all_tracked = {**self.trading_engine.active_trades, **self.trading_engine.breakeven_trades}

            # Perform bidirectional reconciliation
            externally_closed, untracked_positions = reconcile_positions_with_tracking(
                all_tracked,
                bidirectional=True
            )

            # ─── Handle externally closed positions ────────────────────────────────
            if externally_closed:
                print(f"⚠️ Startup: Found {len(externally_closed)} externally closed positions")
                self.telegram_alerts.send_message(
                    f"⚠️ Startup Reconciliation\n\n"
                    f"Found {len(externally_closed)} positions that were closed externally:\n" +
                    "\n".join([f"  • {symbol} ({rule_id})" for symbol, rule_id in externally_closed])
                )

            # ─── Handle untracked positions ────────────────────────────────────────
            if untracked_positions:
                print(f"⚠️ Startup: Found {len(untracked_positions)} untracked positions")

                # Build notification message
                msg_lines = [f"⚠️ Startup Reconciliation\n\nFound {len(untracked_positions)} untracked positions:\n"]

                for pos in untracked_positions:
                    symbol = pos['symbol']
                    side = pos['side']
                    size = pos['size']
                    entry_price = pos['entry_price']
                    unrealized_pnl = pos['unrealized_pnl']

                    msg_lines.append(
                        f"  • {symbol} ({side})\n"
                        f"    Size: {size} | Entry: ${entry_price:.4f}\n"
                        f"    Unrealized PnL: ${unrealized_pnl:.2f}"
                    )

                    # Add to active trades for monitoring
                    # Use generic rule_id since we don't know which rule triggered it
                    rule_id = "untracked_startup"
                    trade_key = (symbol, rule_id)

                    # Create trade data structure
                    trade_data = {
                        'entry_timestamp': datetime.now(timezone.utc) - timedelta(hours=1),  # Assume 1h old
                        'entry_price': entry_price,
                        'position_size': size,
                        'rule_id': rule_id,
                        'expiry_time': datetime.now(timezone.utc) + timedelta(hours=trading_config.TRADE_EXPIRY_HOURS),
                        'take_profit': None,  # Unknown
                        'stop_loss': None,    # Unknown
                        'untracked_origin': True
                    }

                    # Add to active trades
                    self.trading_engine.active_trades[trade_key] = trade_data
                    print(f"✅ Added {symbol} to active trades for monitoring")

                msg_lines.append(f"\n✅ All untracked positions are now being monitored")

                self.telegram_alerts.send_message("\n".join(msg_lines))

            # ─── Summary ────────────────────────────────────────────────────────────
            if not externally_closed and not untracked_positions:
                print("✅ Startup reconciliation: All positions in sync")
            else:
                print(f"✅ Startup reconciliation complete: {len(externally_closed)} closed, {len(untracked_positions)} untracked positions added")

        except Exception as e:
            print(f"⚠️ Startup reconciliation error: {e}")
            import traceback
            traceback.print_exc()

    async def _position_reconciliation_monitor(self):
        """Monitor position reconciliation"""
        print("🔧 Position reconciliation monitor started")
        
        while True:
            await asyncio.sleep(system_config.RECONCILIATION_CHECK_INTERVAL)
            
            try:
                active_trades = self.trading_engine.get_active_trades()
                if len(active_trades) > 0:
                    total_trades = len(active_trades) + len(self.trading_engine.get_breakeven_trades())
                    print(f"🔍 Reconciliation check: {total_trades} trades being monitored ({len(active_trades)} active, {len(self.trading_engine.get_breakeven_trades())} breakeven)")
                    
                    # Check both active and breakeven trades for external closures
                    from order_manager import reconcile_positions_with_tracking
                    
                    # Check active trades
                    externally_closed_active = reconcile_positions_with_tracking(self.trading_engine.active_trades)
                    
                    # Check breakeven trades
                    externally_closed_breakeven = reconcile_positions_with_tracking(self.trading_engine.breakeven_trades)
                    
                    # Combine results
                    all_externally_closed = externally_closed_active + externally_closed_breakeven
                    
                    if all_externally_closed:
                        print(f"🔄 Reconciliation: Found {len(all_externally_closed)} externally closed positions")
                        
                        # Send enhanced notifications about externally closed trades
                        await self._send_detailed_closure_notifications(all_externally_closed)
                    
            except Exception as e:
                print(f"⚠️ Reconciliation error: {e}")
    
    async def _negative_pnl_monitor(self):
        """Monitor for negative PnL after 8 hours"""
        print("🔧 8-hour negative PnL monitor started")
        
        while True:
            await asyncio.sleep(system_config.NEGATIVE_PNL_CHECK_INTERVAL)
            
            try:
                # Check both active and breakeven trades for 8-hour rule
                active_trades = self.trading_engine.get_active_trades()
                breakeven_trades = self.trading_engine.get_breakeven_trades()
                all_trades = {**active_trades, **breakeven_trades}
                
                if len(all_trades) == 0:
                    continue
                
                current_time = datetime.now(timezone.utc)
                trades_to_check = []
                
                for trade_key, trade_data in all_trades.items():
                    symbol, rule_id = trade_key
                    
                    # Check if trade is older than 8 hours
                    entry_time = trade_data.get('entry_timestamp')
                    if not entry_time:
                        continue
                    
                    trade_age = (current_time - entry_time).total_seconds() / 3600
                    
                    if trade_age >= trading_config.NEGATIVE_PNL_CLOSE_HOURS:
                        print(f"⏰ Trade {symbol} ({rule_id}) is {trade_age:.1f}h old - checking for negative PnL")
                        trades_to_check.append((symbol, rule_id, trade_data))
                
                # Check PnL for old trades and close if negative
                for symbol, rule_id, trade_data in trades_to_check:
                    try:
                        # Import position checking function
                        from order_manager import fetch_server_timestamp, generate_signature
                        import requests
                        import settings
                        
                        # Get current position data
                        ts = fetch_server_timestamp()
                        params = {"category": "linear", "symbol": symbol}
                        sig = generate_signature(ts, settings.RECV_WINDOW, params)
                        headers = {
                            'X-BAPI-API-KEY': settings.API_KEY,
                            'X-BAPI-SIGN': sig,
                            'X-BAPI-TIMESTAMP': ts,
                            'X-BAPI-RECV-WINDOW': settings.RECV_WINDOW,
                            'Content-Type': 'application/json'
                        }
                        
                        resp = requests.get(
                            f"{settings.BASE_URL}/v5/position/list",
                            headers=headers,
                            params=params,
                            timeout=5
                        )
                        
                        if resp.status_code == 200:
                            data = resp.json()
                            positions = data.get("result", {}).get("list", [])
                            
                            for pos in positions:
                                if float(pos.get("size", 0)) == 0:
                                    continue
                                    
                                # Calculate unrealized PnL
                                unrealized_pnl = float(pos.get("unrealisedPnl", 0))
                                
                                if unrealized_pnl < 0:
                                    print(f"❌ Closing {symbol} ({rule_id}) - negative PnL after 8h: ${unrealized_pnl:.2f}")
                                    
                                    # Close the trade
                                    from order_manager import close_trade
                                    success = close_trade(symbol, rule_id, "8h_negative_pnl")
                                    
                                    if success:
                                        # Remove from tracking (works for both active and breakeven)
                                        removed_trade = self.trading_engine.remove_trade_completely(symbol, rule_id, "8h_negative_pnl")
                                        
                                        # Send notification and log
                                        self.telegram_alerts.send_message(
                                            f"🔴 Closed {symbol} ({rule_id}) - Negative PnL: ${unrealized_pnl:.2f} after 8h"
                                        )
                                        system_logger.log_trade_closure(symbol, rule_id, "8h_negative_pnl", unrealized_pnl)
                                else:
                                    print(f"✅ {symbol} ({rule_id}) still positive after 8h: ${unrealized_pnl:.2f}")
                        
                    except Exception as pnl_error:
                        print(f"⚠️ Error checking PnL for {symbol}: {pnl_error}")
                        
            except Exception as e:
                print(f"⚠️ Negative PnL monitor error: {e}")
                system_logger.error(f"Negative PnL monitor error: {e}")
    
    async def _log_cleanup_task(self):
        """Automatic log file cleanup task"""
        while True:
            try:
                # Run cleanup once per day
                await asyncio.sleep(86400)  # 24 hours
                
                # Clean up log files
                system_logger.cleanup_old_logs(settings.LOG_RETENTION_DAYS)
                system_logger.log_system_event("log_cleanup", f"Cleaned logs older than {settings.LOG_RETENTION_DAYS} days")
                
                # Clean up completed trade pairs from trade log
                from trade_tracker import trade_tracker
                removed_pairs = trade_tracker.cleanup_closed_trades()
                if removed_pairs > 0:
                    system_logger.log_system_event("trade_log_cleanup", f"Cleaned {removed_pairs} completed trade pairs from trade log")
                
                # Clean up old trade events (over 30 days)
                trade_tracker.cleanup_old_events(max_age_days=30)
                
            except Exception as e:
                system_logger.error(f"Cleanup error: {e}")
    
    async def _send_detailed_closure_notifications(self, externally_closed_trades):
        """Send detailed notifications for externally closed trades"""
        for symbol, rule_id in externally_closed_trades:
            try:
                # Get trade data from tracking if available
                trade_data = None
                
                # Check if we have the trade data in either active or breakeven
                all_trades = self.trading_engine.get_all_trades()
                trade_key = (symbol, rule_id)
                
                if trade_key in all_trades:
                    trade_data = all_trades[trade_key]
                
                # Get current position data to analyze the closure
                closure_details = await self._analyze_trade_closure(symbol, rule_id, trade_data)
                
                # Send detailed notification
                if closure_details:
                    message = self._format_closure_message(symbol, rule_id, closure_details)
                    self.telegram_alerts.send_message(message)
                else:
                    # Fallback to simple notification
                    self.telegram_alerts.send_message(f"🔄 External closure detected: {symbol} ({rule_id})")
                
                # Log the closure
                system_logger.log_trade_closure(symbol, rule_id, "external_closure")
                
                # Remove from tracking completely
                self.trading_engine.remove_trade_completely(symbol, rule_id, "external_closure")
                
            except Exception as e:
                print(f"⚠️ Error processing closure notification for {symbol}: {e}")
                system_logger.error(f"Error processing closure notification for {symbol}: {e}")
    
    async def _analyze_trade_closure(self, symbol: str, rule_id: str, trade_data: dict) -> dict:
        """Analyze trade closure using multiple methods for better accuracy"""
        try:
            if not trade_data:
                return None
            
            # Method 1: Try closed PnL API (most accurate)
            closure_details = await self._get_from_closed_pnl_api(symbol, trade_data)
            if closure_details:
                closure_details['data_source'] = 'closed_pnl_api'
                return closure_details
            
            # Method 2: Try execution history (fallback)
            closure_details = await self._get_from_execution_history(symbol, trade_data)
            if closure_details:
                closure_details['data_source'] = 'execution_history'
                return closure_details
            
            # Method 3: Use last known position data (estimate)
            closure_details = self._estimate_from_last_position(symbol, trade_data)
            if closure_details:
                closure_details['data_source'] = 'position_estimate'
                return closure_details
            
            return None
            
        except Exception as e:
            print(f"⚠️ Error analyzing trade closure for {symbol}: {e}")
            return None
    
    async def _get_from_closed_pnl_api(self, symbol: str, trade_data: dict) -> dict:
        """Get closure details from Bybit closed PnL API - most accurate method"""
        try:
            from order_manager import fetch_server_timestamp, generate_signature
            import requests
            
            entry_time = trade_data.get('entry_timestamp')
            if not entry_time:
                return None
            
            ts = fetch_server_timestamp()
            params = {
                "category": "linear",
                "symbol": symbol,
                "startTime": str(int(entry_time.timestamp() * 1000)),
                "endTime": str(int(datetime.now(timezone.utc).timestamp() * 1000)),
                "limit": "50"
            }
            sig = generate_signature(ts, settings.RECV_WINDOW, params)
            headers = {
                'X-BAPI-API-KEY': settings.API_KEY,
                'X-BAPI-SIGN': sig,
                'X-BAPI-TIMESTAMP': ts,
                'X-BAPI-RECV-WINDOW': settings.RECV_WINDOW,
                'Content-Type': 'application/json'
            }
            
            resp = requests.get(
                f"{settings.BASE_URL}/v5/position/closed-pnl",
                headers=headers,
                params=params,
                timeout=5
            )
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get("retCode") == 0:
                    pnl_records = data.get("result", {}).get("list", [])
                    
                    for record in pnl_records:
                        created_time_ms = int(record.get('createdTime', 0))
                        created_time = datetime.fromtimestamp(created_time_ms / 1000, tz=timezone.utc)
                        
                        if created_time > entry_time:
                            entry_price = float(record.get('avgEntryPrice', 0))
                            exit_price = float(record.get('avgExitPrice', 0))
                            closed_pnl = float(record.get('closedPnl', 0))
                            
                            if exit_price > 0:
                                price_change_pct = ((exit_price - entry_price) / entry_price) * 100
                                closure_reason = self._determine_closure_reason(price_change_pct, trade_data)
                                
                                return {
                                    'entry_price': entry_price,
                                    'exit_price': exit_price,
                                    'price_change_pct': price_change_pct,
                                    'pnl': closed_pnl,
                                    'exit_qty': float(record.get('qty', 0)),
                                    'closure_reason': closure_reason,
                                    'trade_duration': created_time - entry_time
                                }
            
            return None
            
        except Exception as e:
            print(f"⚠️ Error getting closed PnL for {symbol}: {e}")
            return None
    
    async def _get_from_execution_history(self, symbol: str, trade_data: dict) -> dict:
        """Get closure details from execution history - fallback method"""
        try:
            from order_manager import fetch_server_timestamp, generate_signature
            import requests
            
            entry_time = trade_data.get('entry_timestamp')
            entry_price = trade_data.get('entry_price', 0)
            
            if not entry_time or not entry_price:
                return None
            
            ts = fetch_server_timestamp()
            params = {
                "category": "linear",
                "symbol": symbol,
                "startTime": str(int(entry_time.timestamp() * 1000)),
                "limit": "100"
            }
            sig = generate_signature(ts, settings.RECV_WINDOW, params)
            headers = {
                'X-BAPI-API-KEY': settings.API_KEY,
                'X-BAPI-SIGN': sig,
                'X-BAPI-TIMESTAMP': ts,
                'X-BAPI-RECV-WINDOW': settings.RECV_WINDOW,
                'Content-Type': 'application/json'
            }
            
            resp = requests.get(
                f"{settings.BASE_URL}/v5/execution/list",
                headers=headers,
                params=params,
                timeout=5
            )
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get("retCode") == 0:
                    executions = data.get("result", {}).get("list", [])
                    
                    # Find closing executions after entry time
                    closing_executions = []
                    for execution in executions:
                        exec_time_ms = int(execution.get('execTime', 0))
                        exec_time = datetime.fromtimestamp(exec_time_ms / 1000, tz=timezone.utc)
                        
                        if exec_time > entry_time:
                            closing_executions.append({
                                'price': float(execution.get('execPrice', 0)),
                                'qty': float(execution.get('execQty', 0)),
                                'time': exec_time
                            })
                    
                    if closing_executions:
                        # Calculate weighted average exit price
                        total_qty = sum(exec['qty'] for exec in closing_executions)
                        weighted_price = sum(exec['price'] * exec['qty'] for exec in closing_executions) / total_qty
                        pnl = (weighted_price - entry_price) * total_qty
                        
                        price_change_pct = ((weighted_price - entry_price) / entry_price) * 100
                        closure_reason = self._determine_closure_reason(price_change_pct, trade_data)
                        
                        return {
                            'entry_price': entry_price,
                            'exit_price': weighted_price,
                            'price_change_pct': price_change_pct,
                            'pnl': pnl,
                            'exit_qty': total_qty,
                            'closure_reason': closure_reason,
                            'trade_duration': datetime.now(timezone.utc) - entry_time
                        }
            
            return None
            
        except Exception as e:
            print(f"⚠️ Error getting execution history for {symbol}: {e}")
            return None
    
    def _estimate_from_last_position(self, symbol: str, trade_data: dict) -> dict:
        """Estimate closure details from last known position data"""
        try:
            # Use last known data if available
            last_mark_price = trade_data.get('last_mark_price', 0)
            last_unrealized_pnl = trade_data.get('last_unrealized_pnl', 0)
            entry_price = trade_data.get('entry_price', 0)
            position_size = trade_data.get('position_size', 0)
            entry_time = trade_data.get('entry_timestamp')
            
            if last_mark_price > 0 and entry_price > 0:
                price_change_pct = ((last_mark_price - entry_price) / entry_price) * 100
                closure_reason = self._determine_closure_reason(price_change_pct, trade_data)
                
                return {
                    'entry_price': entry_price,
                    'exit_price': last_mark_price,
                    'price_change_pct': price_change_pct,
                    'pnl': last_unrealized_pnl,
                    'exit_qty': position_size,
                    'closure_reason': closure_reason,
                    'trade_duration': datetime.now(timezone.utc) - entry_time,
                    'estimated': True
                }
            
            return None
            
        except Exception as e:
            print(f"⚠️ Error estimating closure for {symbol}: {e}")
            return None
    
    def _determine_closure_reason(self, price_change_pct: float, trade_data: dict) -> str:
        """Determine the likely reason for trade closure based on price movement"""
        
        # Check if trade was moved to breakeven
        moved_to_breakeven = trade_data.get('moved_to_breakeven')
        
        # Define thresholds
        breakeven_threshold = settings.BREAKEVEN_THRESHOLD
        tp_threshold = settings.TAKEPROFIT_PERCENT
        sl_threshold = -settings.STOPLOSS_PERCENT
        
        # Determine closure reason
        if abs(price_change_pct) < 1.0:  # Less than 1% movement
            return "🟡 Breakeven Exit"
        elif price_change_pct >= tp_threshold * 0.8:  # Close to TP target
            return "🟢 Take Profit"
        elif price_change_pct <= sl_threshold * 0.8:  # Close to SL
            return "🔴 Stop Loss"
        elif moved_to_breakeven and price_change_pct > 0:
            return "🔄 Trailing Stop (from breakeven)"
        elif price_change_pct >= breakeven_threshold:
            return "📈 Trailing Stop"
        elif price_change_pct < 0:
            # Check trade age for 8h rule
            entry_time = trade_data.get('entry_timestamp')
            if entry_time:
                trade_age_hours = (datetime.now(timezone.utc) - entry_time).total_seconds() / 3600
                if trade_age_hours >= settings.NEGATIVE_PNL_CLOSE_HOURS:
                    return "⏰ 8h Negative PnL Exit"
            return "📉 Manual/Early Exit"
        else:
            return "🤔 Unknown Exit"
    
    def _format_closure_message(self, symbol: str, rule_id: str, details: dict) -> str:
        """Format detailed closure message for Telegram"""
        
        entry_price = details['entry_price']
        exit_price = details['exit_price']
        price_change_pct = details['price_change_pct']
        pnl = details['pnl']
        closure_reason = details['closure_reason']
        duration = details['trade_duration']
        data_source = details.get('data_source', 'unknown')
        is_estimated = details.get('estimated', False)
        
        # Format duration
        hours = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)
        duration_str = f"{hours}h {minutes}m"
        
        # Add accuracy indicator
        accuracy_indicator = ""
        if data_source == "closed_pnl_api":
            accuracy_indicator = "✅"  # Most accurate - actual realized PnL
        elif data_source == "execution_history":
            accuracy_indicator = "⚠️"  # Good accuracy - calculated from trades
        elif is_estimated or data_source == "position_estimate":
            accuracy_indicator = "📊"  # Estimated from last known data
        
        # Create message
        message = f"""🔄 **Trade Closed Externally** {accuracy_indicator}
        
**Symbol:** {symbol} ({rule_id})
**Entry:** ${entry_price:.6f}
**Exit:** ${exit_price:.6f}
**Change:** {price_change_pct:+.2f}%
**PnL:** ${pnl:+.2f}
**Duration:** {duration_str}
**Reason:** {closure_reason}
**Data:** {data_source.replace('_', ' ').title()}"""
        
        return message


async def main():
    """Main application entry point"""
    bot = CFTPropBot()
    
    try:
        await bot.start()
        
    except KeyboardInterrupt:
        print("🛑 Bot stopped by user")
        
    except Exception as e:
        print(f"❌ Bot crashed: {e}")
        send_telegram_message(f"❌ Bot crashed: {str(e)}")
        raise


if __name__ == "__main__":
    print("🚀 Starting CFT Prop Trading Bot (Restructured Version)...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        import sys
        sys.exit(1)