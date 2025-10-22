# telegram_alerts.py
import os
import requests
import time
import asyncio
from datetime import datetime, timedelta
from collections import deque
from typing import List
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("📋 Using environment variables directly (dotenv not installed)")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Rate limiting variables
last_message_time = 0
MIN_MESSAGE_INTERVAL = 0.3  # Minimum 0.3 seconds between messages

# Batch notification system
class TelegramBatchNotifier:
    def __init__(self):
        self.pending_trades = deque()
        self.batch_timeout = 5.0  # Send batch after 5 seconds
        self.max_batch_size = 10  # Maximum trades per batch
        self.last_batch_time = None
        self.batch_task = None
    
    def add_trade_alert(self, symbol: str, entry_price: float, tp_price: float, sl_price: float, rule_id: str):
        """Add a trade alert to the batch queue"""
        trade_info = {
            'symbol': symbol,
            'entry_price': entry_price,
            'tp_price': tp_price,
            'sl_price': sl_price,
            'rule_id': rule_id,
            'timestamp': datetime.now()
        }
        
        self.pending_trades.append(trade_info)
        
        # Try to start batch timer if event loop is running
        try:
            loop = asyncio.get_running_loop()
            
            # Start batch timer if not already running
            if not self.batch_task or self.batch_task.done():
                self.batch_task = asyncio.create_task(self._batch_timer())
            
            # Send immediately if batch is full
            if len(self.pending_trades) >= self.max_batch_size:
                if self.batch_task and not self.batch_task.done():
                    self.batch_task.cancel()
                asyncio.create_task(self._send_batch())
                
        except RuntimeError:
            # No event loop running, send immediately with sync method
            if len(self.pending_trades) >= self.max_batch_size:
                self._send_batch_sync()
    
    async def _batch_timer(self):
        """Wait for timeout then send batch"""
        try:
            await asyncio.sleep(self.batch_timeout)
            await self._send_batch()
        except asyncio.CancelledError:
            pass  # Task was cancelled, batch will be sent by another trigger
    
    async def _send_batch(self):
        """Send all pending trade alerts as a batch"""
        if not self.pending_trades:
            return
            
        trades_to_send = list(self.pending_trades)
        self.pending_trades.clear()
        
        if len(trades_to_send) == 1:
            # Send single trade normally
            trade = trades_to_send[0]
            msg = (
                f"🚨 Trade Alert: {trade['symbol']}\n"
                f"Entry: {trade['entry_price']} | TP: {trade['tp_price']} | SL: {trade['sl_price']}\n"
                f"Rule: {trade['rule_id']}"
            )
        else:
            # Send batch message
            msg_lines = [f"🚨 **{len(trades_to_send)} New Trades Opened:**"]
            
            for i, trade in enumerate(trades_to_send, 1):
                msg_lines.append(
                    f"{i}. **{trade['symbol']}** | Entry: {trade['entry_price']} | "
                    f"TP: {trade['tp_price']} | SL: {trade['sl_price']} | {trade['rule_id']}"
                )
            
            msg = "\n".join(msg_lines)
        
        await send_telegram_message_async(msg)
    
    def _send_batch_sync(self):
        """Send all pending trade alerts synchronously"""
        if not self.pending_trades:
            return
            
        trades_to_send = list(self.pending_trades)
        self.pending_trades.clear()
        
        if len(trades_to_send) == 1:
            # Send single trade normally
            trade = trades_to_send[0]
            msg = (
                f"🚨 Trade Alert: {trade['symbol']}\n"
                f"Entry: {trade['entry_price']} | TP: {trade['tp_price']} | SL: {trade['sl_price']}\n"
                f"Rule: {trade['rule_id']}"
            )
        else:
            # Send batch message
            msg_lines = [f"🚨 **{len(trades_to_send)} New Trades Opened:**"]
            
            for i, trade in enumerate(trades_to_send, 1):
                msg_lines.append(
                    f"{i}. **{trade['symbol']}** | Entry: {trade['entry_price']} | "
                    f"TP: {trade['tp_price']} | SL: {trade['sl_price']} | {trade['rule_id']}"
                )
            
            msg = "\n".join(msg_lines)
        
        send_telegram_message(msg)

# Global batch notifier instance
batch_notifier = TelegramBatchNotifier()

def send_telegram_message(msg: str, batch_startup=False, max_retries=3):
    """Send Telegram message with rate limiting and retry logic"""
    global last_message_time

    # Rate limiting: ensure minimum interval between messages
    current_time = time.time()
    time_since_last = current_time - last_message_time

    if time_since_last < MIN_MESSAGE_INTERVAL:
        sleep_time = MIN_MESSAGE_INTERVAL - time_since_last
        time.sleep(sleep_time)

    url = f"{BASE_URL}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown",
    }

    for attempt in range(max_retries):
        try:
            res = requests.post(url, json=payload, timeout=10)
            res.raise_for_status()
            last_message_time = time.time()
            if attempt > 0:
                print(f"✅ Telegram sent (attempt {attempt + 1})")
            return True

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                # Rate limited - exponential backoff
                wait_time = 2 ** attempt
                print(f"⚠️ Telegram rate limited, waiting {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue
            else:
                print(f"❌ Telegram HTTP error {e.response.status_code}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                return False

        except requests.exceptions.ConnectionError as e:
            print(f"⚠️ Telegram connection error (attempt {attempt + 1}/{max_retries}): Network unreachable")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            return False

        except requests.exceptions.Timeout as e:
            print(f"⚠️ Telegram timeout (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return False

        except requests.exceptions.RequestException as e:
            print(f"❌ Telegram error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return False

    print(f"❌ Failed to send Telegram message after {max_retries} attempts")
    return False

async def send_telegram_message_async(msg: str):
    """Async version for use in async contexts"""
    # Run the sync function in a thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, send_telegram_message, msg)
