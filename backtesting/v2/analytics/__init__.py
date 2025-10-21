"""
Analytics Module for Backtesting V2

Provides comprehensive performance analysis, chart generation, and PDF reporting.
"""

from .metrics import PerformanceMetrics
from .charts import ChartGenerator
from .reports import ReportGenerator

__all__ = ['PerformanceMetrics', 'ChartGenerator', 'ReportGenerator']
