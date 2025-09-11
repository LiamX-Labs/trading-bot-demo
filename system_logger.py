# system_logger.py - Comprehensive logging system for CFT Prop Bot

import os
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
import settings

class SystemLogger:
    """
    Daily system logger that creates new log files every day at 12am UTC.
    All system events, trades, errors, and monitoring activities are logged.
    """
    
    def __init__(self):
        self.logs_dir = Path(settings.LOGS_DIRECTORY)
        self.logs_dir.mkdir(exist_ok=True)
        
        # Create logger
        self.logger = logging.getLogger('CFTPropBot')
        self.logger.setLevel(getattr(logging, settings.LOG_LEVEL))
        
        # Remove existing handlers to avoid duplicates
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Set up daily rotating file handler
        self._setup_daily_log_file()
        
        # Set up console handler if enabled
        if settings.CONSOLE_LOGGING_ENABLED:
            self._setup_console_handler()
        
        # Log system startup
        self.info("System Logger initialized")
    
    def _setup_daily_log_file(self):
        """Set up daily log file based on current UTC date"""
        current_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        log_filename = f"cftprop_{current_date}.log"
        log_filepath = self.logs_dir / log_filename
        
        # Create file handler
        file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
        file_handler.setLevel(getattr(logging, settings.LOG_LEVEL))
        
        # Create formatter
        formatter = logging.Formatter(
            fmt=settings.LOG_FORMAT,
            datefmt=settings.LOG_DATE_FORMAT
        )
        file_handler.setFormatter(formatter)
        
        # Add handler to logger
        self.logger.addHandler(file_handler)
        
        # Store current date for rotation check
        self._current_log_date = current_date
        self._file_handler = file_handler
    
    def _setup_console_handler(self):
        """Set up console logging if enabled"""
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, settings.CONSOLE_LOG_LEVEL))
        
        # Simplified formatter for console
        console_formatter = logging.Formatter(
            fmt=settings.CONSOLE_LOG_FORMAT,
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        
        self.logger.addHandler(console_handler)
    
    def _check_and_rotate_log(self):
        """Check if we need to rotate to a new daily log file"""
        current_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
        if current_date != self._current_log_date:
            # Remove old file handler
            self.logger.removeHandler(self._file_handler)
            self._file_handler.close()
            
            # Set up new daily log file
            self._setup_daily_log_file()
            
            self.info(f"Rotated to new daily log file for {current_date}")
    
    def _log(self, level, message, **kwargs):
        """Internal logging method with rotation check"""
        self._check_and_rotate_log()
        
        # Add timestamp and extra context
        timestamp = datetime.now(timezone.utc).strftime('%H:%M:%S.%f')[:-3]
        
        # Add extra context if provided
        extra_info = ""
        if kwargs:
            extra_parts = [f"{k}={v}" for k, v in kwargs.items()]
            extra_info = f" [{', '.join(extra_parts)}]"
        
        formatted_message = f"[{timestamp}] {message}{extra_info}"
        
        getattr(self.logger, level)(formatted_message)
    
    def debug(self, message, **kwargs):
        """Log debug message"""
        self._log('debug', message, **kwargs)
    
    def info(self, message, **kwargs):
        """Log info message"""
        self._log('info', message, **kwargs)
    
    def warning(self, message, **kwargs):
        """Log warning message"""
        self._log('warning', message, **kwargs)
    
    def error(self, message, **kwargs):
        """Log error message"""
        self._log('error', message, **kwargs)
    
    def critical(self, message, **kwargs):
        """Log critical message"""
        self._log('critical', message, **kwargs)
    
    # Specialized logging methods for trading bot events
    
    def log_trade_signal(self, symbol, rule_id, price, action="generated"):
        """Log trading signal events"""
        self.info(f"SIGNAL {action.upper()}: {symbol} | {rule_id} @ {price:.6f}", 
                 symbol=symbol, rule_id=rule_id, price=price, event_type="signal")
    
    def log_trade_execution(self, symbol, rule_id, price, quantity, success=True):
        """Log trade execution events"""
        status = "SUCCESS" if success else "FAILED"
        self.info(f"TRADE {status}: {symbol} ({rule_id}) - Qty: {quantity} @ {price:.6f}",
                 symbol=symbol, rule_id=rule_id, price=price, quantity=quantity, 
                 event_type="execution", success=success)
    
    def log_trade_closure(self, symbol, rule_id, reason, pnl=None):
        """Log trade closure events"""
        pnl_info = f" - PnL: ${pnl:.2f}" if pnl is not None else ""
        self.info(f"TRADE CLOSED: {symbol} ({rule_id}) - Reason: {reason}{pnl_info}",
                 symbol=symbol, rule_id=rule_id, reason=reason, pnl=pnl, 
                 event_type="closure")
    
    def log_breakeven_move(self, symbol, rule_id, success=True):
        """Log breakeven movements"""
        status = "SUCCESS" if success else "FAILED"
        self.info(f"BREAKEVEN {status}: {symbol} ({rule_id})",
                 symbol=symbol, rule_id=rule_id, event_type="breakeven", success=success)
    
    def log_risk_event(self, event_type, details, symbols_affected=None):
        """Log risk management events"""
        symbols_info = f" - Symbols: {symbols_affected}" if symbols_affected else ""
        self.warning(f"RISK EVENT: {event_type} - {details}{symbols_info}",
                    event_type="risk", risk_type=event_type, symbols=symbols_affected)
    
    def log_system_event(self, event_type, details):
        """Log system events (startup, shutdown, errors, etc.)"""
        self.info(f"SYSTEM: {event_type} - {details}",
                 event_type="system", system_event=event_type)
    
    def log_api_error(self, endpoint, error_code, error_message):
        """Log API errors"""
        self.error(f"API ERROR: {endpoint} - Code: {error_code} - {error_message}",
                  endpoint=endpoint, error_code=error_code, event_type="api_error")
    
    def log_websocket_event(self, event_type, details):
        """Log WebSocket events"""
        self.debug(f"WEBSOCKET: {event_type} - {details}",
                  event_type="websocket", ws_event=event_type)
    
    def log_reconciliation(self, tracked_trades, actual_positions, externally_closed):
        """Log position reconciliation results"""
        self.info(f"RECONCILIATION: Tracked: {tracked_trades}, Actual: {actual_positions}, "
                 f"Externally Closed: {len(externally_closed)}",
                 tracked=tracked_trades, actual=actual_positions, 
                 externally_closed=len(externally_closed), event_type="reconciliation")
    
    def log_cooldown_event(self, symbol, can_trade, interval_start):
        """Log cooldown check events"""
        status = "ALLOWED" if can_trade else "BLOCKED"
        self.debug(f"COOLDOWN {status}: {symbol} - Interval: {interval_start}",
                  symbol=symbol, can_trade=can_trade, interval=interval_start,
                  event_type="cooldown")
    
    def get_log_file_path(self, date=None):
        """Get path to log file for specific date (defaults to today)"""
        if date is None:
            date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        return self.logs_dir / f"cftprop_{date}.log"
    
    def cleanup_old_logs(self, days_to_keep):
        """Clean up log files older than specified days"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
        
        for log_file in self.logs_dir.glob("cftprop_*.log"):
            try:
                # Extract date from filename
                date_str = log_file.stem.split('_', 1)[1]
                file_date = datetime.strptime(date_str, '%Y-%m-%d')
                
                if file_date.replace(tzinfo=timezone.utc) < cutoff_date:
                    log_file.unlink()
                    self.info(f"Cleaned up old log file: {log_file.name}")
                    
            except (ValueError, IndexError):
                # Skip files that don't match expected pattern
                continue

# Global logger instance
system_logger = SystemLogger()