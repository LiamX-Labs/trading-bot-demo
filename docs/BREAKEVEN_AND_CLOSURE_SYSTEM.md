# CFT Prop Bot - Breakeven & Closure Notification System

## Overview

This document describes the enhanced breakeven tracking system and detailed closure notification features implemented to eliminate redundancy and provide comprehensive trade closure information.

## 🔄 Breakeven Tracking System

### Problem Solved
- **Before**: Trades moved to breakeven were removed from tracking, causing redundant breakeven checks
- **After**: Trades moved to breakeven are tracked separately but still count toward position limits

### Implementation

#### Two-Tier Trade Tracking
```python
# Trading Engine State Management
self.active_trades = {}      # Trades still needing breakeven monitoring
self.breakeven_trades = {}   # Trades moved to breakeven (no more BE checks)
```

#### Position Limit Calculation
```python
# Max trades check includes both active and breakeven
total_positions = len(self.active_trades) + len(self.breakeven_trades)
if total_positions >= MAX_ACTIVE_TRADES:
    return  # Don't open new trade
```

### Breakeven Movement Process

1. **Breakeven Check**: Risk manager checks only `active_trades`
2. **Successful Move**: Trade moved from `active_trades` to `breakeven_trades`
3. **Continued Monitoring**: Breakeven trades monitored for:
   - External closures (reconciliation)
   - 8-hour negative PnL rule
   - Position counting for max limits

### Key Methods

```python
# Move trade to breakeven tracking
trading_engine.move_trade_to_breakeven(symbol, rule_id)

# Get all trades for position counting
total_trades = trading_engine.get_all_trades()

# Remove trade completely from both tracking systems
trading_engine.remove_trade_completely(symbol, rule_id, reason)
```

## 📱 Enhanced Closure Notifications

### Detailed Trade Information

When a position is closed externally, the system now provides:

- **Entry Price**: Original trade entry price
- **Exit Price**: Actual closure price from execution history
- **Price Movement**: Percentage change from entry to exit
- **PnL**: Realized profit/loss in USD
- **Duration**: How long the trade was open
- **Closure Reason**: Intelligent classification of exit type

### Sample Notification

```
🔄 **Trade Closed Externally**

**Symbol:** BTCUSDT (Rule 6)
**Entry:** $45000.000000
**Exit:** $46350.000000
**Change:** +3.00%
**PnL:** $+4.05
**Duration:** 2h 30m
**Reason:** 🟢 Take Profit
```

## 🧠 Intelligent Closure Reason Detection

The system analyzes price movement patterns to classify closure reasons:

### Classification Logic

| Price Change | Condition | Reason |
|-------------|-----------|---------|
| < 1% | Small movement | 🟡 Breakeven Exit |
| ≥ 24% (80% of TP) | Near take profit | 🟢 Take Profit |
| ≤ -6.4% (80% of SL) | Near stop loss | 🔴 Stop Loss |
| > 0% + moved to BE | From breakeven | 🔄 Trailing Stop (from breakeven) |
| ≥ 8% (BE threshold) | Above BE threshold | 📈 Trailing Stop |
| < 0% + ≥ 8h old | Negative after 8h | ⏰ 8h Negative PnL Exit |
| < 0% + < 8h old | Early negative | 📉 Manual/Early Exit |
| Other | Unknown pattern | 🤔 Unknown Exit |

### Settings Integration

All thresholds are configurable in `settings.py`:

```python
# Closure reason thresholds
BREAKEVEN_THRESHOLD = 8.0      # Profit % for breakeven move
TAKEPROFIT_PERCENT = 30        # Take profit target %
STOPLOSS_PERCENT = 8           # Stop loss %
NEGATIVE_PNL_CLOSE_HOURS = 8   # Hours before negative PnL closure
```

## 🔍 Enhanced Position Reconciliation

### Comprehensive Monitoring

The reconciliation system now checks both trade tracking systems:

```python
# Check active trades for external closures
externally_closed_active = reconcile_positions_with_tracking(active_trades)

# Check breakeven trades for external closures  
externally_closed_breakeven = reconcile_positions_with_tracking(breakeven_trades)

# Combined processing
all_externally_closed = externally_closed_active + externally_closed_breakeven
```

### Detailed Closure Analysis

For each externally closed position:

1. **Fetch Execution History**: Get recent trades from Bybit API
2. **Find Exit Execution**: Locate the closing trade after entry time
3. **Calculate Metrics**: Compute PnL, price change, duration
4. **Classify Reason**: Apply intelligent reason detection
5. **Send Notification**: Format and send detailed message
6. **Update Tracking**: Remove from appropriate tracking system

## 📊 Updated Statistics and Monitoring

### Enhanced Diagnostics

```
📊 Market check: 25 total positions (18 active, 7 breakeven), 136 symbols monitored
```

### Reconciliation Logging

```
🔍 Reconciliation check: 25 trades being monitored (18 active, 7 breakeven)
🔄 Reconciliation: Found 3 externally closed positions
```

### Trading Statistics

```python
{
    "active_trades": 18,        # Trades needing breakeven monitoring
    "breakeven_trades": 7,      # Trades moved to breakeven
    "total_positions": 25,      # Total for max position limit
    "symbols_monitored": 136,
    "processed_bars": 456,
    "processed_signals": 89,
    "last_update": 1634567890
}
```

## 🔧 System Architecture Changes

### Risk Manager Integration

```python
# Risk manager now has trading engine reference
risk_manager = RiskManager(
    active_trades_getter=lambda: trading_engine.get_active_trades(),
    trading_engine=trading_engine  # For breakeven management
)
```

### Breakeven Move Process

```python
# Old: Remove from tracking completely
active_trades.pop((symbol, rule_id), None)

# New: Move to breakeven tracking
if trading_engine:
    success = trading_engine.move_trade_to_breakeven(symbol, rule_id)
    if success:
        print("Moved to breakeven tracking")
```

## 📈 Benefits

### Eliminated Redundancy
- ✅ No more repeated breakeven checks for moved trades
- ✅ Cleaner separation of concerns
- ✅ Reduced API calls and processing overhead

### Enhanced Visibility
- ✅ Detailed closure information for all external exits
- ✅ Intelligent classification of exit reasons
- ✅ Complete trade lifecycle tracking

### Improved Accuracy
- ✅ Proper position counting including breakeven trades
- ✅ Accurate reconciliation of all trade states
- ✅ Real-time tracking of trade movements

### Better User Experience
- ✅ Rich Telegram notifications with complete trade details
- ✅ Clear categorization of why trades were closed
- ✅ Professional formatting with all relevant metrics

## 🧪 Testing and Validation

The system includes comprehensive tests covering:

- **Breakeven Movement**: Proper transition from active to breakeven tracking
- **Position Counting**: Correct total for max position limits
- **Closure Analysis**: Accurate reason classification
- **Message Formatting**: Professional Telegram notifications
- **Edge Cases**: Handling of missing data and errors

All tests pass successfully, ensuring robust operation of the enhanced system.

## 🔄 Migration Guide

### For Existing Deployments

1. **Backup Current State**: Save current `active_trades` data
2. **Deploy Updates**: Update all modified files
3. **Monitor Logs**: Watch for proper breakeven transitions
4. **Validate Notifications**: Confirm enhanced closure messages

### Configuration Updates

Ensure these settings are properly configured:

```python
# In settings.py
BREAKEVEN_THRESHOLD = 8.0
TAKEPROFIT_PERCENT = 30
STOPLOSS_PERCENT = 8
NEGATIVE_PNL_CLOSE_HOURS = 8

# Enable detailed notifications
NOTIFY_TRADE_CLOSURES = True
NOTIFY_RECONCILIATION_EVENTS = True
```

This enhanced system provides a much more sophisticated and efficient approach to trade management, eliminating redundancy while significantly improving the quality of trade closure information provided to users.