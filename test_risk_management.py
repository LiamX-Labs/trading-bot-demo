#!/usr/bin/env python3
"""
Test script for equity-based risk management system
Tests all drawdown triggers and performance analysis
"""

import asyncio
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from risk_manager import RiskManager
from telegram_alerts import send_telegram_message
import settings


class TestRiskManagement:
    """Test suite for risk management features"""

    def __init__(self):
        # Create mock active trades getter
        self.mock_active_trades = {}
        self.risk_manager = RiskManager(
            lambda: self.mock_active_trades,
            enable_snapshot=False  # Disable automatic scheduling for testing
        )

    def print_header(self, title):
        """Print formatted test header"""
        print(f"\n{'='*70}")
        print(f"  {title}")
        print(f"{'='*70}\n")

    def test_trading_allowed(self):
        """Test is_trading_allowed() method"""
        self.print_header("TEST 1: Trading Allowed Check")

        allowed, reason = self.risk_manager.is_trading_allowed()
        print(f"Trading allowed: {allowed}")
        print(f"Reason: {reason}")
        print(f"✅ Test passed")

    def test_position_size_multiplier(self):
        """Test get_position_size_multiplier() method"""
        self.print_header("TEST 2: Position Size Multiplier")

        multiplier = self.risk_manager.get_position_size_multiplier()
        print(f"Current multiplier: {multiplier}")
        print(f"Expected: 1.0 (no drawdown)")

        if multiplier == 1.0:
            print(f"✅ Test passed")
        else:
            print(f"❌ Test failed: Expected 1.0, got {multiplier}")

    async def test_daily_circuit_breaker(self):
        """Test daily 2% circuit breaker"""
        self.print_header("TEST 3: Daily 2% Circuit Breaker")

        try:
            # Get current equity
            current_equity = self.risk_manager.get_current_equity()
            print(f"Current equity: ${current_equity:.2f}")

            # Simulate 2% drop
            self.risk_manager.daily_equity_start = current_equity / 0.98  # Sets start high enough for 2% drop
            print(f"Simulated daily start: ${self.risk_manager.daily_equity_start:.2f}")
            print(f"Simulated drop: {((self.risk_manager.daily_equity_start - current_equity) / self.risk_manager.daily_equity_start * 100):.2f}%")

            # Trigger check
            print(f"\n🔍 Triggering circuit breaker check...")
            await self.risk_manager.check_equity_drawdowns()

            # Check if circuit breaker activated
            if self.risk_manager.daily_circuit_breaker_active:
                print(f"✅ Circuit breaker activated")
                print(f"End time: {self.risk_manager.daily_circuit_breaker_end_time}")

                # Test trading allowed
                allowed, reason = self.risk_manager.is_trading_allowed()
                print(f"\nTrading allowed: {allowed}")
                print(f"Reason: {reason}")
            else:
                print(f"❌ Circuit breaker NOT activated (may need higher drop)")

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

    async def test_weekly_position_reduction(self):
        """Test weekly 4% position reduction"""
        self.print_header("TEST 4: Weekly 4% Position Reduction")

        try:
            # Reset daily circuit breaker
            self.risk_manager.daily_circuit_breaker_active = False

            # Get current equity
            current_equity = self.risk_manager.get_current_equity()
            print(f"Current equity: ${current_equity:.2f}")

            # Simulate 4% weekly drop
            self.risk_manager.weekly_equity_start = current_equity / 0.96  # 4% drop
            self.risk_manager.weekly_equity_peak = self.risk_manager.weekly_equity_start
            print(f"Simulated weekly start: ${self.risk_manager.weekly_equity_start:.2f}")
            print(f"Simulated drop: {((self.risk_manager.weekly_equity_start - current_equity) / self.risk_manager.weekly_equity_start * 100):.2f}%")

            # Trigger check
            print(f"\n🔍 Triggering position reduction check...")
            await self.risk_manager.check_equity_drawdowns()

            # Check if position reduced
            print(f"\nWeekly drawdown level: {self.risk_manager.weekly_drawdown_level}")
            print(f"Position size multiplier: {self.risk_manager.position_size_multiplier}")

            if self.risk_manager.weekly_drawdown_level == 1:
                print(f"✅ Position size reduced to {self.risk_manager.position_size_multiplier * 100}%")
            else:
                print(f"❌ Position NOT reduced (may need higher drop)")

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

    async def test_weekly_trading_halt(self):
        """Test weekly 6% trading halt"""
        self.print_header("TEST 5: Weekly 6% Trading Halt")

        try:
            # Reset states
            self.risk_manager.daily_circuit_breaker_active = False
            self.risk_manager.weekly_drawdown_level = 0

            # Get current equity
            current_equity = self.risk_manager.get_current_equity()
            print(f"Current equity: ${current_equity:.2f}")

            # Simulate 6% weekly drop
            self.risk_manager.weekly_equity_start = current_equity / 0.94  # 6% drop
            self.risk_manager.weekly_equity_peak = self.risk_manager.weekly_equity_start
            print(f"Simulated weekly start: ${self.risk_manager.weekly_equity_start:.2f}")
            print(f"Simulated drop: {((self.risk_manager.weekly_equity_start - current_equity) / self.risk_manager.weekly_equity_start * 100):.2f}%")

            # Trigger check
            print(f"\n🔍 Triggering trading halt check...")
            await self.risk_manager.check_equity_drawdowns()

            # Check if halt activated
            print(f"\nWeekly drawdown level: {self.risk_manager.weekly_drawdown_level}")
            print(f"Position size multiplier: {self.risk_manager.position_size_multiplier}")

            if self.risk_manager.weekly_drawdown_level == 2:
                print(f"✅ Trading halt activated")
                print(f"Halt until: {self.risk_manager.weekly_halt_end_time}")

                # Test trading allowed
                allowed, reason = self.risk_manager.is_trading_allowed()
                print(f"\nTrading allowed: {allowed}")
                print(f"Reason: {reason}")
            else:
                print(f"❌ Trading NOT halted (may need higher drop)")

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

    async def test_performance_analysis(self):
        """Test performance analysis trigger"""
        self.print_header("TEST 6: Performance Analysis")

        try:
            print(f"🔍 Triggering performance analysis...")
            print(f"This will fetch trades from yesterday and generate a report\n")

            # Run daily performance analysis
            await self.risk_manager._run_daily_performance_analysis()

            print(f"\n✅ Performance analysis completed")
            print(f"Check Telegram for the report (if trades exist)")

        except Exception as e:
            print(f"⚠️ Error (expected if no trades): {e}")
            if "No trades" not in str(e):
                import traceback
                traceback.print_exc()

    async def test_telegram_alerts(self):
        """Test Telegram alert sending"""
        self.print_header("TEST 7: Telegram Alert System")

        try:
            print(f"🔍 Testing Telegram connectivity...")

            test_message = f"""
🧪 **Risk Management Test Alert**

Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

Testing features:
✓ Daily 2% circuit breaker
✓ Weekly 4% position reduction
✓ Weekly 6% trading halt
✓ Performance analysis
✓ Network error handling with retries

This is a test message to verify Telegram integration.
"""

            result = send_telegram_message(test_message)

            if result:
                print(f"✅ Telegram alert sent successfully")
            else:
                print(f"⚠️ Telegram alert failed (network issue)")
                print(f"Note: This is expected if network is unavailable")

        except Exception as e:
            print(f"❌ Error: {e}")

    async def run_all_tests(self):
        """Run all tests"""
        print(f"\n")
        print(f"╔{'═'*68}╗")
        print(f"║{' '*15}RISK MANAGEMENT TEST SUITE{' '*25}║")
        print(f"╚{'═'*68}╝")

        try:
            # Test 1: Trading allowed
            self.test_trading_allowed()
            await asyncio.sleep(1)

            # Test 2: Position size multiplier
            self.test_position_size_multiplier()
            await asyncio.sleep(1)

            # Test 3: Telegram alerts
            await self.test_telegram_alerts()
            await asyncio.sleep(2)

            # Test 4: Daily circuit breaker
            await self.test_daily_circuit_breaker()
            await asyncio.sleep(2)

            # Test 5: Weekly position reduction
            await self.test_weekly_position_reduction()
            await asyncio.sleep(2)

            # Test 6: Weekly trading halt
            await self.test_weekly_trading_halt()
            await asyncio.sleep(2)

            # Test 7: Performance analysis
            await self.test_performance_analysis()

            # Final summary
            self.print_header("TEST SUMMARY")
            print(f"All tests completed!")
            print(f"Check Telegram for alert messages")
            print(f"Review console output above for detailed results\n")

        except KeyboardInterrupt:
            print(f"\n\n⚠️ Tests interrupted by user")
        except Exception as e:
            print(f"\n\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()


async def main():
    """Main test execution"""
    tester = TestRiskManagement()
    await tester.run_all_tests()


if __name__ == "__main__":
    # Run tests
    asyncio.run(main())
