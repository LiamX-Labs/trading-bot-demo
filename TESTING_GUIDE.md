# Risk Management Testing Guide

## Overview

This guide explains how to test the equity-based risk management system including all drawdown triggers and performance analysis features.

---

## Test Script

### Location
```
test_risk_management.py
```

### Quick Start
```bash
python test_risk_management.py
```

---

## What Gets Tested

### 1. Trading Allowed Check
- Verifies `is_trading_allowed()` method
- Checks if any circuit breakers or halts are active
- Returns status and reason

### 2. Position Size Multiplier
- Checks `get_position_size_multiplier()` method
- Should return 1.0 normally
- Returns 0.5 when weekly 4% triggered
- Returns 0.0 when halted

### 3. Telegram Connectivity
- Tests Telegram API connection
- Verifies retry logic with exponential backoff
- Handles network errors gracefully
- Sends test message to confirm delivery

### 4. Daily 2% Circuit Breaker
- Simulates 2% daily equity drop
- Triggers circuit breaker
- Closes all positions (simulated)
- Pauses trading until 00:01 UTC next day
- Sends Telegram alert with countdown

### 5. Weekly 4% Position Reduction
- Simulates 4% weekly equity drop
- Reduces position size to 50%
- Continues trading with smaller positions
- Sends Telegram alert about reduction

### 6. Weekly 6% Trading Halt
- Simulates 6% weekly equity drop
- Closes all positions (simulated)
- Halts trading until Monday 00:01 UTC
- Sends Telegram alert with countdown

### 7. Performance Analysis
- Fetches closed trades from yesterday
- Calculates comprehensive metrics
- Generates performance report
- Sends to Telegram (if trades exist)

---

## Expected Output

### Successful Test Run

```
╔════════════════════════════════════════════════════════════════╗
║               RISK MANAGEMENT TEST SUITE                       ║
╚════════════════════════════════════════════════════════════════╝

======================================================================
  TEST 1: Trading Allowed Check
======================================================================

Trading allowed: True
Reason: ✅ Trading allowed
✅ Test passed

======================================================================
  TEST 2: Position Size Multiplier
======================================================================

Current multiplier: 1.0
Expected: 1.0 (no drawdown)
✅ Test passed

======================================================================
  TEST 3: Telegram Alert System
======================================================================

🔍 Testing Telegram connectivity...
✅ Telegram alert sent successfully

======================================================================
  TEST 4: Daily 2% Circuit Breaker
======================================================================

Current equity: $10000.00
Simulated daily start: $10204.08
Simulated drop: 2.00%

🔍 Triggering circuit breaker check...
✅ Circuit breaker activated
End time: 2025-10-23 00:01:00+00:00

Trading allowed: False
Reason: ⛔ Daily circuit breaker active. Trading resumes in 14h 32m

... (additional tests)

======================================================================
  TEST SUMMARY
======================================================================

All tests completed!
Check Telegram for alert messages
Review console output above for detailed results
```

---

## Telegram Alert Examples

### Test Alert
```
🧪 **Risk Management Test Alert**

Time: 2025-10-22 09:30:00 UTC

Testing features:
✓ Daily 2% circuit breaker
✓ Weekly 4% position reduction
✓ Weekly 6% trading halt
✓ Performance analysis
✓ Network error handling with retries

This is a test message to verify Telegram integration.
```

### Daily Circuit Breaker Alert
```
🚨 DAILY CIRCUIT BREAKER ACTIVATED

Daily equity drawdown: 2.15%
Start equity: $10,204.08
Current equity: $9,985.00

⛔ All positions closed
⛔ Trading paused until 2025-10-23 00:01 UTC
⏱️ Countdown: 14h 32m remaining
```

### Weekly Position Reduction Alert
```
⚠️ WEEKLY POSITION SIZE REDUCTION

Weekly equity drawdown: 4.23%
Weekly start: $10,000.00
Current equity: $9,577.00

📉 Position size reduced to 50%
🔄 Full size restores after 50% loss recovery
```

### Weekly Trading Halt Alert
```
🚨 WEEKLY TRADING HALT ACTIVATED

Weekly equity drawdown: 6.45%
Weekly start: $10,000.00
Current equity: $9,355.00

⛔ All positions closed
⛔ Trading halted until Monday 2025-10-27 00:01 UTC
⏱️ Countdown: 3d 18h remaining
```

---

## Network Error Handling

### Expected Behavior

When Telegram is unreachable:
```
⚠️ Telegram connection error (attempt 1/3): Network unreachable
⚠️ Telegram connection error (attempt 2/3): Network unreachable
⚠️ Telegram connection error (attempt 3/3): Network unreachable
❌ Failed to send Telegram message after 3 attempts
```

### Features
- **Exponential backoff**: 1s, 2s, 4s between retries
- **Non-blocking**: System continues even if Telegram fails
- **Logging**: All attempts logged for debugging
- **Graceful degradation**: Analysis completes without Telegram

---

## Manual Testing Scenarios

### Test Daily Circuit Breaker in Production

```python
# In risk_manager.py or via console
risk_manager.daily_equity_start = current_equity / 0.98  # Simulate 2% drop
await risk_manager.check_equity_drawdowns()
```

### Test Weekly Position Reduction

```python
# Set weekly start high to trigger 4% drop
risk_manager.weekly_equity_start = current_equity / 0.96  # 4% drop
risk_manager.weekly_equity_peak = risk_manager.weekly_equity_start
await risk_manager.check_equity_drawdowns()
```

### Test Weekly Trading Halt

```python
# Set weekly start high to trigger 6% drop
risk_manager.weekly_equity_start = current_equity / 0.94  # 6% drop
risk_manager.weekly_equity_peak = risk_manager.weekly_equity_start
await risk_manager.check_equity_drawdowns()
```

### Test Performance Analysis

```python
# Manually trigger analysis
await risk_manager._run_daily_performance_analysis()
await risk_manager._run_weekly_performance_analysis()
await risk_manager._run_monthly_performance_analysis()
```

---

## Verification Checklist

After running tests:

- [ ] Test script completes without errors
- [ ] All 7 tests show expected output
- [ ] Telegram test message received
- [ ] Circuit breaker alert received (if triggered)
- [ ] Position reduction alert received (if triggered)
- [ ] Trading halt alert received (if triggered)
- [ ] Performance analysis runs (warns if no trades)
- [ ] Network errors handled gracefully
- [ ] System continues after failed alerts

---

## Troubleshooting

### No Telegram Messages

**Problem**: Tests run but no Telegram messages received

**Solutions**:
1. Check `.env` file has correct `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
2. Verify network connectivity: `ping api.telegram.org`
3. Check bot is added to the chat
4. Review console for error messages

### Circuit Breaker Not Triggering

**Problem**: Daily circuit breaker not activating

**Solutions**:
1. Check current equity is actually 2% below `daily_equity_start`
2. Verify `daily_equity_start` is set (should be set on startup)
3. Check `daily_circuit_breaker_active` is False before test
4. Review threshold in `settings.py`: `DAILY_EQUITY_DRAWDOWN_THRESHOLD`

### Position Size Not Reducing

**Problem**: Weekly position reduction not working

**Solutions**:
1. Check drop is exactly 4% (not more, which triggers halt)
2. Verify `weekly_equity_start` is set correctly
3. Check `weekly_drawdown_level` is 0 before test
4. Review threshold in `settings.py`: `WEEKLY_EQUITY_DRAWDOWN_THRESHOLD_LEVEL1`

### Performance Analysis Fails

**Problem**: Performance analysis throws errors

**Solutions**:
1. Expected if no trades exist - check error message
2. Verify Bybit API credentials in `.env`
3. Check date range (yesterday may have no trades)
4. Review pandas/numpy installation

---

## Advanced Testing

### Continuous Monitoring

Run in loop to monitor real equity changes:

```bash
while true; do
    python test_risk_management.py
    sleep 300  # Run every 5 minutes
done
```

### Integration with Bot

The production bot already runs these checks:
- Equity drawdowns: Every 3 minutes
- Performance analysis: Daily at 00:01 UTC
- Trading status: Before every trade

### Logging Test Results

```bash
python test_risk_management.py 2>&1 | tee test_results_$(date +%Y%m%d_%H%M%S).log
```

---

## Safety Notes

⚠️ **Important**:
- Tests simulate drawdowns - they don't affect real trading
- Tests don't close actual positions
- Telegram alerts are real - you'll receive notifications
- Performance analysis fetches real trade data
- No money is at risk during testing

---

## Next Steps

1. Run test suite: `python test_risk_management.py`
2. Verify Telegram messages received
3. Review console output for any errors
4. If all tests pass, system is ready for production
5. Monitor first few days of live operation
6. Adjust thresholds if needed in `settings.py`

---

**Test Version:** 1.0
**Last Updated:** October 22, 2025
**Status:** Ready for Testing
