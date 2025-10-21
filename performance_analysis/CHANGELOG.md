# Performance Analysis - Changelog

## Version 2.0 (2025-10-06)

### 🚀 Major Features Added

#### 📊 **Visual Charts & Graphs**
- **Equity Curve Chart**: Shows account equity growth over time
- **Drawdown Chart**: Visualizes drawdown periods with shaded areas
- **Win/Loss Distribution**: Histogram and pie chart showing trade outcomes
- **Cumulative P&L Chart**: Shows cumulative profit/loss with color-coded areas

#### 🔧 **API Fixes**
- Fixed Bybit API signature generation error
- Improved server time synchronization with caching
- Better error handling and debugging output
- Proper parameter ordering for API requests

#### 📄 **Enhanced PDF Reports**
- Embedded charts directly in PDF reports
- Multi-page layout with organized sections
- Professional styling with color-coded tables
- Charts include: equity curve, drawdown, distribution, and cumulative P&L

### 🛠️ Technical Improvements

#### API Client
- Implemented time offset caching to reduce API calls
- Added robust retry logic for server time requests
- Fixed signature generation to maintain parameter order
- Improved error messages with debugging information

#### Chart Generation
- Uses matplotlib with non-interactive backend (Agg)
- Seaborn styling for professional appearance
- High DPI (150) for crisp output
- Graceful fallback if matplotlib not installed
- Individual chart generation with error isolation

#### Performance Metrics
- Added `trade_details` to metrics for charting
- Improved data structure for equity curve visualization
- Better handling of edge cases (no trades, single trade, etc.)

### 📦 Dependencies Added
- `matplotlib>=3.7.0` - For chart generation
- Updated installation instructions in documentation

### 📝 Documentation Updates
- Updated QUICKSTART.md with chart examples
- Added `--no-charts` flag documentation
- Improved troubleshooting section
- Added API signature error resolution steps

### 🎯 New Command Line Options
```bash
--no-charts    # Skip chart generation (faster execution)
```

### 📁 Output Files
The script now generates:
1. JSON report with detailed metrics
2. PDF report with embedded charts (4 charts included)
3. Individual PNG chart files:
   - `equity_curve_<period>.png`
   - `drawdown_<period>.png`
   - `distribution_<period>.png`
   - `cumulative_pnl_<period>.png`

### 🐛 Bug Fixes
- Fixed: API signature generation error causing authentication failures
- Fixed: Server time endpoint URL (changed to `/v5/market/time`)
- Fixed: Parameter ordering in signature generation
- Fixed: Time offset caching for improved performance

### ⚡ Performance Improvements
- Server time caching reduces API calls
- Charts generated in parallel with report generation
- Optimized PDF generation with chart embedding

## Version 1.0 (Initial Release)

### Initial Features
- Fetch closed trades from Bybit API
- Calculate MyFXBook-style metrics
- Generate JSON and PDF reports
- Send Telegram notifications
- Support for custom date ranges
- Comprehensive performance metrics

---

## Upgrade Instructions

If you're upgrading from v1.0:

1. **Install new dependencies:**
```bash
pip install matplotlib>=3.7.0
```

2. **Update requirements.txt:**
```bash
pip install -r requirements.txt
```

3. **Run the analysis:**
```bash
python performance_analysis/analyze_performance.py --period 1w
```

The script will now automatically generate charts and embed them in PDF reports.

## Breaking Changes
None. All new features are backward compatible.

## Known Issues
- matplotlib must use 'Agg' backend in headless environments
- Chart generation requires pandas DataFrame operations
- PDF generation with charts increases file size (~2-5MB)

## Future Enhancements
- Interactive HTML reports
- Monthly comparison charts
- Symbol-specific performance breakdown
- Risk metrics visualization (Sharpe ratio, sortino ratio)
- Trade timeline visualization
