# Trading Performance Analysis

This folder contains tools for analyzing your Bybit trading strategy performance with MyFXBook-style metrics.

## Features

- 📊 **Comprehensive Metrics**: Win rate, profit factor, Sharpe ratio, expectancy, and more
- 📈 **Drawdown Analysis**: Maximum drawdown, recovery factor, equity curve tracking
- 📅 **Flexible Time Periods**: Analyze last 1 week, 1 month, or custom date ranges
- 📄 **Multiple Export Formats**: JSON and PDF reports with timestamp labels
- 📱 **Telegram Integration**: Automatic performance summaries sent to Telegram
- 🔄 **Real-time Data**: Fetches closed trades directly from Bybit API

## Installation

Install required dependencies:

```bash
pip install pandas numpy reportlab
```

The script uses existing dependencies from your main trading bot (requests, python-dotenv, etc.)

## Usage

### Basic Usage

Analyze performance for the last week:
```bash
python performance_analysis/analyze_performance.py --period 1w
```

Analyze performance for the last month:
```bash
python performance_analysis/analyze_performance.py --period 1m
```

### Custom Date Range

Analyze a specific period:
```bash
python performance_analysis/analyze_performance.py --period 2025-09-01:2025-10-01
```

### Options

- `--period PERIOD`: Time period to analyze
  - `1w` - Last 1 week
  - `1m` - Last 1 month
  - `YYYY-MM-DD:YYYY-MM-DD` - Custom date range

- `--initial-balance AMOUNT`: Initial balance for return calculations (default: 10000)

- `--no-telegram`: Skip sending Telegram notification

- `--no-pdf`: Skip PDF generation (only create JSON)

### Examples

```bash
# Last week with custom initial balance
python performance_analysis/analyze_performance.py --period 1w --initial-balance 5000

# Last month without Telegram notification
python performance_analysis/analyze_performance.py --period 1m --no-telegram

# Custom range, JSON only (no PDF)
python performance_analysis/analyze_performance.py --period 2025-09-15:2025-10-06 --no-pdf
```

## Output

### Console Output
Displays a comprehensive performance summary in the terminal.

### JSON Export
Detailed metrics saved to `docs/performance_<period>_<timestamp>.json` including:
- All calculated metrics
- Equity curve data points
- Trade-by-trade breakdown

### PDF Report
Professional report saved to `docs/performance_<period>_<timestamp>.pdf` with:
- Performance summary table
- Detailed metrics breakdown by category
- Visual formatting for easy reading

### Telegram Notification
Sends a formatted summary to your configured Telegram chat including:
- Win rate and trade counts
- P&L metrics
- Performance ratios
- Risk metrics
- Activity statistics

## Metrics Explained

### Basic Metrics
- **Total Trades**: Number of closed positions
- **Win Rate**: Percentage of winning trades
- **Win/Loss/BE**: Count of winning, losing, and breakeven trades

### P&L Metrics
- **Net Profit**: Total profit/loss
- **Gross Profit**: Sum of all winning trades
- **Gross Loss**: Sum of all losing trades
- **Total Return**: Percentage return on initial balance

### Performance Ratios
- **Profit Factor**: Gross profit / Gross loss (>1 is profitable)
- **Expectancy**: Expected value per trade in dollars
- **Sharpe Ratio**: Risk-adjusted return measure
- **Risk/Reward Ratio**: Average win / Average loss

### Risk Metrics
- **Max Drawdown**: Largest peak-to-trough decline in equity
- **Recovery Factor**: Net profit / Max drawdown
- **Best/Worst Day**: Largest single-day profit/loss

### Activity Metrics
- **Trades per Day**: Average daily trading frequency
- **Avg Trade Duration**: Average time positions are held
- **Max Consecutive Wins/Losses**: Longest winning/losing streaks

## Configuration

The script uses your existing `.env` configuration:
- `BYBIT_API_KEY`: Your Bybit API key
- `BYBIT_API_SECRET`: Your Bybit API secret
- `BYBIT_USE_DEMO`: Demo or live account
- `TELEGRAM_BOT_TOKEN`: Telegram bot token
- `TELEGRAM_CHAT_ID`: Telegram chat ID

## Automation

### Daily Performance Report

Add to crontab for daily reports at 9 AM UTC:
```bash
0 9 * * * cd /path/to/cftprop && /path/to/venv/bin/python performance_analysis/analyze_performance.py --period 1w
```

### Weekly Summary

Weekly report every Monday at 10 AM UTC:
```bash
0 10 * * 1 cd /path/to/cftprop && /path/to/venv/bin/python performance_analysis/analyze_performance.py --period 1w
```

### Monthly Report

Monthly report on the 1st at 12 PM UTC:
```bash
0 12 1 * * cd /path/to/cftprop && /path/to/venv/bin/python performance_analysis/analyze_performance.py --period 1m
```

## Troubleshooting

### No trades found
- Check the date range includes periods when you were trading
- Verify API credentials are correct
- Ensure positions were fully closed (not just reduced)

### PDF generation fails
- Install reportlab: `pip install reportlab`
- Use `--no-pdf` flag to skip PDF generation

### Telegram notification fails
- Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`
- Check network connectivity
- Use `--no-telegram` flag to skip notification

### API connection issues
- Check internet connectivity
- Verify Bybit API is accessible
- Check API key permissions include "read" access to positions

## Development

### Adding New Metrics

To add new metrics, modify the `calculate_metrics()` method in the `PerformanceAnalyzer` class.

### Custom Report Formats

Extend the `ReportGenerator` class with new methods for different output formats (CSV, HTML, etc.).

### Integration with Trading Bot

You can import and use the analyzer in your main trading bot:

```python
from performance_analysis.analyze_performance import BybitAPIClient, PerformanceAnalyzer

# Fetch trades
api = BybitAPIClient()
trades = api.get_position_closed_pnl(start_time=start_ms, end_time=end_ms)

# Analyze
analyzer = PerformanceAnalyzer(pd.DataFrame(trades))
metrics = analyzer.calculate_metrics()
```

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review console output for error messages
3. Verify API credentials and permissions
4. Check Bybit API documentation for rate limits
