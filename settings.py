# settings.py - Comprehensive configuration for CFT Prop Trading Bot

from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment variables from .env in project root
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# ═══════════════════════════════════════════════════════════════════════════════
# API CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Bybit endpoint configuration
USE_DEMO = os.getenv("BYBIT_USE_DEMO", "false").lower() == "true"
BASE_URL = "https://api-demo.bybit.com" if USE_DEMO else "https://api.bybit.com"
WS_URL = "wss://stream.bybit.com/v5/public/linear"

# API credentials & request settings
API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")
RECV_WINDOW = "10000"

# API request settings
API_TIMEOUT_SECONDS = 5
API_MAX_RETRIES = 3
API_RETRY_DELAY = 0.5

# ═══════════════════════════════════════════════════════════════════════════════
# TRADING STRATEGY PARAMETERS
# ═══════════════════════════════════════════════════════════════════════════════

# Signal generation parameters
PUMP_LOOKBACK = 12  # 1 hour = 12 periods of 5min bars
PUMP_THRESHOLD = 8
TIMEFRAME = "5"  # 5-minute timeframe

# Position sizing and risk management
BASE_POSITION_SIZE_USD = 150
MAX_ACTIVE_TRADES = 30

# Stop loss and take profit settings
STOPLOSS_PERCENT = 8
TAKEPROFIT_PERCENT = 30  # 30% take profit target
TRAIL_ACTIVATION_PERCENT = 20
TRAIL_OFFSET_PERCENT = 10

# Breakeven management
BREAKEVEN_THRESHOLD = 8.0  # Profit percentage to trigger breakeven move

# ═══════════════════════════════════════════════════════════════════════════════
# RISK MANAGEMENT PARAMETERS
# ═══════════════════════════════════════════════════════════════════════════════

# Unrealized PnL drawdown settings
UNREALIZED_DRAWDOWN_THRESHOLD = 0.30  # 30% drawdown triggers liquidation
UNREALIZED_ACTIVATION_MULTIPLIER = 2  # Activation at 2x base position size

# Daily balance drawdown settings
DAILY_BALANCE_DRAWDOWN_THRESHOLD = 0.25  # 25% daily drop triggers liquidation

# Trade age limits
TRADE_MAX_AGE_HOURS = 72  # Auto-expire trades after 72 hours
NEGATIVE_PNL_CLOSE_HOURS = 8  # Close negative trades after 8 hours

# ═══════════════════════════════════════════════════════════════════════════════
# COOLDOWN AND RESTRICTION SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

# Cooldown intervals (in hours)
SYMBOL_COOLDOWN_HOURS = 4  # 4-hour cooldown between trades on same symbol
COOLDOWN_START_HOUR_UTC = 0  # Cooldown intervals start from 12am UTC (0:00)

# Cleanup settings
COOLDOWN_CLEANUP_HOURS = 24  # Clean up cooldown records older than 24 hours

# ═══════════════════════════════════════════════════════════════════════════════
# MONITORING AND SYSTEM INTERVALS
# ═══════════════════════════════════════════════════════════════════════════════

# Check intervals (in seconds)
BALANCE_CHECK_INTERVAL = 300  # 5 minutes
PNL_CHECK_INTERVAL = 180  # 3 minutes  
BREAKEVEN_CHECK_INTERVAL = 120  # 2 minutes
RECONCILIATION_CHECK_INTERVAL = 600  # 10 minutes
NEGATIVE_PNL_CHECK_INTERVAL = 1800  # 30 minutes
MEMORY_CLEANUP_INTERVAL = 3600  # 1 hour
WATCHDOG_CHECK_INTERVAL = 60  # 1 minute
MARKET_DIAGNOSTIC_INTERVAL = 1800  # 30 minutes

# Symbol refresh settings
SYMBOL_REFRESH_INTERVAL = 14400  # 4 hours

# System timeouts
WATCHDOG_TIMEOUT = 60  # Watchdog alert if no updates for 60 seconds

# ═══════════════════════════════════════════════════════════════════════════════
# DATA MANAGEMENT SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

# Historical data requirements
MIN_DATA_BARS = 50  # Minimum bars required for analysis
MAX_HISTORY_BARS = 200  # Maximum bars to keep in memory per symbol

# Cache settings
MARKET_INFO_CACHE_TTL = 7200  # Market info cache TTL (2 hours)
MAX_CACHE_SIZE = 50  # Maximum number of symbols in cache

# WebSocket settings
WS_RECONNECT_DELAY = 5  # Seconds to wait before reconnecting
WS_PING_INTERVAL = 20  # WebSocket ping interval

# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Log directory and file settings
LOGS_DIRECTORY = "logs"  # Directory to store log files
LOG_RETENTION_DAYS = 30  # Keep log files for 30 days

# Log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL = "INFO"
CONSOLE_LOG_LEVEL = "INFO"

# Enable/disable console logging
CONSOLE_LOGGING_ENABLED = True

# Log formats
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S UTC"
CONSOLE_LOG_FORMAT = "%(levelname)-8s | %(message)s"

# ═══════════════════════════════════════════════════════════════════════════════
# TELEGRAM NOTIFICATION SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

# Telegram credentials
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Notification settings
BATCH_NOTIFICATION_DELAY = 10  # Seconds to wait before sending batch notifications
MAX_NOTIFICATIONS_PER_BATCH = 5  # Maximum notifications in one batch

# Enable/disable different notification types
NOTIFY_TRADE_EXECUTIONS = True
NOTIFY_TRADE_CLOSURES = True
NOTIFY_RISK_EVENTS = True
NOTIFY_SYSTEM_EVENTS = True
NOTIFY_RECONCILIATION_EVENTS = True

# ═══════════════════════════════════════════════════════════════════════════════
# PERFORMANCE AND OPTIMIZATION SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

# Memory management
MAX_PROCESSED_BARS = 1000  # Maximum processed bars to keep in memory
MAX_PROCESSED_SIGNALS = 1000  # Maximum processed signals to keep in memory

# Connection pooling settings
HTTP_POOL_CONNECTIONS = 5  # Number of connection pools for t2.micro
HTTP_POOL_MAXSIZE = 10  # Maximum pool size for t2.micro

# Request timeout settings
DEFAULT_REQUEST_TIMEOUT = 3  # Default timeout for API requests
POSITION_CHECK_TIMEOUT = 5  # Timeout for position checks

# ═══════════════════════════════════════════════════════════════════════════════
# TESTING AND DEBUG SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

# Debug flags
DEBUG_WEBSOCKET = False
DEBUG_POSITION_RECONCILIATION = True
DEBUG_BREAKEVEN_MOVES = True
DEBUG_COOLDOWN_CHECKS = False

# Test mode settings
TEST_MODE = False  # Enable test mode (paper trading)
TEST_POSITION_SIZE_USD = 10  # Smaller position size for testing

# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def validate_settings():
    """Validate critical settings and raise errors for invalid configurations"""
    
    # API credentials validation
    if not API_KEY or not API_SECRET:
        raise ValueError("BYBIT_API_KEY and BYBIT_API_SECRET must be set in .env file")
    
    # Telegram validation (if notifications enabled)
    if NOTIFY_TRADE_EXECUTIONS or NOTIFY_TRADE_CLOSURES:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set for notifications")
    
    # Risk management validation
    if UNREALIZED_DRAWDOWN_THRESHOLD <= 0 or UNREALIZED_DRAWDOWN_THRESHOLD >= 1:
        raise ValueError("UNREALIZED_DRAWDOWN_THRESHOLD must be between 0 and 1")
    
    if DAILY_BALANCE_DRAWDOWN_THRESHOLD <= 0 or DAILY_BALANCE_DRAWDOWN_THRESHOLD >= 1:
        raise ValueError("DAILY_BALANCE_DRAWDOWN_THRESHOLD must be between 0 and 1")
    
    # Position size validation
    if BASE_POSITION_SIZE_USD <= 0:
        raise ValueError("BASE_POSITION_SIZE_USD must be positive")
    
    # Cooldown validation
    if SYMBOL_COOLDOWN_HOURS <= 0:
        raise ValueError("SYMBOL_COOLDOWN_HOURS must be positive")
    
    if COOLDOWN_START_HOUR_UTC < 0 or COOLDOWN_START_HOUR_UTC >= 24:
        raise ValueError("COOLDOWN_START_HOUR_UTC must be between 0 and 23")

# Run validation on import
validate_settings()