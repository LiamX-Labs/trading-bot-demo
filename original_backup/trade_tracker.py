# trade_tracker.py - Lightweight trade persistence for handling bot restarts

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
import threading
import time

class TradeTracker:
    def __init__(self, log_file: str = "trade_log.json"):
        self.log_file = Path(log_file)
        self.pending_events = []
        self.lock = threading.Lock()
        self._ensure_log_file()
        
    def _ensure_log_file(self):
        """Create log file if it doesn't exist"""
        if not self.log_file.exists():
            self._write_to_file({"trade_events": []})
    
    def _write_to_file(self, data: dict):
        """Thread-safe file writing"""
        try:
            with open(self.log_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            print(f"⚠️ Error writing trade log: {e}")
    
    def _read_from_file(self) -> dict:
        """Read trade log file"""
        try:
            if self.log_file.exists():
                with open(self.log_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️ Error reading trade log: {e}")
        return {"trade_events": []}
    
    def log_trade_opened(self, symbol: str, rule_id: str, entry_price: float, 
                        position_size: float, entry_timestamp: datetime = None):
        """Log when a trade is opened"""
        if entry_timestamp is None:
            entry_timestamp = datetime.now(timezone.utc)
            
        event = {
            "timestamp": entry_timestamp.isoformat(),
            "event": "opened",
            "symbol": symbol,
            "rule_id": rule_id,
            "entry_price": entry_price,
            "position_size": position_size
        }
        
        self._add_event(event)
    
    def log_trade_closed(self, symbol: str, rule_id: str, reason: str = "manual"):
        """Log when a trade is closed"""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "closed",
            "symbol": symbol,
            "rule_id": rule_id,
            "reason": reason
        }
        
        self._add_event(event)
    
    def _add_event(self, event: dict):
        """Add event to pending queue and write to file"""
        with self.lock:
            # Read current data
            data = self._read_from_file()
            
            # Add new event
            data["trade_events"].append(event)
            
            # Keep only last 1000 events to prevent file growth
            if len(data["trade_events"]) > 1000:
                data["trade_events"] = data["trade_events"][-1000:]
            
            # Write back to file
            self._write_to_file(data)
    
    def get_active_trades_from_log(self, max_age_hours: int = 168) -> Dict[tuple, dict]:
        """
        Recover active trades from log file.
        Returns trades that were opened but not closed within max_age_hours.
        """
        data = self._read_from_file()
        events = data.get("trade_events", [])
        
        # Cutoff time for considering trades
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        
        # Track opened and closed trades
        opened_trades = {}
        closed_trades = set()
        
        for event in events:
            try:
                timestamp = datetime.fromisoformat(event["timestamp"].replace('Z', '+00:00'))
                
                # Skip very old events
                if timestamp < cutoff_time:
                    continue
                
                symbol = event["symbol"]
                rule_id = event["rule_id"]
                trade_key = (symbol, rule_id)
                
                if event["event"] == "opened":
                    opened_trades[trade_key] = {
                        'entry_timestamp': timestamp,
                        'entry_price': event["entry_price"],
                        'position_size': event["position_size"],
                        'rule_id': rule_id,
                        'expiry_time': timestamp + timedelta(hours=72)  # Your existing 72h rule
                    }
                elif event["event"] == "closed":
                    closed_trades.add(trade_key)
                    
            except Exception as e:
                print(f"⚠️ Error parsing event: {e}")
                continue
        
        # Return only trades that were opened but not closed
        active_trades = {k: v for k, v in opened_trades.items() if k not in closed_trades}
        
        return active_trades
    
    def cleanup_old_events(self, max_age_days: int = 30):
        """Remove events older than max_age_days"""
        with self.lock:
            data = self._read_from_file()
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=max_age_days)
            
            filtered_events = []
            for event in data.get("trade_events", []):
                try:
                    timestamp = datetime.fromisoformat(event["timestamp"].replace('Z', '+00:00'))
                    if timestamp >= cutoff_time:
                        filtered_events.append(event)
                except:
                    continue
            
            data["trade_events"] = filtered_events
            self._write_to_file(data)
            
            print(f"🧹 Cleaned trade log: kept {len(filtered_events)} recent events")


# Global instance
trade_tracker = TradeTracker()


def enhance_active_trades_structure(active_trades: dict) -> dict:
    """
    Convert existing active_trades from simple expiry_time to enhanced structure.
    This maintains backward compatibility with existing code.
    """
    enhanced_trades = {}
    
    for trade_key, value in active_trades.items():
        if isinstance(value, datetime):
            # Old format: just expiry time
            enhanced_trades[trade_key] = {
                'entry_timestamp': None,  # Will be estimated during recovery
                'entry_price': 0.0,
                'position_size': 0.0,
                'rule_id': trade_key[1] if len(trade_key) > 1 else "Unknown",
                'expiry_time': value
            }
        elif isinstance(value, dict):
            # Already enhanced format
            enhanced_trades[trade_key] = value
        else:
            # Fallback
            symbol, rule_id = trade_key
            enhanced_trades[trade_key] = {
                'entry_timestamp': datetime.now(timezone.utc),
                'entry_price': 0.0,
                'position_size': 0.0,
                'rule_id': rule_id,
                'expiry_time': datetime.now(timezone.utc) + timedelta(hours=72)
            }
    
    return enhanced_trades


def get_trade_age_hours(trade_data: dict) -> float:
    """
    Get the age of a trade in hours from its entry timestamp.
    Handles both old and new trade data formats.
    """
    if isinstance(trade_data, dict) and 'entry_timestamp' in trade_data:
        entry_time = trade_data['entry_timestamp']
        if entry_time:
            return (datetime.now(timezone.utc) - entry_time).total_seconds() / 3600
    
    # Fallback: estimate from expiry time (assuming 72h trades)
    if isinstance(trade_data, dict) and 'expiry_time' in trade_data:
        expiry_time = trade_data['expiry_time']
        estimated_entry = expiry_time - timedelta(hours=72)
        return (datetime.now(timezone.utc) - estimated_entry).total_seconds() / 3600
    elif isinstance(trade_data, datetime):
        # Old format: trade_data is expiry_time
        estimated_entry = trade_data - timedelta(hours=72)
        return (datetime.now(timezone.utc) - estimated_entry).total_seconds() / 3600
    
    return 0.0


def get_trade_expiry(trade_data: dict) -> datetime:
    """
    Get expiry time from trade data, maintaining compatibility with existing code.
    """
    if isinstance(trade_data, dict):
        return trade_data.get('expiry_time', datetime.now(timezone.utc) + timedelta(hours=72))
    elif isinstance(trade_data, datetime):
        return trade_data  # Old format
    else:
        return datetime.now(timezone.utc) + timedelta(hours=72)