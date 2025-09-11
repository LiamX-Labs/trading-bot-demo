# Crypto Trading Dashboard - Database Integration

Real-time PostgreSQL + TimescaleDB integration for crypto trading algorithm performance tracking.

## 🚀 Quick Setup

### 1. Install Database
```bash
./complete_db_setup.sh
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Test Integration
```bash
python test_integration.py
```

## 💡 Basic Usage

### Database Integration
```python
from database_manager import get_db_manager, TradeData

# Initialize database
db = get_db_manager()

# Log a trade
trade_data = TradeData(
    symbol="BTCUSDT", side="long", entry_price=50000.0, 
    size=0.001, leverage=2.0, strategy="momentum"
)
trade_id = db.log_trade_entry(trade_data)

# Close trade
db.log_trade_exit(trade_id, exit_price=51000.0, pnl=1.0, roe=2.0)
```

### Real-time Trading Bot Integration
```python
from trading_integration import TradingBotIntegration

# Initialize integration
trading_bot = TradingBotIntegration()

# Execute trade (automatically logged)
trade_id = await trading_bot.execute_trade(
    symbol="BTCUSDT", side="long", size=0.001, 
    entry_price=50000.0, strategy="your_strategy"
)

# Close trade (automatic PnL calculation)
await trading_bot.close_trade(trade_id, exit_price=51000.0)
```

### Binance Integration
```python
from trading_integration import BinanceTradingIntegration

# Initialize with API credentials
trading_bot = BinanceTradingIntegration(
    api_key="your_api_key", 
    api_secret="your_api_secret"
)

# Place market order (automatically logged)
trade_id = await trading_bot.place_market_order(
    symbol="BTCUSDT", side="buy", quantity=0.001
)
```

## 📊 Dashboard Data

The system automatically provides:
- **Win rates** (1D, 7D, 30D, 90D, All-time)
- **Trade history** with PnL calculations
- **Equity curve** time-series data  
- **Performance metrics** (ROE, trade counts, etc.)
- **Real-time updates** via callbacks

### Get Performance Data
```python
# Get comprehensive metrics
metrics = db.get_performance_metrics()
print(f"Win Rate: {metrics['win_rate_all']:.2f}%")

# Get equity curve for charts
equity_data = db.get_equity_curve(timeframe='7d')

# Get recent trades
recent_trades = db.get_recent_trades(limit=10)
```

## 🔧 Project Structure

```
cftprop/
├── database_manager.py          # Core database operations
├── trading_integration.py       # Real-time bot integration
├── test_integration.py         # Integration tests
├── complete_db_setup.sh        # Database setup script
├── database_setup.sql          # Database schema
├── requirements.txt            # Python dependencies
└── docs/                       # Detailed documentation
    ├── trading_dashboard_setup.md
    └── trading_integration_guide.md
```

## ✨ Key Features

- **Thread-safe** database operations
- **TimescaleDB** for efficient time-series storage
- **Automatic PnL** calculations and ROE tracking
- **Real-time callbacks** for dashboard updates
- **Exchange integration** (Binance example included)
- **Error handling** and connection recovery

## 🧪 Testing

```bash
# Test database connection only
python test_integration.py --db-only

# Test complete integration
python test_integration.py

# View setup help
python test_integration.py --help
```

## 📚 Documentation

- **Complete Setup Guide**: `docs/trading_dashboard_setup.md`
- **Integration Examples**: `docs/trading_integration_guide.md`

## 🔒 Database Schema

**Tables:**
- `trades` - All trade entries/exits with PnL tracking
- `equity_curve` - TimescaleDB hypertable for account value history

**Views:**
- `open_positions` - Currently active trades
- `closed_trades` - Completed trades with duration
- `daily_performance` - Daily aggregated metrics

**Functions:**
- `get_win_rate(days)` - Calculate win rate for timeframe
- `get_latest_equity()` - Get current account snapshot

## 🚀 Integration with Your Bot

Replace your existing trade logging with:

```python
# Instead of logging to files/CSV
# log_trade_to_csv(symbol, side, price, size)

# Use database integration
trade_id = await trading_bot.execute_trade(
    symbol=symbol, side=side, entry_price=price, size=size
)
```

Your trading algorithm runs unchanged - the integration layer automatically captures all trade data and feeds your dashboard with real-time performance metrics.

---

**Ready to start?** Run `./complete_db_setup.sh` to set up the database, then `python test_integration.py` to verify everything works!