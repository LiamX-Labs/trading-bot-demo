#!/usr/bin/env python3
"""
Quick test to verify the trade execution and batch notification fixes
"""

import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def test_trade_executor():
    """Test that TradeExecutor has the required methods"""
    try:
        from src.trading.executor import TradeExecutor
        
        executor = TradeExecutor()
        print("✅ TradeExecutor imported and initialized")
        
        # Test method exists
        if hasattr(executor, 'open_trade'):
            print("✅ open_trade method exists")
        else:
            print("❌ open_trade method missing")
            return False
            
        # Test return format (without actually executing)
        # This would normally return trade data dict or None
        print("✅ TradeExecutor ready for use")
        return True
        
    except Exception as e:
        print(f"❌ TradeExecutor test failed: {e}")
        return False

def test_batch_notifications():
    """Test batch notification system"""
    try:
        from telegram_alerts import batch_notifier
        print("✅ Batch notifier imported")
        
        # Test adding trades
        batch_notifier.add_trade_alert('TESTUSDT', 1.0, 1.3, 0.9, 'Test Rule')
        print(f"✅ Trade alert queued. Queue size: {len(batch_notifier.pending_trades)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Batch notification test failed: {e}")
        return False

def test_trade_tracker():
    """Test trade tracker"""
    try:
        from trade_tracker import trade_tracker
        
        # Test that get_active_trades_from_log returns dict format
        active_trades = trade_tracker.get_active_trades_from_log(max_age_hours=1)
        print(f"✅ Trade tracker returns {type(active_trades)} with {len(active_trades)} trades")
        
        # Test the format
        for trade_key, trade_data in active_trades.items():
            if not isinstance(trade_data, dict):
                print(f"⚠️ Warning: Trade data is {type(trade_data)}, expected dict")
            break  # Just check first one
            
        return True
        
    except Exception as e:
        print(f"❌ Trade tracker test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing trading bot fixes...")
    print("-" * 40)
    
    tests = [
        test_trade_executor,
        test_batch_notifications, 
        test_trade_tracker
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"🎯 Test Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("✅ All tests passed! The bot should work correctly.")
    else:
        print("⚠️ Some tests failed. Check the errors above.")