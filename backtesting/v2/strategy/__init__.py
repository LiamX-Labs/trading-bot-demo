"""
Strategy Layer Module

Trading rules, signal generation, and pump detection
"""

from .rules import TradingStrategy
from .signal_generator import SignalGenerator

__all__ = ['TradingStrategy', 'SignalGenerator']
