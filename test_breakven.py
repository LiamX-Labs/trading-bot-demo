import asyncio
from risk_manager import RiskManager
from collections import defaultdict

async def test_breakeven():
    # Create a fake active_trades dict with your current positions
    # You'll need to update these with your actual positions
    active_trades = {
        # ("SYMBOLUSDT", "Rule X"): None  # Add your positions here
    }
    
    risk_mgr = RiskManager(active_trades, enable_snapshot=False)
    
    print("Running manual breakeven check...")
    await risk_mgr.check_break_even()

if __name__ == "__main__":
    # Run this to manually test: python test_breakeven.py
    asyncio.run(test_breakeven())