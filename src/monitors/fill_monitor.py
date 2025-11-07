"""
Fill Monitor - Watches for SELL fills and triggers trade closure tracking
============================================================================

This monitor bridges the gap between the shared WebSocket listener (which
writes fills to PostgreSQL) and the bot's internal trade tracking.

When a SELL fill is detected for a tracked position, it:
1. Retrieves fill details (price, quantity, timestamp)
2. Calls alpha_integration.log_trade_closed() for proper P&L tracking
3. Uses FIFO matching to close position entries correctly
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, Set, Optional
from shared.alpha_db_client import AlphaDBClient
from ..integration.alpha_integration import get_integration


class FillMonitor:
    """Monitors database for SELL fills and triggers trade closure tracking"""

    def __init__(self, trading_engine, bot_id: str = 'lxalgo_001', redis_db: int = 1):
        self.trading_engine = trading_engine
        self.bot_id = bot_id
        self.redis_db = redis_db

        # Database client
        self.db_client = AlphaDBClient(bot_id=bot_id, redis_db=redis_db)

        # Alpha integration for logging closes
        self.alpha_integration = get_integration(bot_id=bot_id)

        # Track last processed fill ID to avoid duplicates
        self.last_processed_fill_id = 0

        # Cache of active position symbols
        self.tracked_symbols: Set[str] = set()

        print(f"✅ Fill monitor initialized for {bot_id}")

    def update_tracked_symbols(self):
        """Update the set of symbols we're currently tracking"""
        # Get all active trades from trading engine
        active_trades = self.trading_engine.active_trades
        breakeven_trades = self.trading_engine.breakeven_trades

        # Extract symbols
        self.tracked_symbols = set()
        for (symbol, rule_id) in active_trades.keys():
            self.tracked_symbols.add(symbol)
        for (symbol, rule_id) in breakeven_trades.keys():
            self.tracked_symbols.add(symbol)

    async def start_monitoring(self):
        """Main monitoring loop - polls for new SELL fills"""
        print("🔍 Starting fill monitor...")

        # Get the latest fill ID on startup to avoid processing old fills
        try:
            with self.db_client.pg_conn.cursor() as cur:
                cur.execute("""
                    SELECT COALESCE(MAX(id), 0)
                    FROM trading.fills
                    WHERE bot_id = %s
                """, (self.bot_id,))
                self.last_processed_fill_id = cur.fetchone()[0]
            print(f"🔍 Starting from fill ID: {self.last_processed_fill_id}")
        except Exception as e:
            print(f"⚠️ Error getting initial fill ID: {e}")
            self.last_processed_fill_id = 0

        while True:
            try:
                await self._check_for_new_fills()
                await asyncio.sleep(2)  # Check every 2 seconds
            except Exception as e:
                print(f"⚠️ Error in fill monitor: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(5)  # Back off on error

    async def _check_for_new_fills(self):
        """Check database for new SELL fills"""
        try:
            # Update tracked symbols from trading engine
            self.update_tracked_symbols()

            if not self.tracked_symbols:
                return  # No active positions to monitor

            # Debug: Log tracked symbols occasionally (every 30 checks ~ 1 minute)
            if not hasattr(self, '_debug_counter'):
                self._debug_counter = 0
            self._debug_counter += 1
            if self._debug_counter % 30 == 0:
                print(f"🔍 Fill monitor tracking {len(self.tracked_symbols)} symbols: {sorted(list(self.tracked_symbols)[:5])}")

            # Query for new SELL fills for tracked symbols
            # Note: WebSocket listener writes fills with bot_id='unknown', so we need to check both
            with self.db_client.pg_conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        id,
                        symbol,
                        exec_price,
                        exec_qty,
                        exec_time,
                        close_reason,
                        commission
                    FROM trading.fills
                    WHERE bot_id IN (%s, 'unknown')
                      AND side = 'Sell'
                      AND id > %s
                      AND symbol = ANY(%s)
                    ORDER BY id ASC
                """, (self.bot_id, self.last_processed_fill_id, list(self.tracked_symbols)))

                new_fills = cur.fetchall()

            # Process each new SELL fill
            for fill in new_fills:
                fill_id, symbol, exec_price, exec_qty, exec_time, close_reason, commission = fill
                await self._process_sell_fill(
                    fill_id=fill_id,
                    symbol=symbol,
                    exit_price=float(exec_price),
                    close_qty=float(exec_qty),
                    exit_time=exec_time,
                    close_reason=close_reason or 'stop_loss',
                    commission=float(commission or 0)
                )

                # Update last processed ID
                self.last_processed_fill_id = fill_id

        except Exception as e:
            print(f"⚠️ Error checking fills: {e}")
            import traceback
            traceback.print_exc()

    async def _process_sell_fill(
        self,
        fill_id: int,
        symbol: str,
        exit_price: float,
        close_qty: float,
        exit_time: datetime,
        close_reason: str,
        commission: float
    ):
        """Process a SELL fill and log trade closure"""
        try:
            print(f"🔔 Processing SELL fill: {symbol} | {close_qty} @ ${exit_price} | Reason: {close_reason}")

            # Determine which rule_id this closure belongs to
            # Check both active and breakeven trades
            matching_trades = []
            for (trade_symbol, rule_id), trade_data in self.trading_engine.active_trades.items():
                if trade_symbol == symbol:
                    matching_trades.append((rule_id, trade_data, 'active'))
            for (trade_symbol, rule_id), trade_data in self.trading_engine.breakeven_trades.items():
                if trade_symbol == symbol:
                    matching_trades.append((rule_id, trade_data, 'breakeven'))

            if not matching_trades:
                print(f"⚠️ SELL fill for {symbol} but no tracked trade found")
                return

            # Get the side (should be Buy for long positions)
            rule_id, trade_data, trade_type = matching_trades[0]
            side = trade_data.get('side', 'Buy')

            # Log trade closed via alpha integration (this triggers FIFO matching)
            success = self.alpha_integration.log_trade_closed(
                symbol=symbol,
                side=side,  # Original entry side (Buy for longs)
                exit_price=exit_price,
                position_size=close_qty,
                pnl=0.0,  # Will be calculated by FIFO matching
                reason=close_reason,
                rule_id=rule_id
            )

            if success:
                print(f"✅ Trade closure logged: {symbol} ({rule_id}) | Fill ID: {fill_id}")

                # Check if position is fully closed
                with self.db_client.pg_conn.cursor() as cur:
                    cur.execute("""
                        SELECT SUM(remaining_qty) as total_remaining
                        FROM trading.position_entries
                        WHERE bot_id = %s
                          AND symbol = %s
                          AND status != 'closed'
                    """, (self.bot_id, symbol))
                    result = cur.fetchone()
                    remaining_qty = float(result[0]) if result[0] else 0.0

                if remaining_qty == 0:
                    # Position fully closed - remove from bot tracking
                    print(f"🎯 Position fully closed: {symbol}, removing from tracking")
                    self.trading_engine.remove_trade_completely(symbol, rule_id, close_reason)
                else:
                    print(f"📊 Partial close: {remaining_qty} remaining for {symbol}")
            else:
                print(f"❌ Failed to log trade closure for {symbol}")

        except Exception as e:
            print(f"❌ Error processing SELL fill for {symbol}: {e}")
            import traceback
            traceback.print_exc()
