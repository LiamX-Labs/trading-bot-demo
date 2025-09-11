# CFT Prop Trading Bot - Clean Project Structure

## 📁 Project Organization

```
cftprop/
├── 📄 Core Python Files
│   ├── main.py                     # Legacy main entry point
│   ├── settings.py                 # Comprehensive configuration
│   ├── order_manager.py            # Trade execution and API calls
│   ├── risk_manager.py             # Risk management and breakeven
│   ├── trade_tracker.py            # Trade logging and persistence
│   ├── telegram_alerts.py          # Notification system
│   ├── system_logger.py            # Daily logging system
│   ├── async_trade_processor.py    # Async trade processing
│   ├── database_manager.py         # Database operations
│   └── trading_integration.py      # Trading integration utilities
│
├── 🏗️ Modular Architecture (src/)
│   ├── main.py                     # New modular main entry point
│   ├── config/
│   │   ├── settings.py             # New modular settings
│   │   └── bridge.py               # Legacy settings bridge
│   ├── core/
│   │   └── trading_engine.py       # Core trading engine
│   ├── data/
│   │   ├── market_data.py          # Market data management
│   │   ├── indicators.py           # Technical analysis
│   │   └── websocket.py            # WebSocket connections
│   ├── trading/
│   │   └── executor.py             # Trade execution
│   └── utils/
│       └── helpers.py              # Utility functions and cooldowns
│
├── 📚 Documentation (docs/)
│   ├── README.md                   # Main project documentation
│   ├── PROJECT_STRUCTURE_CLEAN.md  # This file
│   ├── LOGGING_AND_CONFIGURATION.md # Logging system guide
│   ├── BREAKEVEN_AND_CLOSURE_SYSTEM.md # Breakeven system docs
│   ├── RESTRUCTURE_GUIDE.md       # Restructuring information
│   ├── FIXES_APPLIED.md           # Bug fixes documentation
│   ├── ISSUE_RESOLUTION.md        # Issue resolution guide
│   ├── OPTIMIZATION_SUMMARY.md    # Performance optimizations
│   ├── GIT_PUSH_SUMMARY.md        # Git workflow documentation
│   ├── trading_dashboard_setup.md  # Dashboard setup guide
│   └── trading_integration_guide.md # Integration documentation
│
├── 🗃️ Database & Configuration
│   ├── database_setup.sql          # Database schema
│   ├── complete_db_setup.sh        # Database setup script
│   ├── setup_commands.sh           # Environment setup
│   ├── requirements.txt            # Python dependencies
│   ├── .env                        # Environment variables
│   └── .gitignore                  # Git ignore rules
│
├── 🐳 Deployment
│   ├── Dockerfile                  # Container configuration
│   ├── docker-compose.yml          # Multi-container setup
│   └── logs/                       # Daily log files
│
├── 📦 Backup & Archive
│   └── original_backup/            # Original file versions
│
└── 🔧 Development Environment
    └── venv/                       # Python virtual environment
```

## 🚀 Entry Points

### Primary Entry Point (Modular)
```bash
python src/main.py
```
- Uses new modular architecture
- Enhanced logging and monitoring
- Improved breakeven tracking
- Better error handling

### Legacy Entry Point
```bash
python main.py
```
- Original implementation
- Maintained for compatibility
- Simpler structure

## 📋 Key Features by File

### Core System Files

| File | Purpose | Key Features |
|------|---------|--------------|
| **settings.py** | Configuration | All adjustable parameters, validation |
| **system_logger.py** | Logging | Daily rotation, specialized trade logging |
| **order_manager.py** | Trading | API calls, position management, reconciliation |
| **risk_manager.py** | Risk Control | Breakeven moves, drawdown monitoring |
| **trade_tracker.py** | Persistence | Trade history, JSON logging |

### Modular Architecture (src/)

| Directory | Purpose | Components |
|-----------|---------|------------|
| **core/** | Trading Engine | Main trading logic, position tracking |
| **data/** | Market Data | WebSocket, indicators, data management |
| **trading/** | Execution | Trade execution, order management |
| **utils/** | Utilities | Cooldowns, helpers, restrictions |
| **config/** | Configuration | Settings management, validation |

## 🔧 Configuration Files

### Environment Variables (.env)
```bash
BYBIT_API_KEY=your_api_key
BYBIT_API_SECRET=your_secret
BYBIT_USE_DEMO=true
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Main Configuration (settings.py)
- **API Settings**: Endpoints, timeouts, retries
- **Trading Parameters**: Position sizing, risk limits
- **Monitoring Intervals**: Check frequencies
- **Logging Configuration**: Levels, formats, retention
- **Cooldown Settings**: Intervals, cleanup periods

## 📊 Logging System

### Daily Log Files
- **Location**: `logs/cftprop_YYYY-MM-DD.log`
- **Rotation**: Automatic at 12:00 AM UTC
- **Retention**: Configurable (default: 30 days)
- **Types**: Trade events, system status, API errors

### Log Categories
- **TRADE**: Entry, exit, breakeven moves
- **RISK**: Drawdown alerts, position closures
- **SYSTEM**: Startup, shutdown, errors
- **API**: Request errors, timeouts
- **RECONCILIATION**: Position sync events

## 🔄 Data Flow

### Trading Flow
1. **WebSocket** → Market data updates
2. **Technical Analysis** → Signal generation
3. **Trading Engine** → Position management
4. **Risk Manager** → Breakeven and risk control
5. **Trade Tracker** → Persistence and logging
6. **Telegram** → Notifications

### Monitoring Flow
1. **Position Reconciliation** → Sync with exchange
2. **Breakeven Monitoring** → Move profitable trades
3. **Risk Monitoring** → Drawdown protection
4. **8-Hour Rule** → Close negative positions
5. **System Health** → Performance monitoring

## 🛠️ Maintenance

### Regular Tasks
- **Log Cleanup**: Automatic (daily)
- **Memory Cleanup**: Automatic (hourly)
- **Position Reconciliation**: Every 10 minutes
- **Symbol Refresh**: Every 4 hours

### Manual Tasks
- **Configuration Updates**: Edit `settings.py`
- **Database Maintenance**: Use provided scripts
- **Log Analysis**: Check `logs/` directory
- **Performance Monitoring**: Review system stats

## 📈 Performance Optimizations

### Memory Management
- **Connection Pooling**: Reduced pool sizes for t2.micro
- **Cache Management**: TTL-based caching with size limits
- **Data Cleanup**: Periodic cleanup of old data structures

### API Efficiency
- **Batch Operations**: Combined API calls where possible
- **Retry Logic**: Exponential backoff for failed requests
- **Rate Limiting**: Respect exchange limits

### Resource Usage
- **AWS EC2 Optimized**: Tuned for t2.micro instances
- **Memory Limits**: Controlled data structure sizes
- **CPU Efficiency**: Reduced polling intervals

This clean structure provides a maintainable, scalable foundation for the CFT Prop Trading Bot with comprehensive documentation and clear separation of concerns.