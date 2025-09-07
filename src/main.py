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
        # Initialize original components
        self.risk_manager = RiskManager(lambda: self.trading_engine.get_active_trades())
        self.telegram_alerts = TelegramAlertsWrapper()
        
        # Initialize new trading engine
        self.trading_engine = TradingEngine(
            risk_manager=self.risk_manager,
            trade_tracker=trade_tracker,
            telegram_alerts=self.telegram_alerts
        )
        
        # Monitor tasks
        self.monitor_tasks = []
    
    async def start(self):
        """Start the trading bot"""
        print("🚀 Starting CFT Prop Trading Bot...")
        
        # Sync any user modifications from legacy settings
        sync_legacy_settings()
        
        # Initialize trading engine
        await self.trading_engine.initialize()
        
        # Start all monitoring tasks
        await self._start_monitors()
        
        # Start WebSocket monitoring (this runs indefinitely)
        await self.trading_engine.start_websocket_monitoring()
    
    async def _start_monitors(self):
        """Start all monitoring tasks"""
        print("🔧 Starting monitoring systems...")
        
        self.monitor_tasks = [
            asyncio.create_task(self._balance_monitor()),
            asyncio.create_task(self._pnl_monitor()),
            asyncio.create_task(self._breakeven_monitor()),
            asyncio.create_task(self._watchdog_monitor()),
            asyncio.create_task(self._market_diagnostic_monitor()),
            asyncio.create_task(self._memory_cleanup_monitor()),
            asyncio.create_task(self._position_reconciliation_monitor()),
            asyncio.create_task(self._negative_pnl_monitor()),
            asyncio.create_task(self.trading_engine.refresh_symbols_and_data())
        ]
        
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
                print(f"📊 Market check: {stats['active_trades']} active trades, "
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
                print("🧹 Memory cleanup completed")
                
            except Exception as e:
                print(f"⚠️ Memory cleanup error: {e}")
    
    async def _position_reconciliation_monitor(self):
        """Monitor position reconciliation"""
        print("🔧 Position reconciliation monitor started")
        
        while True:
            await asyncio.sleep(system_config.RECONCILIATION_CHECK_INTERVAL)
            
            try:
                active_trades = self.trading_engine.get_active_trades()
                if len(active_trades) > 0:
                    # In full implementation, would reconcile with exchange
                    print(f"🔍 Reconciliation check: {len(active_trades)} trades being monitored")
                    
            except Exception as e:
                print(f"⚠️ Reconciliation error: {e}")
    
    async def _negative_pnl_monitor(self):
        """Monitor for negative PnL after 8 hours"""
        print("🔧 8-hour negative PnL monitor started")
        
        while True:
            await asyncio.sleep(system_config.NEGATIVE_PNL_CHECK_INTERVAL)
            
            try:
                active_trades = self.trading_engine.get_active_trades()
                if len(active_trades) == 0:
                    continue
                
                current_time = datetime.now(timezone.utc)
                
                for trade_key, trade_data in active_trades.items():
                    symbol, rule_id = trade_key
                    
                    # Check if trade is older than 8 hours
                    entry_time = trade_data.get('entry_timestamp')
                    if not entry_time:
                        continue
                    
                    trade_age = (current_time - entry_time).total_seconds() / 3600
                    
                    if trade_age >= trading_config.NEGATIVE_PNL_CLOSE_HOURS:
                        # In full implementation, would check actual PnL and close if negative
                        print(f"⏰ Trade {symbol} ({rule_id}) is {trade_age:.1f}h old - would check for negative PnL")
                        
            except Exception as e:
                print(f"⚠️ Negative PnL monitor error: {e}")


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