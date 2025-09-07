# telegram_alerts.py
import os
import requests
import time
import asyncio
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Rate limiting variables
last_message_time = 0
MIN_MESSAGE_INTERVAL = 0.3  # Minimum 0.3 seconds between messages

def send_telegram_message(msg: str, batch_startup=False):
    """Send Telegram message with rate limiting"""
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
    
    try:
        res = requests.post(url, json=payload, timeout=10)
        res.raise_for_status()
        last_message_time = time.time()
        print(f"✅ Sent: {msg}")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            # Rate limited - wait and retry once
            print(f"⚠️ Telegram rate limited, waiting 2 seconds...")
            time.sleep(2)
            try:
                res = requests.post(url, json=payload, timeout=10)
                res.raise_for_status()
                last_message_time = time.time()
                print(f"✅ Sent (retry): {msg}")
            except Exception as retry_e:
                print(f"❌ Telegram retry failed: {retry_e}")
        else:
            print(f"❌ Telegram HTTP error: {e}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Telegram error: {e}")

async def send_telegram_message_async(msg: str):
    """Async version for use in async contexts"""
    # Run the sync function in a thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, send_telegram_message, msg)
