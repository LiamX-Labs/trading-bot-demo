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
    """Get current 4-hour interval starting from 12am UTC (00:00)
    
    Intervals: 00:00-04:00, 04:00-08:00, 08:00-12:00, 12:00-16:00, 16:00-20:00, 20:00-00:00
    """
    import settings  # Import settings for configurable start hour
    
    now_utc = datetime.now(timezone.utc)
    
    # Calculate hours since start hour today (default 0 = 12am UTC)
    start_hour = settings.COOLDOWN_START_HOUR_UTC
    today_start = now_utc.replace(hour=start_hour, minute=0, second=0, microsecond=0)
    
    # If current time is before start hour today, use yesterday's start hour
    if now_utc < today_start:
        today_start -= timedelta(days=1)
    
    # Calculate which interval we're in based on cooldown hours setting
    cooldown_hours = settings.SYMBOL_COOLDOWN_HOURS
    hours_since_start = (now_utc - today_start).total_seconds() / 3600
    interval_number = int(hours_since_start // cooldown_hours)
    
    return today_start + timedelta(hours=interval_number * cooldown_hours)


class TradingRestrictions:
    """Manages trading restrictions and cooldowns"""
    
    def __init__(self):
        self.symbol_last_trade_time = {}
        import settings
        self.debug_enabled = settings.DEBUG_COOLDOWN_CHECKS
    
    def can_trade_symbol(self, symbol: str) -> bool:
        """Check if symbol can be traded based on configurable interval cooldown"""
        import settings
        
        if symbol not in self.symbol_last_trade_time:
            if self.debug_enabled:
                print(f"🔄 COOLDOWN ALLOWED: {symbol} - No previous trade recorded")
            return True
        
        current_interval = get_current_4h_interval()
        last_trade_interval = self.symbol_last_trade_time[symbol]
        
        can_trade = current_interval > last_trade_interval
        
        if self.debug_enabled:
            status = "ALLOWED" if can_trade else "BLOCKED"
            print(f"🔄 COOLDOWN {status}: {symbol} - Last: {last_trade_interval}, Current: {current_interval}")
        
        return can_trade
    
    def record_trade_for_symbol(self, symbol: str):
        """Record that a trade was executed for this symbol in current interval"""
        current_interval = get_current_4h_interval()
        self.symbol_last_trade_time[symbol] = current_interval
        
        if self.debug_enabled:
            print(f"🔄 COOLDOWN RECORDED: {symbol} - Interval: {current_interval}")
    
    def cleanup_old_records(self):
        """Clean up old trade records based on settings"""
        import settings
        
        current_time = get_current_4h_interval()
        cutoff_time = current_time - timedelta(hours=settings.COOLDOWN_CLEANUP_HOURS)
        
        symbols_to_remove = [
            symbol for symbol, last_time in self.symbol_last_trade_time.items()
            if last_time < cutoff_time
        ]
        
        if symbols_to_remove and self.debug_enabled:
            print(f"🧹 Cleaning up {len(symbols_to_remove)} old cooldown records")
        
        for symbol in symbols_to_remove:
            del self.symbol_last_trade_time[symbol]
    
    def get_next_trade_time(self, symbol: str) -> datetime:
        """Get the next time this symbol can be traded"""
        import settings
        
        if symbol not in self.symbol_last_trade_time:
            return datetime.now(timezone.utc)  # Can trade immediately
        
        last_interval = self.symbol_last_trade_time[symbol]
        next_interval = last_interval + timedelta(hours=settings.SYMBOL_COOLDOWN_HOURS)
        
        return next_interval


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