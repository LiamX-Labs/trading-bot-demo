"""
Utility functions and helper classes.
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime, timezone, timedelta
from typing import Set


def safe_float(value, default=0.0):
    """Safely convert value to float, handling empty strings and None"""
    if value is None or value == '':
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def create_optimized_session():
    """Create an optimized requests session with connection pooling"""
    session = requests.Session()
    
    retry_strategy = Retry(
        total=2,
        backoff_factor=0.1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    
    adapter = HTTPAdapter(
        pool_connections=10,
        pool_maxsize=20,
        max_retries=retry_strategy
    )
    
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session


def get_current_4h_interval() -> datetime:
    """Get current 4-hour interval starting from 3am UTC"""
    now_utc = datetime.now(timezone.utc)
    
    # Calculate hours since 3am today
    today_3am = now_utc.replace(hour=3, minute=0, second=0, microsecond=0)
    
    # If current time is before 3am today, use yesterday's 3am
    if now_utc < today_3am:
        today_3am -= timedelta(days=1)
    
    # Calculate which 4-hour interval we're in
    hours_since_3am = (now_utc - today_3am).total_seconds() / 3600
    interval_number = int(hours_since_3am // 4)
    
    return today_3am + timedelta(hours=interval_number * 4)


class TradingRestrictions:
    """Manages trading restrictions and cooldowns"""
    
    def __init__(self):
        self.symbol_last_trade_time = {}
    
    def can_trade_symbol(self, symbol: str) -> bool:
        """Check if symbol can be traded based on 4-hour interval cooldown"""
        if symbol not in self.symbol_last_trade_time:
            return True
        
        current_interval = get_current_4h_interval()
        last_trade_interval = self.symbol_last_trade_time[symbol]
        
        return current_interval > last_trade_interval
    
    def record_trade_for_symbol(self, symbol: str):
        """Record that a trade was executed for this symbol in current interval"""
        self.symbol_last_trade_time[symbol] = get_current_4h_interval()
    
    def cleanup_old_records(self):
        """Clean up old trade records (older than 24 hours)"""
        current_time = get_current_4h_interval()
        cutoff_time = current_time - timedelta(hours=24)
        
        symbols_to_remove = [
            symbol for symbol, last_time in self.symbol_last_trade_time.items()
            if last_time < cutoff_time
        ]
        
        for symbol in symbols_to_remove:
            del self.symbol_last_trade_time[symbol]


def format_timestamp(dt: datetime) -> str:
    """Format datetime for logging"""
    return dt.strftime('%H:%M:%S')


def calculate_pnl_percentage(entry_price: float, current_price: float) -> float:
    """Calculate PnL percentage for a long position"""
    if entry_price <= 0:
        return 0.0
    return ((current_price - entry_price) / entry_price) * 100


def is_market_hours() -> bool:
    """Check if it's crypto market hours (always true for crypto)"""
    return True  # Crypto markets are 24/7


def truncate_string(text: str, max_length: int = 100) -> str:
    """Truncate string to maximum length"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."