#!/usr/bin/env python3
"""
Performance Metrics Calculator

Calculates comprehensive trading performance metrics from trade history.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from datetime import datetime


class PerformanceMetrics:
    """Calculate comprehensive performance metrics from trade data"""

    def __init__(self, trades_df: pd.DataFrame, initial_balance: float):
        self.trades_df = trades_df.copy()
        self.initial_balance = initial_balance
        self.metrics = {}

    def calculate_all_metrics(self) -> Dict:
        """Calculate all performance metrics"""

        if self.trades_df.empty:
            return self._empty_metrics()

        # Ensure exit_time is datetime
        if 'exit_time' in self.trades_df.columns:
            self.trades_df['exit_time'] = pd.to_datetime(self.trades_df['exit_time'], unit='ms', errors='coerce')

        # Sort by exit time
        self.trades_df = self.trades_df.sort_values('exit_time')

        # Calculate equity curve
        self.trades_df['cumulative_pnl'] = self.trades_df['net_pnl'].cumsum()
        self.trades_df['equity'] = self.initial_balance + self.trades_df['cumulative_pnl']

        # Core metrics
        self._calculate_basic_metrics()
        self._calculate_win_loss_metrics()
        self._calculate_drawdown_metrics()
        self._calculate_risk_metrics()
        self._calculate_duration_metrics()
        self._calculate_exit_metrics()

        return self.metrics

    def _empty_metrics(self) -> Dict:
        """Return metrics for empty trade history"""
        return {
            'initial_balance': self.initial_balance,
            'final_balance': self.initial_balance,
            'total_pnl': 0.0,
            'total_return_pct': 0.0,
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'breakeven_trades': 0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'avg_trade': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'max_drawdown': 0.0,
            'max_drawdown_pct': 0.0,
        }

    def _calculate_basic_metrics(self):
        """Calculate basic P&L metrics"""
        final_balance = self.trades_df['equity'].iloc[-1]
        total_pnl = final_balance - self.initial_balance
        total_return_pct = (total_pnl / self.initial_balance) * 100

        self.metrics['initial_balance'] = self.initial_balance
        self.metrics['final_balance'] = final_balance
        self.metrics['total_pnl'] = total_pnl
        self.metrics['total_return_pct'] = total_return_pct
        self.metrics['total_trades'] = len(self.trades_df)

    def _calculate_win_loss_metrics(self):
        """Calculate win/loss statistics"""
        wins = self.trades_df[self.trades_df['net_pnl'] > 0]
        losses = self.trades_df[self.trades_df['net_pnl'] < 0]
        breakevens = self.trades_df[self.trades_df['net_pnl'] == 0]

        total_trades = len(self.trades_df)
        winning_trades = len(wins)
        losing_trades = len(losses)
        breakeven_trades = len(breakevens)

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        # Win strike rate (>0.5% return)
        win_strike = len(self.trades_df[self.trades_df['return_pct'] > 0.5])
        win_strike_rate = (win_strike / total_trades * 100) if total_trades > 0 else 0

        # Loss strike rate (<-0.5% return)
        loss_strike = len(self.trades_df[self.trades_df['return_pct'] < -0.5])
        loss_strike_rate = (loss_strike / total_trades * 100) if total_trades > 0 else 0

        # Breakeven rate (within ±0.5%)
        be_strike = len(self.trades_df[(self.trades_df['return_pct'] >= -0.5) &
                                       (self.trades_df['return_pct'] <= 0.5)])
        be_strike_rate = (be_strike / total_trades * 100) if total_trades > 0 else 0

        avg_win = wins['net_pnl'].mean() if len(wins) > 0 else 0
        avg_loss = losses['net_pnl'].mean() if len(losses) > 0 else 0
        avg_trade = self.trades_df['net_pnl'].mean()

        # Profit factor
        gross_profit = wins['net_pnl'].sum() if len(wins) > 0 else 0
        gross_loss = abs(losses['net_pnl'].sum()) if len(losses) > 0 else 0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

        # Expectancy
        expectancy = avg_trade if total_trades > 0 else 0

        self.metrics['winning_trades'] = winning_trades
        self.metrics['losing_trades'] = losing_trades
        self.metrics['breakeven_trades'] = breakeven_trades
        self.metrics['win_rate'] = win_rate
        self.metrics['win_strike_rate'] = win_strike_rate
        self.metrics['loss_strike_rate'] = loss_strike_rate
        self.metrics['breakeven_strike_rate'] = be_strike_rate
        self.metrics['avg_win'] = avg_win
        self.metrics['avg_loss'] = avg_loss
        self.metrics['avg_trade'] = avg_trade
        self.metrics['gross_profit'] = gross_profit
        self.metrics['gross_loss'] = gross_loss
        self.metrics['profit_factor'] = profit_factor
        self.metrics['expectancy'] = expectancy

    def _calculate_drawdown_metrics(self):
        """Calculate drawdown statistics"""
        self.trades_df['running_max'] = self.trades_df['equity'].cummax()
        self.trades_df['drawdown'] = self.trades_df['equity'] - self.trades_df['running_max']
        self.trades_df['drawdown_pct'] = (self.trades_df['drawdown'] / self.trades_df['running_max']) * 100

        max_drawdown = self.trades_df['drawdown'].min()
        max_drawdown_pct = self.trades_df['drawdown_pct'].min()

        # Find drawdown duration
        in_drawdown = self.trades_df['drawdown'] < 0
        if in_drawdown.any():
            # Find longest drawdown period
            drawdown_groups = (in_drawdown != in_drawdown.shift()).cumsum()
            drawdown_periods = self.trades_df[in_drawdown].groupby(drawdown_groups).size()
            max_drawdown_duration = drawdown_periods.max() if len(drawdown_periods) > 0 else 0
        else:
            max_drawdown_duration = 0

        self.metrics['max_drawdown'] = abs(max_drawdown)
        self.metrics['max_drawdown_pct'] = abs(max_drawdown_pct)
        self.metrics['max_drawdown_duration'] = max_drawdown_duration

    def _calculate_risk_metrics(self):
        """Calculate risk-adjusted metrics"""
        returns = self.trades_df['return_pct']

        # Sharpe ratio (simplified, using trade returns)
        if len(returns) > 1:
            avg_return = returns.mean()
            std_return = returns.std()
            sharpe = (avg_return / std_return) if std_return > 0 else 0
        else:
            sharpe = 0

        # Sortino ratio (using only downside deviation)
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 1:
            downside_std = downside_returns.std()
            sortino = (returns.mean() / downside_std) if downside_std > 0 else 0
        else:
            sortino = 0

        # Calmar ratio (return / max drawdown)
        if self.metrics['max_drawdown_pct'] != 0:
            calmar = abs(self.metrics['total_return_pct'] / self.metrics['max_drawdown_pct'])
        else:
            calmar = 0

        # Commission costs
        total_commission = self.trades_df['total_commission'].sum() if 'total_commission' in self.trades_df.columns else 0
        commission_pct = (total_commission / self.initial_balance * 100) if self.initial_balance > 0 else 0

        self.metrics['sharpe_ratio'] = sharpe
        self.metrics['sortino_ratio'] = sortino
        self.metrics['calmar_ratio'] = calmar
        self.metrics['total_commission_paid'] = total_commission
        self.metrics['commission_pct'] = commission_pct

    def _calculate_duration_metrics(self):
        """Calculate trade duration statistics"""
        if 'duration_hours' in self.trades_df.columns:
            durations = self.trades_df['duration_hours']
            avg_duration = durations.mean()
            max_duration = durations.max()
            min_duration = durations.min()
        else:
            avg_duration = max_duration = min_duration = 0

        self.metrics['avg_trade_duration_hours'] = avg_duration
        self.metrics['max_trade_duration_hours'] = max_duration
        self.metrics['min_trade_duration_hours'] = min_duration

    def _calculate_exit_metrics(self):
        """Calculate exit reason statistics"""
        if 'exit_reason' in self.trades_df.columns:
            exit_counts = self.trades_df['exit_reason'].value_counts().to_dict()
            self.metrics['exit_reasons'] = exit_counts
        else:
            self.metrics['exit_reasons'] = {}

        # Pyramiding statistics
        if 'entry_count' in self.trades_df.columns:
            pyramided = self.trades_df[self.trades_df['entry_count'] > 1]
            self.metrics['pyramided_positions'] = len(pyramided)
            self.metrics['pyramiding_rate'] = (len(pyramided) / len(self.trades_df) * 100) if len(self.trades_df) > 0 else 0
            self.metrics['avg_entries_per_trade'] = self.trades_df['entry_count'].mean()
        else:
            self.metrics['pyramided_positions'] = 0
            self.metrics['pyramiding_rate'] = 0
            self.metrics['avg_entries_per_trade'] = 1.0

    def get_metrics_summary(self) -> str:
        """Get formatted metrics summary"""
        if not self.metrics:
            self.calculate_all_metrics()

        lines = [
            "=" * 70,
            "PERFORMANCE METRICS SUMMARY",
            "=" * 70,
            "",
            "📊 Core Metrics:",
            f"   Initial Balance: ${self.metrics['initial_balance']:,.2f}",
            f"   Final Balance: ${self.metrics['final_balance']:,.2f}",
            f"   Total P&L: ${self.metrics['total_pnl']:,.2f}",
            f"   Total Return: {self.metrics['total_return_pct']:.2f}%",
            "",
            "🎯 Trade Statistics:",
            f"   Total Trades: {self.metrics['total_trades']}",
            f"   Winning Trades: {self.metrics['winning_trades']} ({self.metrics['win_rate']:.1f}%)",
            f"   Losing Trades: {self.metrics['losing_trades']}",
            f"   Breakeven Trades: {self.metrics['breakeven_trades']}",
            "",
            "💰 Win/Loss Analysis:",
            f"   Average Win: ${self.metrics['avg_win']:.2f}",
            f"   Average Loss: ${self.metrics['avg_loss']:.2f}",
            f"   Average Trade: ${self.metrics['avg_trade']:.2f}",
            f"   Profit Factor: {self.metrics['profit_factor']:.2f}",
            f"   Expectancy: ${self.metrics['expectancy']:.2f}",
            "",
            "📉 Risk Metrics:",
            f"   Max Drawdown: ${self.metrics['max_drawdown']:,.2f} ({self.metrics['max_drawdown_pct']:.2f}%)",
            f"   Sharpe Ratio: {self.metrics['sharpe_ratio']:.2f}",
            f"   Sortino Ratio: {self.metrics['sortino_ratio']:.2f}",
            f"   Calmar Ratio: {self.metrics['calmar_ratio']:.2f}",
            "",
            "💸 Costs:",
            f"   Total Commission: ${self.metrics['total_commission_paid']:.2f}",
            f"   Commission %: {self.metrics['commission_pct']:.3f}%",
            "",
            "=" * 70,
        ]

        return "\n".join(lines)
