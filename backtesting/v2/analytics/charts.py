#!/usr/bin/env python3
"""
Chart Generator

Generates performance visualization charts for backtest results.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict


class ChartGenerator:
    """Generate performance visualization charts"""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def create_equity_curve(self, trades_df: pd.DataFrame, initial_balance: float) -> Optional[Path]:
        """Create equity curve chart"""
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
        except ImportError:
            print("⚠️ matplotlib not installed. Skipping equity curve chart.")
            return None

        if trades_df.empty:
            return None

        # Prepare data
        trades_df = trades_df.copy()
        # Convert exit_time to datetime first (handles mixed types and timezones)
        trades_df['exit_time'] = pd.to_datetime(trades_df['exit_time'], errors='coerce', utc=True)
        # Filter out NaT values
        trades_df = trades_df.dropna(subset=['exit_time'])
        # Remove timezone for matplotlib compatibility
        trades_df['exit_time'] = trades_df['exit_time'].dt.tz_localize(None)
        trades_df = trades_df.sort_values('exit_time')
        trades_df['cumulative_pnl'] = trades_df['net_pnl'].cumsum()
        trades_df['equity'] = initial_balance + trades_df['cumulative_pnl']

        # Create figure
        fig, ax = plt.subplots(figsize=(12, 6))

        # Plot equity curve
        ax.plot(trades_df['exit_time'], trades_df['equity'],
               linewidth=2, color='#2E86AB', label='Equity', zorder=3)

        # Initial balance line
        ax.axhline(y=initial_balance, color='gray',
                  linestyle='--', alpha=0.5, label='Initial Balance', zorder=1)

        # Fill areas
        ax.fill_between(trades_df['exit_time'], trades_df['equity'], initial_balance,
                       where=(trades_df['equity'] >= initial_balance),
                       color='#06A77D', alpha=0.2, zorder=2)
        ax.fill_between(trades_df['exit_time'], trades_df['equity'], initial_balance,
                       where=(trades_df['equity'] < initial_balance),
                       color='#D62246', alpha=0.2, zorder=2)

        # Styling
        ax.set_xlabel('Date', fontsize=11)
        ax.set_ylabel('Equity ($)', fontsize=11)
        ax.set_title('Backtest Equity Curve', fontsize=14, fontweight='bold')
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)

        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.xticks(rotation=45)

        # Format y-axis
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

        plt.tight_layout()

        # Save
        filename = f"equity_curve_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        print(f"📊 Generated equity curve: {filepath}")
        return filepath

    def create_drawdown_chart(self, trades_df: pd.DataFrame, initial_balance: float) -> Optional[Path]:
        """Create drawdown chart"""
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
        except ImportError:
            print("⚠️ matplotlib not installed. Skipping drawdown chart.")
            return None

        if trades_df.empty:
            return None

        # Prepare data
        trades_df = trades_df.copy()
        # Convert exit_time to datetime first (handles mixed types and timezones)
        trades_df['exit_time'] = pd.to_datetime(trades_df['exit_time'], errors='coerce', utc=True)
        # Filter out NaT values
        trades_df = trades_df.dropna(subset=['exit_time'])
        # Remove timezone for matplotlib compatibility
        trades_df['exit_time'] = trades_df['exit_time'].dt.tz_localize(None)
        trades_df = trades_df.sort_values('exit_time')
        trades_df['cumulative_pnl'] = trades_df['net_pnl'].cumsum()
        trades_df['equity'] = initial_balance + trades_df['cumulative_pnl']
        trades_df['running_max'] = trades_df['equity'].cummax()
        trades_df['drawdown'] = trades_df['equity'] - trades_df['running_max']
        trades_df['drawdown_pct'] = (trades_df['drawdown'] / trades_df['running_max'] * 100)

        # Create figure
        fig, ax = plt.subplots(figsize=(12, 6))

        # Plot drawdown
        ax.fill_between(trades_df['exit_time'], trades_df['drawdown_pct'],
                       0, color='#A23B72', alpha=0.6, zorder=2)
        ax.plot(trades_df['exit_time'], trades_df['drawdown_pct'],
               linewidth=1.5, color='#A23B72', zorder=3)

        # Styling
        ax.set_xlabel('Date', fontsize=11)
        ax.set_ylabel('Drawdown (%)', fontsize=11)
        ax.set_title('Drawdown Analysis', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)

        # Format axes
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.xticks(rotation=45)

        # Mark maximum drawdown
        max_dd_idx = trades_df['drawdown_pct'].idxmin()
        max_dd_value = trades_df.loc[max_dd_idx, 'drawdown_pct']
        max_dd_date = trades_df.loc[max_dd_idx, 'exit_time']
        ax.scatter([max_dd_date], [max_dd_value], color='red', s=100, zorder=4, label=f'Max DD: {max_dd_value:.2f}%')
        ax.legend(loc='lower right')

        plt.tight_layout()

        # Save
        filename = f"drawdown_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        print(f"📊 Generated drawdown chart: {filepath}")
        return filepath

    def create_pnl_distribution(self, trades_df: pd.DataFrame) -> Optional[Path]:
        """Create P&L distribution chart"""
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
        except ImportError:
            print("⚠️ matplotlib not installed. Skipping P&L distribution chart.")
            return None

        if trades_df.empty:
            return None

        # Separate wins and losses
        wins = trades_df[trades_df['net_pnl'] > 0]['net_pnl']
        losses = trades_df[trades_df['net_pnl'] < 0]['net_pnl']
        breakevens = trades_df[trades_df['net_pnl'] == 0]

        # Create figure with 2 subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

        # Histogram
        bins = 30
        if len(wins) > 0:
            ax1.hist(wins, bins=bins, color='#06A77D', alpha=0.7, label=f'Wins ({len(wins)})', edgecolor='black')
        if len(losses) > 0:
            ax1.hist(losses, bins=bins, color='#D62246', alpha=0.7, label=f'Losses ({len(losses)})', edgecolor='black')

        ax1.set_xlabel('P&L ($)', fontsize=11)
        ax1.set_ylabel('Frequency', fontsize=11)
        ax1.set_title('P&L Distribution', fontsize=12, fontweight='bold')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        ax1.axvline(x=0, color='black', linestyle='--', linewidth=1)

        # Pie chart
        win_count = len(wins)
        loss_count = len(losses)
        be_count = len(breakevens)

        sizes = [win_count, loss_count, be_count]
        labels = [f"Wins\n{win_count}\n({win_count/len(trades_df)*100:.1f}%)",
                 f"Losses\n{loss_count}\n({loss_count/len(trades_df)*100:.1f}%)",
                 f"Breakeven\n{be_count}\n({be_count/len(trades_df)*100:.1f}%)"]
        colors = ['#06A77D', '#D62246', '#FFA500']

        # Remove zero slices
        non_zero = [(s, l, c) for s, l, c in zip(sizes, labels, colors) if s > 0]
        if non_zero:
            sizes, labels, colors = zip(*non_zero)
            ax2.pie(sizes, labels=labels, colors=colors, startangle=90, textprops={'fontsize': 10})
            ax2.set_title('Win/Loss/Breakeven Ratio', fontsize=12, fontweight='bold')

        plt.tight_layout()

        # Save
        filename = f"pnl_distribution_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        print(f"📊 Generated P&L distribution: {filepath}")
        return filepath

    def create_exit_reasons_chart(self, trades_df: pd.DataFrame) -> Optional[Path]:
        """Create exit reasons breakdown chart"""
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
        except ImportError:
            print("⚠️ matplotlib not installed. Skipping exit reasons chart.")
            return None

        if trades_df.empty or 'exit_reason' not in trades_df.columns:
            return None

        # Count exit reasons
        exit_counts = trades_df['exit_reason'].value_counts()

        # Create figure
        fig, ax = plt.subplots(figsize=(10, 6))

        # Color mapping
        colors_map = {
            'stop_loss': '#D62246',
            'take_profit': '#06A77D',
            'breakeven_sl': '#2E86AB',
            'trailing_sl': '#F18F01',
            'negative_pnl_8h': '#A23B72',
            'time_limit_72h': '#888888',
            'force_close_eod': '#666666'
        }

        bar_colors = [colors_map.get(reason, '#888888') for reason in exit_counts.index]

        # Create bars
        bars = ax.bar(range(len(exit_counts)), exit_counts.values, color=bar_colors, edgecolor='black', linewidth=1.5)

        # Labels
        ax.set_xticks(range(len(exit_counts)))
        ax.set_xticklabels([r.replace('_', ' ').title() for r in exit_counts.index], rotation=45, ha='right')
        ax.set_ylabel('Count', fontsize=11)
        ax.set_title('Exit Reasons Breakdown', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')

        # Add count labels on bars
        for i, (bar, count) in enumerate(zip(bars, exit_counts.values)):
            height = bar.get_height()
            pct = (count / len(trades_df)) * 100
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{count}\n({pct:.1f}%)',
                   ha='center', va='bottom', fontweight='bold', fontsize=9)

        plt.tight_layout()

        # Save
        filename = f"exit_reasons_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        print(f"📊 Generated exit reasons chart: {filepath}")
        return filepath

    def create_cumulative_pnl_chart(self, trades_df: pd.DataFrame) -> Optional[Path]:
        """Create cumulative P&L chart"""
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
        except ImportError:
            print("⚠️ matplotlib not installed. Skipping cumulative P&L chart.")
            return None

        if trades_df.empty:
            return None

        # Prepare data
        trades_df = trades_df.copy()
        # Convert exit_time to datetime first (handles mixed types and timezones)
        trades_df['exit_time'] = pd.to_datetime(trades_df['exit_time'], errors='coerce', utc=True)
        # Filter out NaT values
        trades_df = trades_df.dropna(subset=['exit_time'])
        # Remove timezone for matplotlib compatibility
        trades_df['exit_time'] = trades_df['exit_time'].dt.tz_localize(None)
        trades_df = trades_df.sort_values('exit_time')
        trades_df['cumulative_pnl'] = trades_df['net_pnl'].cumsum()

        # Create figure
        fig, ax = plt.subplots(figsize=(12, 6))

        # Plot cumulative P&L
        colors = ['#06A77D' if pnl >= 0 else '#D62246' for pnl in trades_df['cumulative_pnl']]
        ax.plot(trades_df['exit_time'], trades_df['cumulative_pnl'],
               linewidth=2, color='#1f77b4', zorder=3)
        ax.fill_between(trades_df['exit_time'], trades_df['cumulative_pnl'], 0,
                        where=(trades_df['cumulative_pnl'] >= 0),
                        color='#06A77D', alpha=0.2, zorder=2)
        ax.fill_between(trades_df['exit_time'], trades_df['cumulative_pnl'], 0,
                        where=(trades_df['cumulative_pnl'] < 0),
                        color='#D62246', alpha=0.2, zorder=2)

        # Zero line
        ax.axhline(y=0, color='black', linestyle='-', linewidth=1, zorder=1)

        # Styling
        ax.set_xlabel('Date', fontsize=11)
        ax.set_ylabel('Cumulative P&L ($)', fontsize=11)
        ax.set_title('Cumulative P&L Over Time', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)

        # Format axes
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
        plt.xticks(rotation=45)

        plt.tight_layout()

        # Save
        filename = f"cumulative_pnl_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        print(f"📊 Generated cumulative P&L chart: {filepath}")
        return filepath

    def create_all_charts(self, trades_df: pd.DataFrame, initial_balance: float) -> Dict[str, Path]:
        """Generate all performance charts"""
        print("\n" + "="*70)
        print("📊 GENERATING PERFORMANCE CHARTS")
        print("="*70 + "\n")

        charts = {}

        charts['equity_curve'] = self.create_equity_curve(trades_df, initial_balance)
        charts['drawdown'] = self.create_drawdown_chart(trades_df, initial_balance)
        charts['pnl_distribution'] = self.create_pnl_distribution(trades_df)
        charts['cumulative_pnl'] = self.create_cumulative_pnl_chart(trades_df)
        charts['exit_reasons'] = self.create_exit_reasons_chart(trades_df)

        # Remove None values
        charts = {k: v for k, v in charts.items() if v is not None}

        print(f"\n✅ Generated {len(charts)} charts in {self.output_dir}")
        return charts
