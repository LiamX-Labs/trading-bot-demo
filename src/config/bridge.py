"""
Configuration bridge to ensure compatibility between old settings.py and new modular config.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import original settings
parent_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(parent_dir))

try:
    # Try to import original settings for any user modifications
    import settings as legacy_settings
    
    # Override new config values with any user modifications from legacy settings
    def sync_legacy_settings():
        """Sync user modifications from legacy settings.py"""
        from .settings import trading_config, data_config
        
        # Check if legacy settings has updated values
        if hasattr(legacy_settings, 'PUMP_THRESHOLD'):
            trading_config.PUMP_THRESHOLD = legacy_settings.PUMP_THRESHOLD
            
        if hasattr(legacy_settings, 'PUMP_LOOKBACK'):
            trading_config.PUMP_LOOKBACK = legacy_settings.PUMP_LOOKBACK
            data_config.PUMP_LOOKBACK = legacy_settings.PUMP_LOOKBACK
            
        if hasattr(legacy_settings, 'BASE_POSITION_SIZE_USD'):
            trading_config.BASE_POSITION_SIZE_USD = legacy_settings.BASE_POSITION_SIZE_USD
            
        if hasattr(legacy_settings, 'TAKEPROFIT_PERCENT'):
            trading_config.TAKEPROFIT_PERCENT = legacy_settings.TAKEPROFIT_PERCENT
            
        if hasattr(legacy_settings, 'STOPLOSS_PERCENT'):
            trading_config.STOPLOSS_PERCENT = legacy_settings.STOPLOSS_PERCENT
            
        if hasattr(legacy_settings, 'TRAIL_ACTIVATION_PERCENT'):
            trading_config.TRAIL_ACTIVATION_PERCENT = legacy_settings.TRAIL_ACTIVATION_PERCENT
            
        if hasattr(legacy_settings, 'TRAIL_OFFSET_PERCENT'):
            trading_config.TRAIL_OFFSET_PERCENT = legacy_settings.TRAIL_OFFSET_PERCENT
        
        print(f"🔄 Synced settings: PUMP_THRESHOLD={trading_config.PUMP_THRESHOLD}")
        
except ImportError:
    def sync_legacy_settings():
        """No legacy settings found, using defaults"""
        print("📋 Using default configuration settings")
        pass