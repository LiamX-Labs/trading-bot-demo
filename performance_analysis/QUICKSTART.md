# Performance Analysis - Quick Start Guide

## 🚀 One-Time Setup

1. **Install dependencies:**
```bash
pip install numpy reportlab matplotlib
```

2. **Verify your `.env` file has required credentials:**
```
BYBIT_API_KEY=your_api_key
BYBIT_API_SECRET=your_api_secret
BYBIT_USE_DEMO=True
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

## 📊 Run Analysis

### Last Week Performance
```bash
python performance_analysis/analyze_performance.py --period 1w
```

### Last Month Performance
```bash
python performance_analysis/analyze_performance.py --period 1m
```

### Custom Date Range
```bash
python performance_analysis/analyze_performance.py --period 2025-09-01:2025-10-06
```

## 📁 Output Files

Reports are saved in the `docs/` folder with timestamps:
- `performance_Last_1_Week_20251006_143022.json` - Detailed metrics
- `performance_Last_1_Week_20251006_143022.pdf` - Visual report with charts
- `equity_curve_Last_1_Week.png` - Equity curve chart
- `drawdown_Last_1_Week.png` - Drawdown chart
- `distribution_Last_1_Week.png` - Win/loss distribution
- `cumulative_pnl_Last_1_Week.png` - Cumulative P&L chart

## 📱 Telegram Summary

A formatted summary is automatically sent to your Telegram chat including:
- Win rate and trade statistics
- P&L breakdown
- Performance ratios (Profit Factor, Sharpe Ratio)
- Risk metrics (Max Drawdown, Recovery Factor)

## 🔧 Options

```bash
# Skip Telegram notification
python performance_analysis/analyze_performance.py --period 1w --no-telegram

# Skip PDF generation (JSON only)
python performance_analysis/analyze_performance.py --period 1w --no-pdf

# Skip chart generation
python performance_analysis/analyze_performance.py --period 1w --no-charts

# Custom initial balance
python performance_analysis/analyze_performance.py --period 1w --initial-balance 5000
```

## ⚡ Quick Examples

```bash
# Weekly report without Telegram
python performance_analysis/analyze_performance.py --period 1w --no-telegram

# Monthly report, JSON only
python performance_analysis/analyze_performance.py --period 1m --no-pdf

# Last 2 weeks with custom balance
python performance_analysis/analyze_performance.py --period 2025-09-20:2025-10-06 --initial-balance 15000
```

## 🤖 Automation (Optional)

Run automatically every Monday at 9 AM:
```bash
# Add to crontab
0 9 * * 1 cd /home/william/Desktop/cftprop && python performance_analysis/analyze_performance.py --period 1w
```

## ❓ Troubleshooting

**No trades found:**
- Ensure you have closed positions in the date range
- Check API credentials

**API signature error:**
- The script now properly handles Bybit API authentication
- Ensure your API keys have "Read" permissions for positions

**reportlab not found:**
```bash
pip install reportlab matplotlib
```

**matplotlib not found:**
```bash
pip install matplotlib
```

**Telegram fails:**
- Verify bot token and chat ID in `.env`
- Use `--no-telegram` to skip

For more details, see [README.md](README.md)
