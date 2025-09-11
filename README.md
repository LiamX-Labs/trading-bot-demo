# CFT Prop Trading Bot

> Advanced cryptocurrency trading bot with intelligent breakeven management, comprehensive risk controls, and detailed logging.

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Bybit account with API access
- Telegram bot for notifications

### Installation
```bash
# Clone repository
git clone <repository-url>
cd cftprop

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Configuration
1. **Set up API credentials** in `.env`
2. **Configure trading parameters** in `settings.py`
3. **Set up Telegram notifications**
4. **Review risk management settings**

### Run the Bot
```bash
# New modular version (recommended)
python src/main.py

# Legacy version
python main.py
```

## 📚 Documentation

All documentation has been organized in the `docs/` directory:

### 📋 Core Documentation
- **[Project Structure](docs/PROJECT_STRUCTURE_CLEAN.md)** - Clean project organization
- **[Logging & Configuration](docs/LOGGING_AND_CONFIGURATION.md)** - Comprehensive logging system
- **[Breakeven & Closure System](docs/BREAKEVEN_AND_CLOSURE_SYSTEM.md)** - Enhanced trade management

### 🔧 Setup & Integration
- **[Trading Dashboard Setup](docs/trading_dashboard_setup.md)** - Dashboard configuration
- **[Trading Integration Guide](docs/trading_integration_guide.md)** - Integration documentation
- **[Restructure Guide](docs/RESTRUCTURE_GUIDE.md)** - Architecture overview

### 🛠️ Maintenance & Support
- **[Fixes Applied](docs/FIXES_APPLIED.md)** - Bug fixes and improvements
- **[Issue Resolution](docs/ISSUE_RESOLUTION.md)** - Common issues and solutions
- **[Optimization Summary](docs/OPTIMIZATION_SUMMARY.md)** - Performance improvements
- **[Git Workflow](docs/GIT_PUSH_SUMMARY.md)** - Development workflow

## ✨ Key Features

### 🎯 Trading Features
- **Multi-Rule Signal Generation**: 8 different trading rules
- **Intelligent Position Sizing**: Configurable position sizes
- **Breakeven Management**: Automatic stop-loss to breakeven moves
- **Trailing Stops**: Advanced exit strategies

### 🛡️ Risk Management
- **Two-Tier Drawdown Protection**: Unrealized and daily balance limits
- **8-Hour Negative PnL Rule**: Automatic closure of losing positions
- **Position Reconciliation**: Sync with exchange positions
- **Max Position Limits**: Configurable maximum active trades

### 📊 Monitoring & Logging
- **Daily Log Rotation**: Organized daily log files
- **Comprehensive Trade Tracking**: Complete trade lifecycle logging
- **Real-time Notifications**: Detailed Telegram alerts
- **System Health Monitoring**: Performance and error tracking

### 🔄 Cooldown System
- **4-Hour Intervals**: From 12:00 AM UTC (configurable)
- **Symbol-Level Restrictions**: Prevent overtrading
- **Automatic Cleanup**: Memory management

## 🏗️ Architecture

### Modular Design
```
src/
├── core/          # Trading engine
├── data/          # Market data & WebSocket
├── trading/       # Trade execution
├── utils/         # Utilities & helpers
└── config/        # Configuration management
```

### Legacy Compatibility
- Original files maintained for compatibility
- Gradual migration to modular architecture
- Backward compatibility preserved

## ⚙️ Configuration

### Key Settings (settings.py)
```python
# Trading Parameters
BASE_POSITION_SIZE_USD = 150
MAX_ACTIVE_TRADES = 30
BREAKEVEN_THRESHOLD = 8.0

# Risk Management
NEGATIVE_PNL_CLOSE_HOURS = 8
SYMBOL_COOLDOWN_HOURS = 4

# Monitoring Intervals
BREAKEVEN_CHECK_INTERVAL = 120  # seconds
RECONCILIATION_CHECK_INTERVAL = 600
```

### Environment Variables (.env)
```bash
BYBIT_API_KEY=your_api_key
BYBIT_API_SECRET=your_secret
BYBIT_USE_DEMO=true
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
```

## 📈 Performance

### Optimizations
- **AWS EC2 t2.micro optimized**: Reduced resource usage
- **Connection pooling**: Efficient API usage
- **Memory management**: Automatic cleanup
- **Rate limiting**: Exchange-compliant requests

### Monitoring
- **Daily log files**: `logs/cftprop_YYYY-MM-DD.log`
- **System statistics**: Real-time performance tracking
- **Error tracking**: Comprehensive error logging

## 🔧 Troubleshooting

### Common Issues
1. **API Connection Errors**: Check credentials and network
2. **Missing Notifications**: Verify Telegram setup
3. **Position Sync Issues**: Review reconciliation logs
4. **Performance Issues**: Check system resources

### Debug Mode
Enable debug logging in `settings.py`:
```python
LOG_LEVEL = "DEBUG"
DEBUG_POSITION_RECONCILIATION = True
DEBUG_BREAKEVEN_MOVES = True
```

## 📞 Support

- **Documentation**: Check the `docs/` directory
- **Issues**: Review `docs/ISSUE_RESOLUTION.md`
- **Logs**: Check `logs/` directory for detailed information
- **Configuration**: Review all settings in `settings.py`

## 🚨 Important Notes

### Risk Disclaimer
- **This is trading software**: Use at your own risk
- **Test thoroughly**: Use demo mode first
- **Monitor actively**: Review logs and notifications
- **Understand settings**: Review all configuration options

### Security
- **Keep API keys secure**: Never commit to version control
- **Use demo mode**: For testing and development
- **Monitor positions**: Regular reconciliation checks
- **Backup configurations**: Save working configurations

---

**For detailed setup instructions and advanced configuration, see the documentation in the `docs/` directory.**
