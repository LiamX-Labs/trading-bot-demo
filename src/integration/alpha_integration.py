"""
LXAlgo Strategy - Alpha Infrastructure Integration
Integrates with shared PostgreSQL and Redis services
"""

import sys
import os
from pathlib import Path
import logging
from datetime import datetime
from typing import Dict, Optional

# Add shared library to path
alpha_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(alpha_root))

from shared.alpha_db_client import AlphaDBClient, create_client_order_id

logger = logging.getLogger(__name__)


class LXAlgoAlphaIntegration:
    """
    Integration layer between LXAlgo strategy and Alpha infrastructure.

    Responsibilities:
    - Write all fills to PostgreSQL (trading.fills)
    - Update position state in Redis
    - Track performance metrics
    - Send heartbeats to bot registry
    """

    def __init__(self, bot_id: str = 'lxalgo_001'):
        """
        Initialize integration with Alpha infrastructure.

        Args:
            bot_id: Bot identifier (default: 'lxalgo_001')
        """
        self.bot_id = bot_id
        self.db_client = None
        self._initialize_db_client()

    def _initialize_db_client(self):
        """Initialize database client with retry logic."""
        try:
            # LXAlgo uses Redis DB 1 (per integration spec)
            self.db_client = AlphaDBClient(bot_id=self.bot_id, redis_db=1)
            logger.info(f"✅ Alpha infrastructure integration initialized for {self.bot_id}")
            print(f"✅ Alpha infrastructure integration initialized for {self.bot_id}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Alpha integration: {e}")
            print(f"⚠️ Alpha integration failed: {e}")
            print("⚠️ Strategy will continue without database integration")
            self.db_client = None

    def is_connected(self) -> bool:
        """Check if database integration is active."""
        return self.db_client is not None

    # ========================================
    # TRADE TRACKING (Integrates with trade_tracker)
    # ========================================

    def log_trade_opened(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        position_size: float,
        rule_id: str,
        entry_timestamp: datetime = None
    ) -> bool:
        """
        Log trade entry to PostgreSQL (called when trade opens).

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            side: 'Buy' or 'Sell'
            entry_price: Entry price
            position_size: Position quantity
            rule_id: Trading rule identifier
            entry_timestamp: Entry time (defaults to now)

        Returns:
            True if successful
        """
        if not self.db_client:
            return False

        try:
            if entry_timestamp is None:
                entry_timestamp = datetime.utcnow()

            # Create trade ID from rule and timestamp
            trade_id = f"{self.bot_id}_{symbol}_{rule_id}_{int(entry_timestamp.timestamp())}"

            # Capitalize side for PostgreSQL constraint (Buy/Sell not buy/sell)
            side_capitalized = side.capitalize() if side else side

            # Record entry fill
            self.db_client.write_fill(
                symbol=symbol,
                side=side_capitalized,
                exec_price=entry_price,
                exec_qty=position_size,
                order_id=trade_id,
                client_order_id=create_client_order_id(self.bot_id, 'entry'),
                close_reason='entry',
                commission=0.0,  # Will be updated from actual order
                exec_time=entry_timestamp
            )

            # Update position in Redis
            self.db_client.update_position_redis(
                symbol=symbol,
                size=position_size,
                side=side_capitalized,
                avg_price=entry_price,
                unrealized_pnl=0.0
            )

            logger.info(f"📊 Trade entry logged: {symbol} {side} {position_size} @ {entry_price} (rule: {rule_id})")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to log trade entry: {e}")
            return False

    def log_trade_closed(
        self,
        symbol: str,
        side: str,
        exit_price: float,
        position_size: float,
        pnl: float,
        reason: str,
        rule_id: str = None
    ) -> bool:
        """
        Log trade exit to PostgreSQL (called when trade closes).

        Args:
            symbol: Trading pair
            side: Original entry side ('Buy' or 'Sell')
            exit_price: Exit price
            position_size: Position quantity
            pnl: Profit/loss in USD
            reason: Close reason ('take_profit', 'stop_loss', 'trailing_stop', 'manual', etc.)
            rule_id: Trading rule identifier (optional)

        Returns:
            True if successful
        """
        if not self.db_client:
            return False

        try:
            # Determine exit side (opposite of entry)
            exit_side = 'Sell' if side == 'Buy' else 'Buy'

            # Create trade ID
            trade_id = f"{self.bot_id}_{symbol}_exit_{int(datetime.utcnow().timestamp())}"

            # Record exit fill
            self.db_client.write_fill(
                symbol=symbol,
                side=exit_side,
                exec_price=exit_price,
                exec_qty=position_size,
                order_id=trade_id,
                client_order_id=create_client_order_id(self.bot_id, reason),
                close_reason=reason,
                commission=0.0,  # Will be updated from actual order
                exec_time=datetime.utcnow()
            )

            # Update position to flat in Redis
            self.db_client.update_position_redis(
                symbol=symbol,
                size=0.0,
                side='None',
                avg_price=0.0,
                unrealized_pnl=0.0
            )

            logger.info(f"📊 Trade exit logged: {symbol} PnL: ${pnl:.2f} - {reason}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to log trade exit: {e}")
            return False

    # ========================================
    # POSITION MANAGEMENT
    # ========================================

    def update_position(
        self,
        symbol: str,
        size: float,
        side: str = None,
        avg_price: float = None,
        unrealized_pnl: float = None
    ):
        """
        Update position state in Redis.

        Args:
            symbol: Trading pair
            size: Position size (0 = flat)
            side: 'Buy' (long), 'Sell' (short), or None
            avg_price: Average entry price
            unrealized_pnl: Current unrealized P&L
        """
        if not self.db_client:
            return

        try:
            self.db_client.update_position_redis(
                symbol=symbol,
                size=size,
                side=side,
                avg_price=avg_price,
                unrealized_pnl=unrealized_pnl
            )

            logger.debug(f"📊 Redis position updated: {symbol} = {size}")

        except Exception as e:
            logger.error(f"❌ Failed to update Redis position: {e}")

    def get_position(self, symbol: str) -> Optional[Dict]:
        """
        Get current position from Redis.

        Args:
            symbol: Trading pair

        Returns:
            Position dict or None
        """
        if not self.db_client:
            return None

        try:
            return self.db_client.get_position_redis(symbol)
        except Exception as e:
            logger.error(f"❌ Failed to get Redis position: {e}")
            return None

    # ========================================
    # HEARTBEAT & STATUS
    # ========================================

    def send_heartbeat(self):
        """Send heartbeat to bot registry."""
        if not self.db_client:
            return

        try:
            self.db_client.update_heartbeat()
            logger.debug(f"💓 Heartbeat sent for {self.bot_id}")
        except Exception as e:
            logger.debug(f"Failed to send heartbeat: {e}")

    def update_equity(self, equity: float):
        """Update current equity in bot registry."""
        if not self.db_client:
            return

        try:
            self.db_client.update_equity(equity)
            logger.debug(f"💰 Equity updated: ${equity:,.2f}")
        except Exception as e:
            logger.debug(f"Failed to update equity: {e}")

    # ========================================
    # PERFORMANCE QUERIES
    # ========================================

    def get_daily_pnl(self, days: int = 1) -> float:
        """Get P&L for last N days."""
        if not self.db_client:
            return 0.0

        try:
            return self.db_client.get_daily_pnl(days)
        except:
            return 0.0

    def get_trade_count_today(self) -> int:
        """Get number of trades today."""
        if not self.db_client:
            return 0

        try:
            return self.db_client.get_trade_count_today()
        except:
            return 0

    # ========================================
    # CLEANUP
    # ========================================

    def close(self):
        """Close database connections."""
        if self.db_client:
            try:
                self.db_client.close()
                logger.info(f"Alpha integration closed for {self.bot_id}")
            except:
                pass


# Singleton instance for easy import
_integration = None


def get_integration(bot_id: str = 'lxalgo_001') -> LXAlgoAlphaIntegration:
    """
    Get singleton integration instance.

    Args:
        bot_id: Bot identifier

    Returns:
        LXAlgoAlphaIntegration instance
    """
    global _integration
    if _integration is None:
        _integration = LXAlgoAlphaIntegration(bot_id=bot_id)
    return _integration
