#!/usr/bin/env python3
"""
Report Generator

Generates comprehensive PDF and text reports from backtest results.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from .metrics import PerformanceMetrics
from .charts import ChartGenerator


class ReportGenerator:
    """Generate comprehensive backtest reports"""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_trades_csv(self, trades_df: pd.DataFrame, filename: Optional[str] = None) -> Path:
        """Save trade details to CSV"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"trades_{timestamp}.csv"

        filepath = self.output_dir / filename

        # Format datetime columns
        trades_copy = trades_df.copy()
        if 'entry_time' in trades_copy.columns:
            trades_copy['entry_time'] = pd.to_datetime(trades_copy['entry_time'], unit='ms', errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')
        if 'exit_time' in trades_copy.columns:
            trades_copy['exit_time'] = pd.to_datetime(trades_copy['exit_time'], unit='ms', errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')

        trades_copy.to_csv(filepath, index=False)
        print(f"💾 Saved trades to: {filepath}")

        return filepath

    def generate_text_report(self, metrics: Dict, config: Dict, trades_df: pd.DataFrame) -> Path:
        """Generate detailed text report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backtest_report_{timestamp}.txt"
        filepath = self.output_dir / filename

        lines = []
        lines.append("=" * 80)
        lines.append("BACKTESTING REPORT - CFT PROP TRADING STRATEGY")
        lines.append("=" * 80)
        lines.append("")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append("")

        # Configuration
        lines.append("=" * 80)
        lines.append("BACKTEST CONFIGURATION")
        lines.append("=" * 80)
        lines.append(f"Period: {config.get('start_date', 'N/A')} to {config.get('end_date', 'N/A')}")
        lines.append(f"Initial Balance: ${config.get('initial_balance', 0):,.2f}")
        lines.append(f"Position Size: ${config.get('position_size', 0):,.2f}")
        lines.append(f"Max Active Trades: {config.get('max_active_trades', 0)}")
        lines.append(f"Commission Rate: {config.get('commission_rate', 0)*100:.3f}%")
        lines.append(f"Universe Type: {config.get('universe_type', 'N/A')}")
        lines.append(f"Pump Threshold: {config.get('pump_threshold', 0)}%")
        lines.append(f"Stop Loss: {config.get('stop_loss_pct', 0)}%")
        lines.append(f"Take Profit: {config.get('take_profit_pct', 0)}%")
        lines.append("")

        # Performance Summary
        lines.append("=" * 80)
        lines.append("PERFORMANCE SUMMARY")
        lines.append("=" * 80)
        lines.append(f"Initial Balance:     ${metrics['initial_balance']:>15,.2f}")
        lines.append(f"Final Balance:       ${metrics['final_balance']:>15,.2f}")
        lines.append(f"Total P&L:           ${metrics['total_pnl']:>15,.2f}")
        lines.append(f"Total Return:        {metrics['total_return_pct']:>15.2f}%")
        lines.append("")

        # Trade Statistics
        lines.append("=" * 80)
        lines.append("TRADE STATISTICS")
        lines.append("=" * 80)
        lines.append(f"Total Trades:        {metrics['total_trades']:>15}")
        lines.append(f"Winning Trades:      {metrics['winning_trades']:>15} ({metrics['win_rate']:.1f}%)")
        lines.append(f"Losing Trades:       {metrics['losing_trades']:>15}")
        lines.append(f"Breakeven Trades:    {metrics['breakeven_trades']:>15}")
        lines.append("")
        lines.append(f"Win Strike Rate:     {metrics.get('win_strike_rate', 0):>15.1f}% (>0.5% return)")
        lines.append(f"Loss Strike Rate:    {metrics.get('loss_strike_rate', 0):>15.1f}% (<-0.5% return)")
        lines.append(f"Breakeven Rate:      {metrics.get('breakeven_strike_rate', 0):>15.1f}% (±0.5%)")
        lines.append("")

        # Win/Loss Analysis
        lines.append("=" * 80)
        lines.append("WIN/LOSS ANALYSIS")
        lines.append("=" * 80)
        lines.append(f"Average Win:         ${metrics['avg_win']:>15.2f}")
        lines.append(f"Average Loss:        ${metrics['avg_loss']:>15.2f}")
        lines.append(f"Average Trade:       ${metrics['avg_trade']:>15.2f}")
        lines.append(f"Gross Profit:        ${metrics['gross_profit']:>15.2f}")
        lines.append(f"Gross Loss:          ${metrics['gross_loss']:>15.2f}")
        lines.append(f"Profit Factor:       {metrics['profit_factor']:>15.2f}")
        lines.append(f"Expectancy:          ${metrics['expectancy']:>15.2f}")
        lines.append("")

        # Risk Metrics
        lines.append("=" * 80)
        lines.append("RISK METRICS")
        lines.append("=" * 80)
        lines.append(f"Max Drawdown:        ${metrics['max_drawdown']:>15,.2f} ({metrics['max_drawdown_pct']:.2f}%)")
        lines.append(f"Max DD Duration:     {metrics.get('max_drawdown_duration', 0):>15} trades")
        lines.append(f"Sharpe Ratio:        {metrics['sharpe_ratio']:>15.2f}")
        lines.append(f"Sortino Ratio:       {metrics['sortino_ratio']:>15.2f}")
        lines.append(f"Calmar Ratio:        {metrics['calmar_ratio']:>15.2f}")
        lines.append("")

        # Costs
        lines.append("=" * 80)
        lines.append("COSTS")
        lines.append("=" * 80)
        lines.append(f"Total Commission:    ${metrics['total_commission_paid']:>15.2f}")
        lines.append(f"Commission %:        {metrics['commission_pct']:>15.3f}%")
        lines.append("")

        # Duration Metrics
        if 'avg_trade_duration_hours' in metrics:
            lines.append("=" * 80)
            lines.append("DURATION METRICS")
            lines.append("=" * 80)
            lines.append(f"Avg Duration:        {metrics['avg_trade_duration_hours']:>15.2f} hours")
            lines.append(f"Max Duration:        {metrics['max_trade_duration_hours']:>15.2f} hours")
            lines.append(f"Min Duration:        {metrics['min_trade_duration_hours']:>15.2f} hours")
            lines.append("")

        # Pyramiding Stats
        if 'pyramided_positions' in metrics:
            lines.append("=" * 80)
            lines.append("PYRAMIDING STATISTICS")
            lines.append("=" * 80)
            lines.append(f"Pyramided Positions: {metrics['pyramided_positions']:>15}")
            lines.append(f"Pyramiding Rate:     {metrics['pyramiding_rate']:>15.1f}%")
            lines.append(f"Avg Entries/Trade:   {metrics['avg_entries_per_trade']:>15.2f}")
            lines.append("")

        # Exit Reasons
        if 'exit_reasons' in metrics and metrics['exit_reasons']:
            lines.append("=" * 80)
            lines.append("EXIT REASONS BREAKDOWN")
            lines.append("=" * 80)
            for reason, count in sorted(metrics['exit_reasons'].items(), key=lambda x: x[1], reverse=True):
                pct = (count / metrics['total_trades']) * 100
                lines.append(f"{reason.replace('_', ' ').title():<25} {count:>10} ({pct:>5.1f}%)")
            lines.append("")

        # Top Trades
        if not trades_df.empty:
            lines.append("=" * 80)
            lines.append("TOP 10 WINNING TRADES")
            lines.append("=" * 80)
            top_wins = trades_df.nlargest(10, 'net_pnl')[['symbol', 'net_pnl', 'return_pct', 'exit_reason']]
            for idx, row in top_wins.iterrows():
                lines.append(f"{row['symbol']:<15} ${row['net_pnl']:>10.2f} ({row['return_pct']:>6.2f}%)  {row['exit_reason']}")
            lines.append("")

            lines.append("=" * 80)
            lines.append("TOP 10 LOSING TRADES")
            lines.append("=" * 80)
            top_losses = trades_df.nsmallest(10, 'net_pnl')[['symbol', 'net_pnl', 'return_pct', 'exit_reason']]
            for idx, row in top_losses.iterrows():
                lines.append(f"{row['symbol']:<15} ${row['net_pnl']:>10.2f} ({row['return_pct']:>6.2f}%)  {row['exit_reason']}")
            lines.append("")

        lines.append("=" * 80)
        lines.append("END OF REPORT")
        lines.append("=" * 80)

        # Write file
        with open(filepath, 'w') as f:
            f.write('\n'.join(lines))

        print(f"📄 Generated text report: {filepath}")
        return filepath

    def generate_complete_report(
        self,
        trades_df: pd.DataFrame,
        initial_balance: float,
        config: Dict
    ) -> Dict[str, Path]:
        """Generate complete report package: CSV, text report, and charts"""

        print("\n" + "=" * 80)
        print("📊 GENERATING COMPLETE BACKTEST REPORT")
        print("=" * 80 + "\n")

        outputs = {}

        # Calculate metrics
        print("1️⃣ Calculating performance metrics...")
        metrics_calc = PerformanceMetrics(trades_df, initial_balance)
        metrics = metrics_calc.calculate_all_metrics()
        print("   ✅ Metrics calculated\n")

        # Save trades CSV
        print("2️⃣ Saving trade history...")
        outputs['trades_csv'] = self.save_trades_csv(trades_df)
        print()

        # Generate text report
        print("3️⃣ Generating text report...")
        outputs['text_report'] = self.generate_text_report(metrics, config, trades_df)
        print()

        # Generate charts
        print("4️⃣ Generating performance charts...")
        chart_gen = ChartGenerator(self.output_dir)
        charts = chart_gen.create_all_charts(trades_df, initial_balance)
        outputs.update(charts)
        print()

        # Display metrics summary
        print(metrics_calc.get_metrics_summary())

        print("\n" + "=" * 80)
        print(f"✅ REPORT GENERATION COMPLETE")
        print(f"   Output directory: {self.output_dir}")
        print(f"   Files generated: {len(outputs)}")
        print("=" * 80 + "\n")

        return outputs
