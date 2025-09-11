# CFT Prop Trading Bot - Restructuring Guide

## 🏗️ New Project Structure

The project has been restructured for better modularity, maintainability, and scalability while preserving all existing functionality.

### 📂 Directory Structure

```
cftprop/
├── src/                          # New modular source code
│   ├── config/                   # Configuration management
│   │   ├── __init__.py
│   │   └── settings.py          # Centralized settings (replaces settings.py)
│   ├── core/                     # Core trading engine
│   │   ├── __init__.py
│   │   └── trading_engine.py    # Main trading logic coordination
│   ├── data/                     # Data management modules
│   │   ├── __init__.py
│   │   ├── market_data.py       # Market data fetching and management
│   │   ├── indicators.py        # Technical analysis and signals
│   │   └── websocket.py         # WebSocket connection management
│   ├── trading/                  # Trading execution
│   │   ├── __init__.py
│   │   └── executor.py          # Trade execution and order management
│   ├── utils/                    # Utility functions
│   │   ├── __init__.py
│   │   └── helpers.py           # Helper functions and utilities
│   └── main.py                   # New main application entry point
├── original_backup/              # Backup of original files
│   ├── main.py                   # Original monolithic main.py
│   ├── order_manager.py
│   ├── risk_manager.py
│   ├── settings.py
│   ├── telegram_alerts.py
│   └── trade_tracker.py
├── main_new.py                   # New entry point (use this to start)
├── risk_manager.py               # Kept as-is (reused)
├── trade_tracker.py              # Kept as-is (reused)
├── telegram_alerts.py            # Kept as-is (reused)
└── settings.py                   # Original (kept for compatibility)
```

## 🔧 How to Run

### Option 1: New Restructured Version (Recommended)
```bash
python main_new.py
```

### Option 2: Original Version (Backup)
```bash
python original_backup/main.py
```

## 📋 Key Improvements

### 1. **Modular Architecture**
- **Separation of Concerns**: Each module has a specific responsibility
- **Maintainability**: Easier to modify and debug individual components
- **Testability**: Components can be tested in isolation
- **Scalability**: Easy to add new features without affecting existing code

### 2. **Configuration Management**
- **Centralized Settings**: All configuration in `src/config/settings.py`
- **Organized by Category**: API, Trading, Data, System, Telegram configs
- **Type Safety**: Clear configuration classes and defaults

### 3. **Data Management**
- **Market Data Manager**: Handles symbol fetching and historical data
- **Technical Analyzer**: Isolated technical analysis and signal generation
- **WebSocket Manager**: Dedicated WebSocket connection handling

### 4. **Trading Engine**
- **Core Coordination**: Central orchestration of all trading activities
- **State Management**: Proper tracking of trades and system state
- **Error Handling**: Improved error handling and recovery

### 5. **Utility Functions**
- **Helper Functions**: Reusable utility functions
- **Trading Restrictions**: Dedicated cooldown and restriction management

## 🔄 Migration Notes

### Preserved Functionality
All existing functionality has been preserved:
- ✅ 5-minute bar processing with converted indicators
- ✅ 30% take profit + 8% stop loss + trailing stop
- ✅ Max 30 active trades
- ✅ 4-hour cooldown per symbol (from 3am UTC)
- ✅ 8-hour negative PnL auto-close
- ✅ 10M volume minimum filter
- ✅ WebSocket real-time data processing
- ✅ Risk management and breakeven logic
- ✅ Telegram notifications
- ✅ Position recovery and reconciliation

### Dependencies
The restructured version reuses existing modules:
- `risk_manager.py` - Risk management (unchanged)
- `trade_tracker.py` - Trade logging (unchanged) 
- `telegram_alerts.py` - Notifications (unchanged)

### Configuration
Settings have been reorganized but all original parameters are preserved:
- Volume filter: 10M USDT minimum
- Timeframe: 5-minute bars
- Indicator periods: Converted for 5-min equivalency
- Trading parameters: All original values maintained

## 🚀 Performance Benefits

### 1. **Better Resource Management**
- Optimized for 3-core, 8GB server
- Improved concurrent request handling
- Better memory management

### 2. **Enhanced Monitoring**
- Modular monitoring systems
- Better error isolation
- Comprehensive system diagnostics

### 3. **Improved Reliability**
- Better error handling
- Graceful degradation
- Automatic recovery mechanisms

## 🛠️ Development Benefits

### 1. **Easier Debugging**
- Component isolation
- Clear data flow
- Better logging structure

### 2. **Feature Addition**
- Add new indicators in `data/indicators.py`
- Add new trading strategies in `trading/`
- Add new monitoring in `main.py`

### 3. **Testing**
- Unit test individual components
- Mock external dependencies
- Test different configurations

## 📊 Monitoring

The restructured version provides better monitoring:
- System performance metrics
- Trading statistics
- Resource usage tracking
- WebSocket connection status

## 🔧 Troubleshooting

### If the new version has issues:
1. Check logs for specific error messages
2. Verify all dependencies are installed
3. Ensure .env file is properly configured
4. Fall back to original version: `python original_backup/main.py`

### Common Issues:
- **Import errors**: Ensure Python path includes src directory
- **Config errors**: Check .env file format
- **Connection errors**: Verify API credentials and network

## 📈 Future Enhancements

The new structure makes it easy to add:
- Additional technical indicators
- Multiple timeframe analysis
- Advanced risk management rules
- Performance analytics dashboard
- Database integration
- REST API interface

## 🎯 Conclusion

The restructured version maintains 100% functionality while providing:
- Better code organization
- Easier maintenance
- Enhanced performance
- Improved reliability
- Future extensibility

Use `main_new.py` to run the restructured version with all the benefits of the new architecture!