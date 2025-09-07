"""
Technical indicators and signal generation.
"""

import pandas as pd
from ta.momentum import RSIIndicator
from typing import Dict, Any, Optional, Tuple

from ..config.settings import data_config, trading_config


class TechnicalAnalyzer:
    """Technical analysis and signal generation"""
    
    @staticmethod
    def apply_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Apply technical indicators to price data"""
        # RSI with converted period for 5min bars
        df["rsi"] = RSIIndicator(df["close"], window=data_config.RSI_PERIOD).rsi()
        
        # Volatility calculation
        returns = df["close"].pct_change() * 100
        df["volatility"] = returns.rolling(data_config.VOLATILITY_PERIOD).std()
        
        # Price spread
        df["spread"] = (df["high"] - df["low"]) / df["close"] * 100
        
        # Price and volume changes
        price_change = df["close"].pct_change(data_config.PRICE_CHANGE_PERIOD) * 100
        volume_change = df["volume"].pct_change(data_config.VOLUME_CHANGE_PERIOD) * 100
        
        # Composite score
        df["score"] = (
            (df["rsi"] > 60).astype(int) +
            (volume_change > 50).astype(int) +
            (df["spread"] < 3).astype(int) +
            (df["volatility"] > 0.005).astype(int) +
            (price_change > 5).astype(int)
        )
        
        return df
    
    @staticmethod
    def check_pump_condition(df: pd.DataFrame) -> bool:
        """Check if pump condition is met"""
        if len(df) <= trading_config.PUMP_LOOKBACK:
            return False
            
        old_close = df["open"].iloc[-1 - trading_config.PUMP_LOOKBACK]
        new_close = df["close"].iloc[-1]
        pump_pct = (new_close - old_close) / old_close * 100
        
        return pump_pct >= trading_config.PUMP_THRESHOLD
    
    @staticmethod
    def generate_signal(df: pd.DataFrame) -> Optional[str]:
        """Generate trading signals based on technical conditions"""
        if len(df) < data_config.MIN_DATA_BARS:
            return None
            
        # Check pump condition first
        if not TechnicalAnalyzer.check_pump_condition(df):
            return None
            
        # Apply indicators
        df_with_indicators = TechnicalAnalyzer.apply_indicators(df)
        row = df_with_indicators.iloc[-1]
        
        # Signal rules
        if row["score"] >= 2 and row["spread"] < 4:
            return "Rule 8"
        elif row["rsi"] > 55 and row["volatility"] > 0.008:
            return "Rule 6"
            
        return None
    
    @staticmethod
    def get_signal_data(df: pd.DataFrame) -> Dict[str, Any]:
        """Get comprehensive signal data for a symbol"""
        if len(df) < data_config.MIN_DATA_BARS:
            return {}
            
        df_with_indicators = TechnicalAnalyzer.apply_indicators(df)
        row = df_with_indicators.iloc[-1]
        
        return {
            "close_price": row["close"],
            "rsi": row["rsi"],
            "volatility": row["volatility"],
            "spread": row["spread"],
            "score": row["score"],
            "timestamp": row.get("timestamp", ""),
            "has_pump": TechnicalAnalyzer.check_pump_condition(df)
        }