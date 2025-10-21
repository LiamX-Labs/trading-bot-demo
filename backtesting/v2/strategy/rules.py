#!/usr/bin/env python3
"""
Trading Strategy Rules for Backtesting
Matches the EXACT live system implementation from src/data/indicators.py
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from typing import Optional, Dict

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from utils.config_loader import StrategyConfig


def calculate_rsi(prices: pd.Series, period: int = 84) -> pd.Series:
    """Calculate RSI indicator"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


class TradingStrategy:
    """
    Implements the EXACT strategy from the live system
    - Requires 8% pump over last 12 bars (1 hour)
    - Only 2 signal rules (Rule 6 and Rule 8)
    """

    def __init__(self, config: Optional[StrategyConfig] = None):
        # Use config system (V2) or fallback to defaults
        if config:
            self.rsi_period = config.rsi_period
            self.volatility_period = config.volatility_period
            self.price_change_period = config.price_change_period
            self.volume_change_period = config.volume_change_period
            self.pump_lookback = config.pump_lookback
            self.pump_threshold = config.pump_threshold
        else:
            # Fallback defaults (matching live system)
            self.rsi_period = 84  # 7 hours
            self.volatility_period = 144  # 12 hours
            self.price_change_period = 144  # 12 hours
            self.volume_change_period = 144  # 12 hours
            self.pump_lookback = 12  # 1 hour
            self.pump_threshold = 8  # 8% pump required

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators matching live system"""
        df = df.copy()

        # RSI with 7-hour period
        df['rsi'] = calculate_rsi(df['close'], self.rsi_period)

        # Volatility calculation (12-hour rolling std of returns)
        returns = df['close'].pct_change() * 100
        df['volatility'] = returns.rolling(self.volatility_period).std()

        # Price spread (high-low as % of close)
        df['spread'] = (df['high'] - df['low']) / df['close'] * 100

        # Price change over 12 hours
        price_change = df['close'].pct_change(self.price_change_period) * 100

        # Volume change over 12 hours
        volume_change = df['volume'].pct_change(self.volume_change_period) * 100

        # Composite score (matches live system exactly)
        df['score'] = (
            (df['rsi'] > 60).astype(int) +
            (volume_change > 50).astype(int) +
            (df['spread'] < 3).astype(int) +
            (df['volatility'] > 0.005).astype(int) +
            (price_change > 5).astype(int)
        )

        return df

    def check_pump_condition(self, df: pd.DataFrame) -> bool:
        """
        Check if pump condition is met
        Requires 8% pump over last 12 bars (1 hour)
        """
        if len(df) <= self.pump_lookback:
            return False

        old_close = df['open'].iloc[-1 - self.pump_lookback]
        new_close = df['close'].iloc[-1]
        pump_pct = (new_close - old_close) / old_close * 100

        return pump_pct >= self.pump_threshold

    def check_rule_6(self, row: pd.Series) -> Optional[Dict]:
        """
        Rule 6: RSI > 55 and Volatility > 0.008
        """
        if row['rsi'] > 55 and row['volatility'] > 0.008:
            return {'side': 'Buy', 'rule': 'Rule 6'}
        return None

    def check_rule_8(self, row: pd.Series) -> Optional[Dict]:
        """
        Rule 8: Score >= 2 and Spread < 4
        """
        if row['score'] >= 2 and row['spread'] < 4:
            return {'side': 'Buy', 'rule': 'Rule 8'}
        return None

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trading signals for entire dataset
        Matches live system EXACTLY:
        1. Check pump condition first (REQUIRED)
        2. Only check Rule 8 and Rule 6

        Returns DataFrame with 'signal_side' and 'signal_rule' columns
        """
        # Ensure minimum data bars (matches live system MIN_DATA_BARS = 150)
        min_bars = max(self.volatility_period, self.rsi_period, 150)
        if len(df) < min_bars:
            # Not enough data, return empty signals
            df['signal_side'] = None
            df['signal_rule'] = None
            return df

        df = self.calculate_indicators(df)

        signals = []

        for idx, row in df.iterrows():
            signal = None

            # Get a slice up to current row for pump check
            df_slice = df.loc[:idx]

            # CRITICAL: Check pump condition first (matches live system)
            if self.check_pump_condition(df_slice):
                # Check Rule 8 first (has priority in live system)
                signal = self.check_rule_8(row)

                # If no Rule 8 signal, check Rule 6
                if not signal:
                    signal = self.check_rule_6(row)

            if signal:
                signals.append({
                    'signal_side': signal['side'],
                    'signal_rule': signal['rule']
                })
            else:
                signals.append({
                    'signal_side': None,
                    'signal_rule': None
                })

        signals_df = pd.DataFrame(signals, index=df.index)
        df = pd.concat([df, signals_df], axis=1)

        return df
