"""
Configuration settings for the CFT Prop trading bot.
All configuration parameters are centralized here.
"""

import os
from pathlib import Path

# Try to load dotenv if available, otherwise use environment variables directly
try:
    from dotenv import load_dotenv
    # Load environment variables from .env in project root
    env_path = Path(__file__).parent.parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)
except ImportError:
    # dotenv not available, use environment variables directly
    print("📋 Using environment variables directly (dotenv not installed)")
    pass


class APIConfig:
    """Bybit API configuration"""
    USE_DEMO = os.getenv("BYBIT_USE_DEMO", "false").lower() == "true"
    BASE_URL = "https://api-demo.bybit.com" if USE_DEMO else "https://api.bybit.com"
    WS_URL = "wss://stream.bybit.com/v5/public/linear"
    
    API_KEY = os.getenv("BYBIT_API_KEY")
    API_SECRET = os.getenv("BYBIT_API_SECRET")
    RECV_WINDOW = "10000"


class TradingConfig:
    """Trading strategy parameters"""
    # Symbol filtering
    VOLUME_FILTER_USD = 10_000_000  # 10M minimum volume
    
    # Signal detection
    PUMP_LOOKBACK = 12  # 1 hour = 12 periods of 5min bars
    PUMP_THRESHOLD = 1  # 1% price increase threshold (updated by user)
    
    # Position sizing
    BASE_POSITION_SIZE_USD = 200
    MAX_ACTIVE_TRADES = 20
    
    # Risk management
    STOPLOSS_PERCENT = 8
    TAKEPROFIT_PERCENT = 30  # 30% take profit target
    TRAIL_ACTIVATION_PERCENT = 20
    TRAIL_OFFSET_PERCENT = 10
    BREAKEVEN_THRESHOLD = 8.0
    
    # Time limits
    TRADE_EXPIRY_HOURS = 72
    NEGATIVE_PNL_CLOSE_HOURS = 8
    COOLDOWN_INTERVAL_HOURS = 4  # 4h cooldown from 3am UTC


class DataConfig:
    """Data processing configuration"""
    TIMEFRAME = "5"  # 5-minute bars
    HISTORY_LIMIT = 200  # Number of bars to fetch
    HISTORY_BUFFER_SIZE = 200  # Deque max length
    MIN_DATA_BARS = 150  # Minimum bars needed for indicators
    
    # Indicator periods (converted for 5min bars)
    RSI_PERIOD = 84  # 7 hours
    VOLATILITY_PERIOD = 144  # 12 hours  
    PRICE_CHANGE_PERIOD = 144  # 12 hours
    VOLUME_CHANGE_PERIOD = 144  # 12 hours


class SystemConfig:
    """System performance configuration"""
    # Symbol management
    SYMBOL_REFRESH_INTERVAL = 4 * 3600  # 4 hours in seconds
    
    # WebSocket settings
    WS_RECONNECT_DELAY = 5
    
    # HTTP client settings
    HTTP_CONNECTION_LIMIT = 20
    HTTP_CONNECTION_LIMIT_PER_HOST = 10
    HTTP_TIMEOUT = 5
    CONCURRENT_REQUESTS = 8
    
    # Monitor intervals
    BALANCE_CHECK_INTERVAL = 180  # 3 minutes
    PNL_CHECK_INTERVAL = 5  # 5 seconds
    BREAKEVEN_CHECK_INTERVAL = 120  # 2 minutes
    RECONCILIATION_CHECK_INTERVAL = 180  # 3 minutes
    NEGATIVE_PNL_CHECK_INTERVAL = 180  # 3 minutes
    MEMORY_CLEANUP_INTERVAL = 3600  # 1 hour
    MARKET_DIAGNOSTIC_INTERVAL = 3600  # 1 hour
    
    # Watchdog
    WATCHDOG_CHECK_INTERVAL = 10
    WATCHDOG_TIMEOUT = 60


class TelegramConfig:
    """Telegram notification configuration"""
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


# Global configuration instances
api_config = APIConfig()
trading_config = TradingConfig()
data_config = DataConfig()
system_config = SystemConfig()
telegram_config = TelegramConfig()
