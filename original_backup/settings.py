# settings.py

from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment variables from .env in project root
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# Bybit endpoint configuration
USE_DEMO = os.getenv("BYBIT_USE_DEMO", "false").lower() == "true"
BASE_URL = "https://api-demo.bybit.com" if USE_DEMO else "https://api.bybit.com"
WS_URL = "wss://stream.bybit.com/v5/public/linear"

# API credentials & request settings
API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")
RECV_WINDOW = "10000"

# Strategy parameters
PUMP_LOOKBACK = 12  # 1 hour = 12 periods of 5min bars
PUMP_THRESHOLD = 8
BASE_POSITION_SIZE_USD = 150
STOPLOSS_PERCENT = 8
TRAIL_ACTIVATION_PERCENT = 20
TRAIL_OFFSET_PERCENT = 10
TAKEPROFIT_PERCENT = 30  # 30% take profit target
BREAKEVEN_THRESHOLD = 8.0  # Changed from 10.0 to 1.0 for testing