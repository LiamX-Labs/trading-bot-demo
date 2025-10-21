# Risk Management Quick Reference Card

## 🚨 Drawdown Triggers

| Level | Threshold | Action | Duration | Auto-Recovery |
|-------|-----------|--------|----------|---------------|
| **Daily Circuit Breaker** | 2% | Close all + Pause | Until 00:01 UTC next day | Yes |
| **Weekly Level 1** | 4% | Reduce position to 50% | Until 50% recovery | Yes |
| **Weekly Level 2** | 6% | Close all + Halt | Until Monday 00:01 UTC | Yes |

---

## 📊 Performance Analysis Schedule

| Frequency | Time | Content | Delivery |
|-----------|------|---------|----------|
| **Daily** | 00:01 UTC | Yesterday's performance | Telegram |
| **Weekly** | Monday 00:01 UTC | Last 7 days | Telegram |
| **Monthly** | 1st 00:01 UTC | Last 30 days | Telegram |

---

## ⚙️ Key Settings

```python
# Thresholds
DAILY_EQUITY_DRAWDOWN_THRESHOLD = 0.02          # 2%
WEEKLY_EQUITY_DRAWDOWN_THRESHOLD_LEVEL1 = 0.04  # 4%
WEEKLY_EQUITY_DRAWDOWN_THRESHOLD_LEVEL2 = 0.06  # 6%

# Actions
WEEKLY_POSITION_SIZE_REDUCTION = 0.50    # 50% reduction
WEEKLY_RECOVERY_THRESHOLD = 0.50         # 50% recovery needed

# Monitoring
EQUITY_DRAWDOWN_CHECK_INTERVAL = 180     # 3 minutes
```

---

## 🔍 Status Check Commands

```python
# Trading allowed?
allowed, reason = risk_manager.is_trading_allowed()

# Current position multiplier
multiplier = risk_manager.get_position_size_multiplier()
# Returns: 1.0 (full), 0.5 (reduced), 0.0 (halted)

# Current equity
equity = risk_manager.get_current_equity()

# Drawdown state
risk_manager.daily_circuit_breaker_active     # True/False
risk_manager.weekly_drawdown_level            # 0, 1, or 2
risk_manager.position_size_multiplier         # 1.0, 0.5, or 0.0
```

---

## 🛠️ Manual Override (Emergency)

```python
# Disable daily circuit breaker
risk_manager.daily_circuit_breaker_active = False
risk_manager.daily_circuit_breaker_end_time = None

# Disable weekly protections
risk_manager.weekly_drawdown_level = 0
risk_manager.position_size_multiplier = 1.0
risk_manager.weekly_halt_end_time = None

# Reset equity snapshots
risk_manager.daily_equity_start = risk_manager.get_current_equity()
risk_manager.weekly_equity_start = risk_manager.get_current_equity()
```

---

## 📱 Alert Examples

### Daily Circuit Breaker
```
🚨 DAILY CIRCUIT BREAKER ACTIVATED
Daily equity drawdown: 2.15%
⛔ Trading paused until 2025-10-23 00:01 UTC
⏱️ Countdown: 14h 32m remaining
```

### Weekly Position Reduction
```
⚠️ WEEKLY POSITION SIZE REDUCTION
Weekly equity drawdown: 4.23%
📉 Position size reduced to 50%
🔄 Full size restores after 50% loss recovery
```

### Weekly Halt
```
🚨 WEEKLY TRADING HALT ACTIVATED
Weekly equity drawdown: 6.45%
⛔ Trading halted until Monday 00:01 UTC
⏱️ Countdown: 3d 18h remaining
```

---

## 🔄 Reset Schedule

| Event | Frequency | Action |
|-------|-----------|--------|
| Daily snapshot | Every day 00:01 UTC | Reset daily equity start |
| Weekly snapshot | Every Monday 00:01 UTC | Reset weekly equity start + clear drawdown levels |
| Performance analysis | Daily/Weekly/Monthly | Auto-run after snapshots |

---

## 📈 Key Metrics Tracked

- Total trades, win rate
- Net P&L, profit factor
- Sharpe ratio, expectancy
- Max drawdown, recovery factor
- Largest win/loss
- Consecutive streaks
- Best/worst days
- Average trade duration

---

## 🎯 Protection Flow

```
New Trade Signal
    ↓
Is trading allowed?
    ↓ No → Skip trade
    ↓ Yes
Get position multiplier
    ↓ 0.0 → Skip trade
    ↓ 0.5 → Execute with 50% size
    ↓ 1.0 → Execute with full size
```

---

## 📍 Key File Locations

- Configuration: `settings.py`
- Risk logic: `risk_manager.py`
- Trading integration: `src/core/trading_engine.py`
- Monitor task: `src/main.py`
- Full docs: `docs/EQUITY_RISK_MANAGEMENT.md`

---

## 🚀 Quick Start After Update

1. Verify settings in `settings.py`
2. Restart bot to initialize equity snapshots
3. Watch for first 00:01 UTC snapshot
4. Monitor Telegram for alerts
5. Check daily performance report next morning

---

**Print this card for quick reference during trading hours!**
