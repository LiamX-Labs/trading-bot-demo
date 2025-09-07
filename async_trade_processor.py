#!/usr/bin/env python3
"""
Async Trade Processor - Demonstrates faster trade execution
This module provides async processing for multiple concurrent trade signals
"""

import asyncio
import time
from datetime import datetime
from typing import List, Dict, Any

# Import the async executor
import sys
from pathlib import Path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

try:
    from src.trading.executor import TradeExecutor
    from telegram_alerts import batch_notifier
    ASYNC_AVAILABLE = True
except ImportError:
    ASYNC_AVAILABLE = False
    print("⚠️ Async modules not available, falling back to synchronous processing")

class AsyncTradeProcessor:
    """Process multiple trade signals concurrently for faster execution"""
    
    def __init__(self):
        self.executor = TradeExecutor() if ASYNC_AVAILABLE else None
        self.trade_queue = asyncio.Queue()
        self.processing = False
        
    async def start_processing(self):
        """Start the async trade processor"""
        self.processing = True
        print("🚀 Async trade processor started")
        
        while self.processing:
            try:
                # Get trade signal from queue (wait up to 1 second)
                trade_signal = await asyncio.wait_for(
                    self.trade_queue.get(), 
                    timeout=1.0
                )
                
                # Process trade immediately
                await self._process_trade_signal(trade_signal)
                
            except asyncio.TimeoutError:
                # No trades in queue, continue
                continue
            except Exception as e:
                print(f"⚠️ Trade processing error: {e}")
    
    def add_trade_signal(self, symbol: str, side: str, price: float, rule_id: str):
        """Add a trade signal to the processing queue"""
        trade_signal = {
            'symbol': symbol,
            'side': side, 
            'price': price,
            'rule_id': rule_id,
            'timestamp': datetime.now()
        }
        
        # Add to queue without blocking
        try:
            self.trade_queue.put_nowait(trade_signal)
            print(f"📥 Queued signal: {symbol} @ {price}")
        except asyncio.QueueFull:
            print(f"⚠️ Trade queue full, dropping signal for {symbol}")
    
    async def _process_trade_signal(self, trade_signal: Dict[str, Any]):
        """Process a single trade signal asynchronously"""
        start_time = time.time()
        
        symbol = trade_signal['symbol']
        side = trade_signal['side']
        price = trade_signal['price']
        rule_id = trade_signal['rule_id']
        
        print(f"⚡ Processing {symbol} signal...")
        
        if not self.executor:
            print(f"❌ Async executor not available for {symbol}")
            return
        
        try:
            # Execute trade asynchronously
            trade_result = await self.executor.open_trade_async(
                symbol, side, price, rule_id
            )
            
            if trade_result:
                execution_time = (time.time() - start_time) * 1000
                print(f"✅ {symbol} executed in {execution_time:.1f}ms")
                
                # Add to batch notification
                batch_notifier.add_trade_alert(
                    symbol, 
                    price, 
                    trade_result['take_profit'], 
                    trade_result['stop_loss'], 
                    rule_id
                )
            else:
                print(f"❌ Failed to execute {symbol}")
                
        except Exception as e:
            print(f"❌ Error executing {symbol}: {e}")
    
    def stop_processing(self):
        """Stop the trade processor"""
        self.processing = False
        print("🛑 Async trade processor stopped")
    
    async def process_batch_signals(self, signals: List[Dict[str, Any]]):
        """Process multiple signals concurrently"""
        print(f"⚡ Processing {len(signals)} signals concurrently...")
        
        start_time = time.time()
        
        # Create tasks for all signals
        tasks = []
        for signal in signals:
            task = asyncio.create_task(self._process_trade_signal(signal))
            tasks.append(task)
        
        # Wait for all to complete
        await asyncio.gather(*tasks, return_exceptions=True)
        
        total_time = (time.time() - start_time) * 1000
        print(f"✅ Batch of {len(signals)} signals processed in {total_time:.1f}ms")
        print(f"📊 Average: {total_time/len(signals):.1f}ms per signal")

# Global async processor instance
async_processor = AsyncTradeProcessor()

# Example usage function
async def demo_async_processing():
    """Demonstrate the async processing speed improvements"""
    print("🚀 Demonstrating async trade processing...")
    
    # Example trade signals (similar to your log output)
    demo_signals = [
        {'symbol': 'GALAUSDT', 'side': 'Buy', 'price': 0.016150, 'rule_id': 'Rule 8'},
        {'symbol': 'VIRTUALUSDT', 'side': 'Buy', 'price': 1.131400, 'rule_id': 'Rule 8'},
        {'symbol': 'PYTHUSDT', 'side': 'Buy', 'price': 0.166500, 'rule_id': 'Rule 8'},
        {'symbol': 'NMRUSDT', 'side': 'Buy', 'price': 18.197000, 'rule_id': 'Rule 8'},
        {'symbol': 'MEMEUSDT', 'side': 'Buy', 'price': 0.002550, 'rule_id': 'Rule 8'},
    ]
    
    # Process all signals concurrently
    await async_processor.process_batch_signals(demo_signals)
    
    # Clean up
    await async_processor.executor.close_session()

if __name__ == "__main__":
    if ASYNC_AVAILABLE:
        print("🚀 Running async trade processing demo...")
        asyncio.run(demo_async_processing())
    else:
        print("❌ Async modules not available. Please ensure all dependencies are installed.")