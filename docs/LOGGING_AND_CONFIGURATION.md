# CFT Prop Bot - Logging & Configuration System

## Overview

This document describes the comprehensive logging system and configuration management implemented for the CFT Prop Trading Bot.

## 🗂️ System Logging

### Daily Log Files
- **Location**: `logs/` directory
- **Format**: `cftprop_YYYY-MM-DD.log`
- **Rotation**: Automatic daily rotation at 12:00 AM UTC
- **Retention**: Configurable (default: 30 days)

### Log Levels
- **DEBUG**: Detailed diagnostic information
- **INFO**: General operational messages
- **WARNING**: Important events that need attention
- **ERROR**: Error conditions that don't stop the bot
- **CRITICAL**: Serious errors that may cause the bot to stop

### Specialized Logging Methods

```python
from system_logger import system_logger

# Trading events
system_logger.log_trade_signal("BTCUSDT", "Rule 6", 45000.0)
system_logger.log_trade_execution("BTCUSDT", "Rule 6", 45000.0, 0.003, True)
system_logger.log_trade_closure("BTCUSDT", "Rule 6", "take_profit", 150.50)
system_logger.log_breakeven_move("BTCUSDT", "Rule 6", True)

# Risk management
system_logger.log_risk_event("drawdown", "30% unrealized drawdown", ["BTCUSDT"])

# System events
system_logger.log_system_event("startup", "Bot started successfully")
system_logger.log_api_error("/v5/position/list", 10001, "Invalid signature")

# Position reconciliation
system_logger.log_reconciliation(5, 3, ["ETHUSDT", "ADAUSDT"])

# Cooldown events
system_logger.log_cooldown_event("BTCUSDT", False, "2024-01-01 04:00:00")
```

## ⏰ 4-Hour Cooldown System

### Interval Calculation
- **Start Time**: 12:00 AM UTC (00:00)
- **Intervals**: 
  - 00:00 - 04:00
  - 04:00 - 08:00  
  - 08:00 - 12:00
  - 12:00 - 16:00
  - 16:00 - 20:00
  - 20:00 - 00:00

### Usage
```python
from src.utils.helpers import TradingRestrictions

restrictions = TradingRestrictions()

# Check if symbol can be traded
if restrictions.can_trade_symbol("BTCUSDT"):
    # Execute trade
    restrictions.record_trade_for_symbol("BTCUSDT")

# Get next available trade time
next_time = restrictions.get_next_trade_time("BTCUSDT")
```

## ⚙️ Configuration System (settings.py)

### API Configuration
```python
# Bybit API settings
USE_DEMO = True/False
API_KEY = "your_api_key"
API_SECRET = "your_api_secret"
RECV_WINDOW = "10000"
API_TIMEOUT_SECONDS = 5
API_MAX_RETRIES = 3
```

### Trading Strategy Parameters
```python
# Position sizing
BASE_POSITION_SIZE_USD = 150
MAX_ACTIVE_TRADES = 30

# Risk management
STOPLOSS_PERCENT = 8
TAKEPROFIT_PERCENT = 30
BREAKEVEN_THRESHOLD = 8.0

# Signal generation
PUMP_LOOKBACK = 12
PUMP_THRESHOLD = 8
TIMEFRAME = "5"
```

### Risk Management Settings
```python
# Drawdown limits
UNREALIZED_DRAWDOWN_THRESHOLD = 0.30  # 30%
DAILY_BALANCE_DRAWDOWN_THRESHOLD = 0.25  # 25%

# Trade age limits
TRADE_MAX_AGE_HOURS = 72  # Auto-expire after 72h
NEGATIVE_PNL_CLOSE_HOURS = 8  # Close negative trades after 8h
```

### Cooldown Configuration
```python
# Cooldown intervals
SYMBOL_COOLDOWN_HOURS = 4  # 4-hour cooldown
COOLDOWN_START_HOUR_UTC = 0  # Start from 12am UTC
COOLDOWN_CLEANUP_HOURS = 24  # Cleanup old records
```

### Monitoring Intervals
```python
# Check intervals (seconds)
BALANCE_CHECK_INTERVAL = 300  # 5 minutes
PNL_CHECK_INTERVAL = 180  # 3 minutes
BREAKEVEN_CHECK_INTERVAL = 120  # 2 minutes
RECONCILIATION_CHECK_INTERVAL = 600  # 10 minutes
NEGATIVE_PNL_CHECK_INTERVAL = 1800  # 30 minutes
```

### Logging Configuration
```python
# Log settings
LOGS_DIRECTORY = "logs"
LOG_RETENTION_DAYS = 30
LOG_LEVEL = "INFO"
CONSOLE_LOGGING_ENABLED = True

# Log formats
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(message)s"
CONSOLE_LOG_FORMAT = "%(levelname)-8s | %(message)s"
```

### Telegram Notifications
```python
# Telegram settings
TELEGRAM_BOT_TOKEN = "your_bot_token"
TELEGRAM_CHAT_ID = "your_chat_id"

# Notification controls
NOTIFY_TRADE_EXECUTIONS = True
NOTIFY_TRADE_CLOSURES = True
NOTIFY_RISK_EVENTS = True
NOTIFY_SYSTEM_EVENTS = True
```

### Performance Settings
```python
# Memory management
MAX_PROCESSED_BARS = 1000
MAX_PROCESSED_SIGNALS = 1000
HTTP_POOL_CONNECTIONS = 5
HTTP_POOL_MAXSIZE = 10

# Timeouts
DEFAULT_REQUEST_TIMEOUT = 3
POSITION_CHECK_TIMEOUT = 5
```

### Debug Settings
```python
# Debug flags
DEBUG_WEBSOCKET = False
DEBUG_POSITION_RECONCILIATION = True
DEBUG_BREAKEVEN_MOVES = True
DEBUG_COOLDOWN_CHECKS = False

# Test mode
TEST_MODE = False
TEST_POSITION_SIZE_USD = 10
```

## 🔧 Configuration Validation

The system automatically validates critical settings on startup:

- API credentials must be provided
- Telegram tokens required if notifications enabled
- Drawdown thresholds must be between 0 and 1
- Position sizes must be positive
- Cooldown hours must be positive

## 📁 Log File Structure

Example log entry:
```
2024-01-01 12:34:56 UTC | INFO     | [12:34:56.123] TRADE SUCCESS: BTCUSDT (Rule 6) - Qty: 0.003 @ 45000.000000 [symbol=BTCUSDT, rule_id=Rule 6, price=45000.0, quantity=0.003, event_type=execution, success=True]
```

## 🔄 Automatic Maintenance

### Log Cleanup
- Runs daily at 24-hour intervals
- Removes logs older than `LOG_RETENTION_DAYS`
- Automatically logged when cleanup occurs

### Memory Cleanup
- Cooldown records cleaned every hour
- Removes records older than `COOLDOWN_CLEANUP_HOURS`
- Market data cache management
- Python garbage collection

## 🚨 Important Features

### Position Reconciliation
- Detects externally closed positions
- Automatically removes from tracking
- Logs all reconciliation events
- Sends Telegram notifications

### 8-Hour Negative PnL Monitoring
- Checks trades older than 8 hours
- Closes positions with negative PnL
- Logs closure with PnL amount
- Removes from active tracking

### Enhanced Error Handling
- All exceptions logged with context
- API errors logged with endpoint details
- WebSocket events logged for debugging
- Graceful degradation on failures

## 📋 Quick Setup Checklist

1. **Environment Variables** (`.env` file):
   ```
   BYBIT_API_KEY=your_api_key
   BYBIT_API_SECRET=your_api_secret
   BYBIT_USE_DEMO=true
   TELEGRAM_BOT_TOKEN=your_bot_token
   TELEGRAM_CHAT_ID=your_chat_id
   ```

2. **Create logs directory**:
   ```bash
   mkdir logs
   ```

3. **Adjust settings** in `settings.py` as needed

4. **Test configuration**:
   ```bash
   python3 test_basic_functionality.py
   ```

## 📊 Monitoring Dashboard

The logging system provides comprehensive monitoring:

- **Trade Activity**: Entry, exit, and breakeven movements
- **Risk Events**: Drawdown alerts and position closures  
- **System Health**: API errors, WebSocket status, memory usage
- **Performance**: Execution times and success rates
- **Configuration**: Settings validation and changes

All events are timestamped in UTC and include relevant context for analysis and debugging.