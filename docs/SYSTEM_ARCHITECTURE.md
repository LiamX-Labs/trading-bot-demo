# CFT Prop Trading System - Architecture & Functionality

**Last Updated:** October 13, 2025
**System Version:** 2.0 (Modular Architecture)

---

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Core Components](#core-components)
4. [Trading Flow](#trading-flow)
5. [Risk Management](#risk-management)
6. [Performance Analysis](#performance-analysis)
7. [Configuration](#configuration)
8. [Deployment](#deployment)

---

## System Overview

### Purpose
The CFT Prop Trading System is an automated cryptocurrency trading bot designed for prop trading accounts on Bybit exchange. It implements a multi-rule signal generation strategy with sophisticated risk management, breakeven logic, and comprehensive performance tracking.

### Key Characteristics
- **Exchange:** Bybit (Linear Perpetual Futures)
- **Strategy:** Multi-rule technical analysis with 8 different signal patterns
- **Risk Approach:** Conservative with multiple protective layers
- **Execution:** Asynchronous, event-driven architecture
- **Monitoring:** Real-time Telegram notifications and detailed logging

---

## Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────┐
│                    CFT Prop Trading Bot                      │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐   ┌──────────────┐
│  WebSocket   │    │   Trading    │   │    Risk      │
│  Data Feed   │───▶│   Engine     │◀──│  Manager     │
└──────────────┘    └──────────────┘   └──────────────┘
        │                   │                   │
        │                   ▼                   │
        │           ┌──────────────┐            │
        │           │    Order     │            │
        └──────────▶│   Manager    │◀───────────┘
                    └──────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐   ┌──────────────┐
│   Telegram   │    │   System     │   │    Trade     │
│   Alerts     │    │   Logger     │   │   Tracker    │
└──────────────┘    └──────────────┘   └──────────────┘
```

### Directory Structure

```
cftprop/
├── src/                          # New modular architecture
│   ├── core/                     # Core trading engine
│   │   └── trading_engine.py    # Main trading logic
│   ├── data/                     # Market data handling
│   │   ├── websocket.py         # Real-time price feed
│   │   ├── market_data.py       # Market data manager
│   │   └── indicators.py        # Technical indicators
│   ├── trading/                  # Trade execution
│   │   └── executor.py          # Order execution logic
│   ├── config/                   # Configuration
│   │   ├── settings.py          # Settings management
│   │   └── bridge.py            # Legacy bridge
│   ├── utils/                    # Utilities
│   │   └── helpers.py           # Helper functions
│   └── main.py                   # Entry point
│
├── performance_analysis/         # Performance analytics
│   └── analyze_performance.py   # Trade analysis script
│
├── main.py                       # Main entry point (wrapper)
├── settings.py                   # Configuration settings
├── order_manager.py              # Order management
├── risk_manager.py               # Risk control
├── trade_tracker.py              # Trade tracking
├── telegram_alerts.py            # Notifications
├── system_logger.py              # Logging system
├── async_trade_processor.py     # Async processing
│
├── logs/                         # Daily log files
├── docs/                         # Documentation
│   └── performance_reports/     # Performance reports
├── .env                          # Environment variables
└── requirements.txt              # Python dependencies
```

---

## Core Components

### 1. Trading Engine (`src/core/trading_engine.py`)

**Purpose:** Central orchestrator for all trading operations

**Key Responsibilities:**
- Signal generation from 8 different trading rules
- Position sizing and order creation
- Breakeven management (moves stop-loss to entry + commission)
- Negative P&L monitoring (closes trades open >8 hours with losses)
- Position reconciliation with exchange
- Cooldown management (4-hour intervals per symbol)

**Signal Rules:**
1. **Rule 1:** Death Cross + RSI Oversold (Short)
2. **Rule 2:** Golden Cross + RSI Overbought (Long)
3. **Rule 3:** RSI Extreme Oversold Bounce (Long)
4. **Rule 4:** RSI Extreme Overbought Reversal (Short)
5. **Rule 5:** Bollinger Band Lower Touch (Long)
6. **Rule 6:** Bollinger Band Upper Touch (Short)
7. **Rule 7:** MACD Bullish Crossover + Positive Histogram (Long)
8. **Rule 8:** MACD Bearish Crossover + Negative Histogram (Short)

### 2. WebSocket Data Feed (`src/data/websocket.py`)

**Purpose:** Real-time market data streaming

**Features:**
- Subscribes to kline (candlestick) updates for all monitored symbols
- Handles reconnection with exponential backoff
- Provides cleaned, validated price data to trading engine
- Supports multiple symbols simultaneously

**Data Flow:**
```
Bybit WebSocket → Parse & Validate → Update Internal State → Notify Trading Engine
```

### 3. Order Manager (`order_manager.py`)

**Purpose:** Handles all order-related operations with Bybit API

**Key Functions:**
- `place_market_order()`: Execute market orders with validation
- `cancel_order()`: Cancel pending orders
- `get_open_orders()`: Fetch current open orders
- `get_closed_pnl()`: Retrieve closed trade P&L data
- Position queries and order status checks

**API Integration:**
- Uses Bybit V5 API
- HMAC SHA256 authentication
- Rate limiting compliance
- Automatic retry logic for transient errors

### 4. Risk Manager (`risk_manager.py`)

**Purpose:** Enforce risk limits and prevent overtrading

**Protection Layers:**

1. **Drawdown Protection (Two-Tier)**
   - **Unrealized Drawdown:** Monitors open position P&L
   - **Daily Balance Drawdown:** Tracks account balance changes from start of day
   - Closes all positions if either threshold breached

2. **Position Limits**
   - Maximum active trades (default: 30)
   - Per-symbol cooldown periods (4 hours)
   - Prevents overexposure to single symbol

3. **Time-Based Rules**
   - 8-hour negative P&L rule (closes losing trades)
   - Daily reset at midnight UTC

4. **Emergency Controls**
   - Manual override capability
   - Automatic trading pause on critical errors

### 5. Trade Tracker (`trade_tracker.py`)

**Purpose:** Maintain complete trade history and state

**Features:**
- Logs every trade lifecycle event
- Tracks entry/exit prices, P&L, duration
- Persists trade data to JSON files
- Provides historical analysis data
- Symbol cooldown enforcement

**Data Structure:**
```python
{
    "trade_id": "unique_id",
    "symbol": "BTCUSDT",
    "side": "Buy",
    "entry_price": 45000.0,
    "exit_price": 46000.0,
    "quantity": 0.01,
    "pnl": 10.0,
    "entry_time": "2025-10-13T12:00:00Z",
    "exit_time": "2025-10-13T14:30:00Z",
    "rule": "Rule 1: Death Cross + RSI Oversold",
    "status": "closed"
}
```

### 6. System Logger (`system_logger.py`)

**Purpose:** Comprehensive logging with daily rotation

**Log Levels:**
- **DEBUG:** Detailed diagnostic information
- **INFO:** General informational messages
- **WARNING:** Warning messages (potential issues)
- **ERROR:** Error messages (operation failures)
- **CRITICAL:** Critical errors (system failures)

**Log Format:**
```
2025-10-13 21:30:45 [INFO] [order_manager] Market order placed: BTCUSDT Buy 0.01
2025-10-13 21:30:46 [INFO] [trade_tracker] New trade recorded: trade_id_12345
2025-10-13 21:35:20 [WARNING] [risk_manager] Approaching drawdown limit: -4.5%
```

### 7. Telegram Alerts (`telegram_alerts.py`)

**Purpose:** Real-time notifications to user

**Notification Types:**
- Trade entries (with rule, price, size)
- Trade exits (with P&L, duration)
- Risk alerts (drawdown warnings, limit hits)
- System events (startup, shutdown, errors)
- Daily summaries (P&L, win rate, trade count)

**Message Format:**
```
🔔 Trade Entry - BTCUSDT
📊 Rule: Golden Cross + RSI
💰 Price: $45,000
📈 Size: 0.01 BTC ($450)
⏰ Time: 2025-10-13 21:30:45 UTC
```

### 8. Performance Analyzer (`performance_analysis/analyze_performance.py`)

**Purpose:** Post-trade analysis and reporting

**Features:**
- Fetches closed trade data from Bybit API
- Calculates 30+ performance metrics
- Generates visual reports (equity curve, drawdown, distribution)
- Creates PDF and JSON reports
- Sends summary to Telegram

**Metrics Calculated:**
- Win rate, profit factor, expectancy
- Sharpe ratio, recovery factor
- Average win/loss, largest win/loss
- Max drawdown, max consecutive wins/losses
- Trades per day, average duration
- Best/worst trading days

**Usage:**
```bash
# Analyze last month
python performance_analysis/analyze_performance.py --period 1m --initial-balance 5000

# Custom date range
python performance_analysis/analyze_performance.py --period 2025-09-05:2025-10-13 --initial-balance 5000

# Skip Telegram notification
python performance_analysis/analyze_performance.py --period 1m --no-telegram
```

---

## Trading Flow

### Complete Trade Lifecycle

```
1. Market Data Received (WebSocket)
   │
   ├─▶ Technical Indicators Calculated
   │   │
   │   └─▶ 8 Trading Rules Evaluated
   │
2. Signal Generated
   │
   ├─▶ Risk Checks (Drawdown, Position Limits, Cooldown)
   │   │
   │   └─▶ If PASS: Continue | If FAIL: Ignore Signal
   │
3. Order Preparation
   │
   ├─▶ Calculate Position Size (based on BASE_POSITION_SIZE_USD)
   │   │
   │   └─▶ Determine Entry Price
   │
4. Order Execution
   │
   ├─▶ Place Market Order via API
   │   │
   │   └─▶ Confirm Fill & Record Trade
   │
5. Position Monitoring (Active Trade)
   │
   ├─▶ Breakeven Check (every 2 minutes)
   │   │   - If price moved 8 USD in profit: Move SL to breakeven
   │   │
   ├─▶ Negative P&L Check (continuous)
   │   │   - If open >8 hours AND losing: Close position
   │   │
   └─▶ Risk Monitoring (continuous)
       │   - Check drawdown limits
       │   - Monitor position count
       │
6. Exit Trigger
   │
   ├─▶ Stop-Loss Hit (breakeven or original)
   │   │
   ├─▶ Take-Profit Hit
   │   │
   ├─▶ Negative P&L Rule Triggered
   │   │
   └─▶ Risk Manager Emergency Close
       │
7. Trade Closure
   │
   ├─▶ Record P&L, Duration, Exit Reason
   │   │
   ├─▶ Update Trade Tracker
   │   │
   ├─▶ Apply Symbol Cooldown (4 hours)
   │   │
   └─▶ Send Telegram Notification
```

### Example: Successful Long Trade

```
12:00:00 - BTCUSDT price drops to $44,500
12:00:05 - Rule 3 (RSI Extreme Oversold) triggers
12:00:10 - Risk checks pass (no cooldown, under position limit)
12:00:15 - Calculate size: $150 / $44,500 = 0.00337 BTC
12:00:20 - Place market buy order for 0.00337 BTC
12:00:25 - Order filled at $44,505 (avg entry)
12:00:30 - Set stop-loss at $44,300 (0.46% below entry)
12:00:35 - Record trade in tracker, send Telegram alert

12:15:00 - Price rises to $44,530 (+$0.84 profit, 0.56%)
12:15:05 - Breakeven check: Not yet (need $8+ profit)

13:45:00 - Price rises to $44,590 (+$2.86 profit, 1.9%)
13:45:05 - Breakeven check: Not yet (need $8+ profit)

15:20:00 - Price rises to $44,700 (+$6.57 profit, 4.4%)
15:20:05 - Breakeven check: Not yet (need $8+ profit)

16:30:00 - Price rises to $44,900 (+$13.31 profit, 9.8%)
16:30:05 - Breakeven threshold met! Move SL to $44,510 (breakeven + commission)

17:45:00 - Price hits $45,200, then reverses
18:00:00 - Stop-loss hit at $44,510
18:00:05 - Position closed, P&L: +$1.68 (+0.11%)
18:00:10 - Record exit, send Telegram alert
18:00:15 - Apply 4-hour cooldown to BTCUSDT (until 22:00:00)
```

---

## Risk Management

### Multi-Layer Protection System

#### Layer 1: Pre-Trade Validation
- **Position Limit Check:** Ensures max active trades not exceeded
- **Cooldown Check:** Prevents trading same symbol within 4 hours
- **Drawdown Check:** Blocks new trades if account in drawdown
- **Balance Validation:** Ensures sufficient margin available

#### Layer 2: Trade Execution
- **Order Size Validation:** Verifies minimum order requirements
- **Price Sanity Check:** Detects abnormal price movements
- **API Response Validation:** Confirms order acceptance
- **Slippage Protection:** Monitors execution quality

#### Layer 3: Active Position Monitoring
- **Breakeven Management:**
  - Threshold: $8 USD profit per position
  - Action: Move stop-loss to entry + commission cost
  - Check Interval: Every 120 seconds

- **Negative P&L Rule:**
  - Condition: Position open >8 hours AND losing money
  - Action: Close position immediately
  - Reason: Prevent holding losing trades indefinitely

- **Real-Time Drawdown Monitoring:**
  - Unrealized Drawdown: Sum of all open position P&L
  - Daily Balance Drawdown: Account balance vs. start-of-day
  - Threshold: Configurable (default: -5%)

#### Layer 4: Emergency Controls
- **Global Position Closure:** Close all positions on critical risk breach
- **Trading Pause:** Temporarily halt new trade entries
- **Manual Override:** Telegram commands for emergency control

### Drawdown Calculation

```python
# Unrealized Drawdown
unrealized_pnl = sum(position.unrealized_pnl for position in open_positions)
unrealized_drawdown_pct = (unrealized_pnl / account_balance) * 100

# Daily Balance Drawdown
daily_start_balance = get_balance_at_midnight_utc()
current_balance = get_current_balance()
daily_drawdown_pct = ((current_balance - daily_start_balance) / daily_start_balance) * 100

# Risk Action
if unrealized_drawdown_pct <= -5.0 or daily_drawdown_pct <= -5.0:
    close_all_positions()
    pause_trading()
    send_alert("DRAWDOWN LIMIT BREACHED")
```

### Cooldown System

**Purpose:** Prevent overtrading and give markets time to develop

**Mechanics:**
- Symbol-level cooldown (not account-wide)
- Duration: 4 hours (configurable)
- Starts: From 00:00 UTC, 04:00 UTC, 08:00 UTC, etc.
- Cleanup: Automatic removal of expired cooldowns

**Example:**
```
12:15:00 - Enter BTCUSDT Long
12:15:05 - Apply cooldown to BTCUSDT until 16:00:00
14:30:00 - BTCUSDT signal triggers → BLOCKED (cooldown active)
16:00:01 - BTCUSDT cooldown expires
16:15:00 - BTCUSDT signal triggers → ALLOWED
```

---

## Performance Analysis

### Analysis System Architecture

```
Bybit API (Closed P&L Endpoint)
         │
         ▼
┌─────────────────────┐
│  Data Collection    │
│  - Fetch trades     │
│  - Handle pagination│
│  - Date chunking    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Data Processing    │
│  - Clean data       │
│  - Sort by time     │
│  - Calculate metrics│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Analysis Engine    │
│  - Performance KPIs │
│  - Risk metrics     │
│  - Statistical data │
└──────────┬──────────┘
           │
           ├─────────────────┐
           │                 │
           ▼                 ▼
┌─────────────────┐  ┌──────────────┐
│ Chart Generator │  │    Reports   │
│ - Equity curve  │  │ - JSON       │
│ - Drawdown      │  │ - PDF        │
│ - Distribution  │  │ - Telegram   │
│ - Cumulative P&L│  │              │
└─────────────────┘  └──────────────┘
```

### Key Performance Metrics

**Profitability Metrics:**
- Net Profit: Total realized P&L
- Total Return: Profit as % of initial balance
- Gross Profit: Sum of winning trades
- Gross Loss: Sum of losing trades
- Profit Factor: Gross Profit / Gross Loss

**Efficiency Metrics:**
- Win Rate: % of winning trades
- Average Win: Mean profit of winning trades
- Average Loss: Mean loss of losing trades
- Expectancy: Expected profit per trade
- Risk/Reward Ratio: Avg Win / Avg Loss

**Risk Metrics:**
- Max Drawdown: Largest peak-to-trough decline
- Max Drawdown %: Drawdown as % of peak balance
- Recovery Factor: Net Profit / Max Drawdown
- Sharpe Ratio: Risk-adjusted return metric

**Activity Metrics:**
- Total Trades: Number of completed trades
- Trades/Day: Average trading frequency
- Avg Duration: Mean time in trade
- Max Consecutive Wins/Losses: Longest streaks

### Report Generation

**Charts Created:**
1. **Equity Curve:** Account balance over time
2. **Drawdown Chart:** Underwater equity visualization
3. **Win/Loss Distribution:** Histogram of trade outcomes
4. **Cumulative P&L:** Running profit/loss over time

**Report Formats:**
- **JSON:** Machine-readable, detailed metrics
- **PDF:** Professional report with charts and tables
- **Telegram:** Quick summary for mobile viewing

---

## Configuration

### Environment Variables (.env)

```bash
# Bybit API Credentials
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_api_secret_here
BYBIT_USE_DEMO=true  # Use testnet (true) or mainnet (false)

# Telegram Notifications
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# API Settings
BYBIT_BASE_URL=https://api-testnet.bybit.com  # Or https://api.bybit.com
RECV_WINDOW=10000
```

### Trading Parameters (settings.py)

```python
# Position Sizing
BASE_POSITION_SIZE_USD = 150  # USD value per trade
MAX_ACTIVE_TRADES = 30        # Maximum concurrent positions

# Breakeven Management
BREAKEVEN_THRESHOLD = 8.0           # USD profit to trigger breakeven
BREAKEVEN_CHECK_INTERVAL = 120      # Seconds between checks
BREAKEVEN_OFFSET_BUFFER = 0.0002    # Extra buffer above entry

# Risk Management
NEGATIVE_PNL_CLOSE_HOURS = 8        # Hours before closing losing trades
UNREALIZED_DRAWDOWN_LIMIT = -5.0    # % unrealized loss limit
DAILY_DRAWDOWN_LIMIT = -5.0         # % daily balance loss limit

# Cooldown System
SYMBOL_COOLDOWN_HOURS = 4           # Hours between trades per symbol
COOLDOWN_START_HOUR = 0             # UTC hour for cooldown intervals

# Technical Indicators
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
RSI_EXTREME_OVERSOLD = 20
RSI_EXTREME_OVERBOUGHT = 80

BBANDS_PERIOD = 20
BBANDS_STD = 2

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

MA_SHORT = 50   # Golden/Death Cross
MA_LONG = 200

# Stop Loss / Take Profit
STOP_LOSS_PERCENT = 0.5    # % below entry for SL
TAKE_PROFIT_PERCENT = 2.0  # % above entry for TP

# Monitoring Intervals
RECONCILIATION_CHECK_INTERVAL = 600  # Seconds between position syncs
WEBSOCKET_RECONNECT_DELAY = 5        # Seconds before reconnect attempt

# Logging
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_DIR = "logs"
LOG_ROTATION = "daily"  # daily, weekly, monthly

# Symbols to Trade
TRADE_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT",
    "DOGEUSDT", "XRPUSDT", "DOTUSDT", "MATICUSDT",
    "AVAXUSDT", "LINKUSDT", "UNIUSDT", "ATOMUSDT",
    "LTCUSDT", "ETCUSDT", "ALGOUSDT", "VETUSDT"
]
```

---

## Deployment

### Production Deployment (AWS EC2 t2.micro)

#### Step 1: Server Setup
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.8+
sudo apt install python3 python3-pip python3-venv -y

# Install system dependencies
sudo apt install git -y
```

#### Step 2: Clone and Setup
```bash
# Clone repository
git clone <your-repo-url> cftprop
cd cftprop

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### Step 3: Configuration
```bash
# Create and configure .env
cp .env.example .env
nano .env  # Edit with your credentials

# Review settings
nano settings.py  # Adjust trading parameters
```

#### Step 4: Testing
```bash
# Run in demo mode first
# Ensure BYBIT_USE_DEMO=true in .env
python main.py

# Monitor logs
tail -f logs/cftprop_$(date +%Y-%m-%d).log
```

#### Step 5: Production Start
```bash
# Use screen or tmux for persistent session
screen -S trading_bot

# Start bot
python main.py

# Detach: Ctrl+A, then D
# Reattach: screen -r trading_bot
```

#### Step 6: Process Management (Optional)
```bash
# Install supervisor
sudo apt install supervisor -y

# Create supervisor config
sudo nano /etc/supervisor/conf.d/trading_bot.conf
```

**Supervisor Config:**
```ini
[program:trading_bot]
directory=/home/ubuntu/cftprop
command=/home/ubuntu/cftprop/venv/bin/python main.py
user=ubuntu
autostart=true
autorestart=true
stderr_logfile=/home/ubuntu/cftprop/logs/supervisor_error.log
stdout_logfile=/home/ubuntu/cftprop/logs/supervisor_output.log
```

```bash
# Start supervisor service
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start trading_bot

# Check status
sudo supervisorctl status trading_bot
```

### Monitoring and Maintenance

#### Daily Tasks
- Review Telegram notifications
- Check daily log files
- Monitor account balance
- Verify position reconciliation

#### Weekly Tasks
- Run performance analysis
- Review trade statistics
- Check for system errors
- Update risk parameters if needed

#### Monthly Tasks
- Full system audit
- Review and optimize parameters
- Backup trade data
- Update dependencies

#### Health Check Commands
```bash
# Check if bot is running
ps aux | grep python

# View recent logs
tail -n 100 logs/cftprop_$(date +%Y-%m-%d).log

# Check active positions
# (Via Bybit web interface or API)

# Run performance analysis
python performance_analysis/analyze_performance.py --period 1m --initial-balance 5000
```

---

## Troubleshooting

### Common Issues

**Issue: Bot not starting**
- Check Python version (3.8+)
- Verify dependencies installed: `pip list`
- Check .env file exists and has correct credentials
- Review error logs in console output

**Issue: No trades executing**
- Verify WebSocket connection (check logs)
- Confirm cooldown periods not blocking all symbols
- Check risk limits not preventing new trades
- Ensure account has sufficient margin

**Issue: Telegram notifications not working**
- Verify bot token and chat ID in .env
- Test with `curl` or Telegram API tester
- Check bot permissions in Telegram
- Review telegram_alerts.py logs

**Issue: Position sync issues**
- Check API credentials and permissions
- Verify network connectivity to Bybit
- Review reconciliation logs
- Manually close positions if necessary

**Issue: High memory usage**
- Check log file sizes (may need cleanup)
- Verify cooldown cleanup running
- Consider reducing TRADE_SYMBOLS list
- Restart bot periodically

---

## Security Best Practices

1. **API Key Security**
   - Never commit .env to version control
   - Use API keys with minimum required permissions
   - Regularly rotate API keys
   - Monitor API usage logs

2. **Access Control**
   - Restrict SSH access to trusted IPs
   - Use SSH keys, not passwords
   - Keep server OS updated
   - Enable firewall (UFW on Ubuntu)

3. **Monitoring**
   - Set up alerts for unusual activity
   - Monitor account balance changes
   - Track API rate limit usage
   - Log all system access

4. **Backup**
   - Regular backup of trade data
   - Save configuration files
   - Document custom modifications
   - Keep offline copy of credentials

---

## Performance Optimization

### For Low-Resource Environments (t2.micro)

1. **Reduce Symbol Count**
   ```python
   TRADE_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]  # Top 3 only
   ```

2. **Increase Check Intervals**
   ```python
   BREAKEVEN_CHECK_INTERVAL = 180  # 3 minutes instead of 2
   RECONCILIATION_CHECK_INTERVAL = 900  # 15 minutes instead of 10
   ```

3. **Log Level Adjustment**
   ```python
   LOG_LEVEL = "WARNING"  # Less verbose logging
   ```

4. **Periodic Restarts**
   ```bash
   # Cron job to restart daily at 00:00 UTC
   0 0 * * * /home/ubuntu/restart_bot.sh
   ```

---

## Conclusion

The CFT Prop Trading System is a sophisticated, production-ready automated trading solution with multiple layers of risk protection, comprehensive monitoring, and detailed performance analytics. It's designed for reliability, maintainability, and profitability in live prop trading environments.

**Key Strengths:**
- Multi-rule signal generation for diverse market conditions
- Conservative risk management with multiple protective layers
- Real-time monitoring and alerting via Telegram
- Detailed performance tracking and analysis
- Modular, maintainable codebase
- Production-tested on AWS infrastructure

**Recommended Use:**
- Start with demo/testnet for at least 2 weeks
- Gradually increase position sizes based on performance
- Regularly review and adjust risk parameters
- Maintain active monitoring during market hours
- Run weekly performance analysis
- Keep detailed records of all modifications

---

**Document Version:** 1.0
**Author:** System Documentation
**Contact:** Via project repository

