# Equity-Based Risk Management System

## Overview

The trading system now implements a comprehensive equity-based drawdown management system with multiple layers of protection and automated performance analysis.

---

## 📊 Equity Drawdown Protection

### 1. Daily Equity Drawdown (2% Circuit Breaker)

**Trigger:** Daily equity drops 2% from start-of-day snapshot

**Action:**
- ✅ All positions immediately closed
- ⛔ Trading halted until next day 00:01 UTC
- 📱 Telegram alert with countdown timer

**Example:**
```
🚨 DAILY CIRCUIT BREAKER ACTIVATED

Daily equity drawdown: 2.15%
Start equity: $10,000.00
Current equity: $9,785.00

⛔ All positions closed
⛔ Trading paused until 2025-10-23 00:01 UTC
⏱️ Countdown: 14h 32m remaining
```

**Location:** [risk_manager.py:464-495](../risk_manager.py#L464-495)

---

### 2. Weekly Equity Drawdown Level 1 (4% - Position Size Reduction)

**Trigger:** Weekly equity drops 4% from Monday start

**Action:**
- 📉 Position size reduced by 50%
- ✅ Trading continues with half-size positions
- 🔄 Full size restored after recovering 50% of losses

**Example:**
```
⚠️ WEEKLY POSITION SIZE REDUCTION

Weekly equity drawdown: 4.23%
Weekly start: $10,000.00
Current equity: $9,577.00

📉 Position size reduced to 50%
🔄 Full size restores after 50% loss recovery
```

**Recovery Logic:**
- Weekly loss: $423
- Recovery target: $10,000 - ($423 × 50%) = $9,788.50
- When equity reaches $9,788.50 → restore to 100% position size

**Location:** [risk_manager.py:537-568](../risk_manager.py#L537-568)

---

### 3. Weekly Equity Drawdown Level 2 (6% - Trading Halt)

**Trigger:** Weekly equity drops 6% from Monday start

**Action:**
- ✅ All positions immediately closed
- ⛔ Trading halted until Monday 00:01 UTC
- 📱 Telegram alert with countdown timer

**Example:**
```
🚨 WEEKLY TRADING HALT ACTIVATED

Weekly equity drawdown: 6.45%
Weekly start: $10,000.00
Current equity: $9,355.00

⛔ All positions closed
⛔ Trading halted until Monday 2025-10-27 00:01 UTC
⏱️ Countdown: 3d 18h remaining
```

**Location:** [risk_manager.py:504-535](../risk_manager.py#L504-535)

---

## 📈 Automated Performance Analysis

### Daily Analysis (00:01 UTC)

**Frequency:** Every day at 00:01 UTC

**Content:**
- Previous day's trading performance
- Win rate, P&L, profit factor
- Risk metrics (Sharpe ratio, drawdown)
- Delivered via Telegram (no PDF)

**Example Output:**
```
📊 Daily Performance Analysis

**Overview:**
Total Trades: 15
Win Rate: 60.00%
Wins: 9 | Losses: 6 | BE: 0

**P&L:**
Net Profit: $245.50
Total Return: 2.46%
Gross Profit: $567.80
Gross Loss: $322.30

**Performance Metrics:**
Profit Factor: 1.76
Expectancy: $16.37
Sharpe Ratio: 1.42
```

**Location:** [risk_manager.py:154-195](../risk_manager.py#L154-195)

---

### Weekly Analysis (Monday 00:01 UTC)

**Frequency:** Every Monday at 00:01 UTC

**Content:**
- Previous week's trading performance
- All metrics from daily analysis
- Extended trade statistics
- Delivered via Telegram (no PDF)

**Location:** [risk_manager.py:197-228](../risk_manager.py#L197-228)

---

### Monthly Analysis (1st of Month 00:01 UTC)

**Frequency:** 1st day of each month at 00:01 UTC

**Content:**
- Previous month's trading performance
- Comprehensive metrics and statistics
- Long-term trend analysis
- Delivered via Telegram (no PDF)

**Location:** [risk_manager.py:230-261](../risk_manager.py#L230-261)

---

## ⚙️ Configuration

All settings are in [settings.py](../settings.py):

```python
# Daily equity drawdown (circuit breaker)
DAILY_EQUITY_DRAWDOWN_THRESHOLD = 0.02  # 2%
DAILY_CIRCUIT_BREAKER_PAUSE_HOURS = 24  # Until next day 00:01 UTC

# Weekly equity drawdown (progressive risk reduction)
WEEKLY_EQUITY_DRAWDOWN_THRESHOLD_LEVEL1 = 0.04  # 4% reduces position size
WEEKLY_EQUITY_DRAWDOWN_THRESHOLD_LEVEL2 = 0.06  # 6% halts trading
WEEKLY_POSITION_SIZE_REDUCTION = 0.50  # Reduce to 50%
WEEKLY_RECOVERY_THRESHOLD = 0.50  # Recover 50% to restore full size

# Monitoring intervals
EQUITY_DRAWDOWN_CHECK_INTERVAL = 180  # 3 minutes
```

---

## 🔄 System Integration

### Trading Engine Integration

Before executing any trade, the system checks:

1. **Trading allowed?** (`is_trading_allowed()`)
   - Daily circuit breaker active?
   - Weekly halt active?

2. **Position size multiplier** (`get_position_size_multiplier()`)
   - Returns: 1.0 (full), 0.5 (reduced), or 0.0 (halted)

**Location:** [trading_engine.py:168-182](../src/core/trading_engine.py#L168-182)

### Monitoring Tasks

New dedicated monitor in main.py:

```python
async def _equity_drawdown_monitor(self):
    """Monitor equity-based drawdowns every 3 minutes"""
    while True:
        await asyncio.sleep(settings.EQUITY_DRAWDOWN_CHECK_INTERVAL)
        await self.risk_manager.check_equity_drawdowns()
```

**Location:** [main.py:129-136](../src/main.py#L129-136)

---

## 📱 Telegram Notifications

All triggers include:
- Current drawdown percentage
- Starting and current equity values
- Action taken (close positions, reduce size, halt)
- Countdown timer to resumption
- Clear emojis for quick visual identification

---

## 🔍 Equity Calculation

Equity = Wallet Balance + Unrealized PnL

Uses Bybit's `totalEquity` field from wallet-balance API:

```python
def get_current_equity(self) -> float:
    """Get current account equity (balance + unrealized PnL)"""
    # Fetches from /v5/account/wallet-balance
    # Returns totalEquity for USDT
```

**Location:** [risk_manager.py:320-353](../risk_manager.py#L320-353)

---

## 📅 Weekly Reset Logic

Every Monday at 00:01 UTC:
- Weekly equity start reset to current equity
- Weekly peak reset to current equity
- Drawdown level reset to 0 (normal)
- Position size multiplier reset to 1.0 (full)

**Location:** [risk_manager.py:133-140](../risk_manager.py#L133-140)

---

## 🛡️ Safety Features

### Multiple Layers
1. **Daily:** 2% drawdown → full pause
2. **Weekly Level 1:** 4% drawdown → 50% position size
3. **Weekly Level 2:** 6% drawdown → full halt

### Automatic Recovery
- Daily circuit breaker: Auto-lifts at 00:01 UTC next day
- Weekly Level 1: Auto-recovers at 50% loss recovery
- Weekly Level 2: Auto-lifts Monday 00:01 UTC

### Countdown Timers
- All pauses include real-time countdown
- Users always know when trading resumes
- Prevents premature manual intervention

---

## 📊 Performance Analysis Features

### No PDF Generation
- All reports via Telegram only
- Reduces server resource usage
- Immediate delivery
- Mobile-friendly format

### Smart Scheduling
- Daily: 00:01 UTC every day
- Weekly: 00:01 UTC every Monday
- Monthly: 00:01 UTC 1st of month
- Automatic cascading (Monday triggers weekly, 1st triggers monthly)

### Metrics Included
- Total trades, win rate, P&L
- Profit factor, Sharpe ratio, expectancy
- Max drawdown, recovery factor
- Largest wins/losses
- Consecutive streaks
- Best/worst days
- Average trade duration

---

## 🚨 Emergency Override

If manual intervention needed:

```python
# Disable daily circuit breaker
risk_manager.daily_circuit_breaker_active = False
risk_manager.daily_circuit_breaker_end_time = None

# Disable weekly halt
risk_manager.weekly_drawdown_level = 0
risk_manager.position_size_multiplier = 1.0
risk_manager.weekly_halt_end_time = None
```

---

## 📈 Monitoring Dashboard

Key methods for status checks:

```python
# Check if trading allowed
allowed, reason = risk_manager.is_trading_allowed()

# Get current position size multiplier
multiplier = risk_manager.get_position_size_multiplier()

# Get current equity
equity = risk_manager.get_current_equity()

# Check drawdown status
print(f"Daily equity: ${risk_manager.daily_equity_start:.2f}")
print(f"Weekly equity: ${risk_manager.weekly_equity_start:.2f}")
print(f"Weekly level: {risk_manager.weekly_drawdown_level}")
```

---

## 🎯 Benefits

1. **Proactive Protection:** Stops losses before they spiral
2. **Progressive Response:** Graduated levels of protection
3. **Automatic Recovery:** Self-healing system
4. **Transparency:** Real-time notifications with countdowns
5. **Performance Insights:** Daily/weekly/monthly analysis
6. **Resource Efficient:** Telegram-only, no PDF generation
7. **Peace of Mind:** Multiple safety nets working 24/7

---

## 📝 Notes

- All equity calculations use live data from Bybit API
- Snapshots taken at 00:01 UTC (not midnight)
- Performance analysis runs AFTER snapshot updates
- Weekly reset always on Monday regardless of drawdown
- Monthly analysis uses 30-day rolling window
- System survives restarts (checks equity on startup)

---

## 🔗 Related Files

- [risk_manager.py](../risk_manager.py) - Core risk management implementation
- [settings.py](../settings.py) - Configuration parameters
- [trading_engine.py](../src/core/trading_engine.py) - Trading integration
- [main.py](../src/main.py) - Monitor orchestration
- [analyze_performance.py](../performance_analysis/analyze_performance.py) - Performance analysis engine
