#!/usr/bin/env python3
"""
Backtesting V2 - Main Execution Script

This script runs the complete backtest workflow:
1. Load configuration
2. Generate signals (if needed)
3. Run pyramid backtest
4. Generate reports

Usage:
    python scripts/run_backtest_v2.py --config config/backtest_config.yaml
    python scripts/run_backtest_v2.py --start 2025-09-05 --end 2025-10-17
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone

# Add v2 directory to path
v2_dir = Path(__file__).parent.parent
sys.path.insert(0, str(v2_dir))

from utils.config_loader import load_configs
from strategy.signal_generator import SignalGenerator
from execution.engine import PyramidBacktestEngine
from data.data_fetcher import BybitDataFetcher
from data.universe_manager import TokenUniverseScanner
from analytics.reports import ReportGenerator
import pandas as pd
import json
from typing import Dict


def generate_signals(backtest_cfg, strategy_cfg, signals_file: str):
    """Generate trading signals for the backtest period"""

    print("="*70)
    print("🔄 PHASE 1: GENERATING SIGNALS")
    print("="*70 + "\n")

    # Parse dates
    start_date = datetime.strptime(backtest_cfg.start_date, '%Y-%m-%d')
    end_date = datetime.strptime(backtest_cfg.end_date, '%Y-%m-%d')

    print(f"Period: {backtest_cfg.start_date} to {backtest_cfg.end_date}")
    print(f"Universe: {backtest_cfg.universe_type}")
    print(f"Pump Threshold: {strategy_cfg.pump_threshold}%\n")

    # Initialize components
    print("1️⃣ Initializing components...")
    use_dynamic = backtest_cfg.universe_type == "dynamic"

    signal_gen = SignalGenerator(
        start_date=start_date,
        end_date=end_date,
        use_dynamic_universe=use_dynamic,
        backtest_config=backtest_cfg,
        strategy_config=strategy_cfg
    )

    data_fetcher = BybitDataFetcher(use_cache=False)

    # Get token universe
    print(f"\n2️⃣ Getting token universe...")
    if use_dynamic:
        scanner = TokenUniverseScanner(config=backtest_cfg)
        # For dynamic universe, we'll get symbols at the start date
        symbols = scanner.get_symbols_for_date(start_date)
    else:
        # For static universe, would need to load from config
        # For now, use dynamic as fallback
        scanner = TokenUniverseScanner(config=backtest_cfg)
        symbols = scanner.get_symbols_for_date(start_date)

    print(f"   Found {len(symbols)} symbols to analyze\n")

    # Fetch data and generate signals
    print(f"3️⃣ Fetching data and generating signals...")
    print(f"   This may take 10-20 minutes...\n")

    all_signals = []
    symbol_data = {}

    for i, symbol in enumerate(symbols, 1):
        try:
            # Progress indicator
            if i % 50 == 0:
                print(f"   Progress: {i}/{len(symbols)} symbols processed...")

            # Fetch OHLCV data (convert datetime to milliseconds)
            start_ms = int(start_date.timestamp() * 1000)
            end_ms = int(end_date.timestamp() * 1000)
            df = data_fetcher.fetch_klines(
                symbol=symbol,
                interval=backtest_cfg.timeframe,
                start_time=start_ms,
                end_time=end_ms
            )

            if df is None or len(df) < 150:
                continue

            symbol_data[symbol] = df

            # Generate signals for this symbol
            signals = signal_gen.generate_signals_for_symbol(symbol, df)
            all_signals.extend(signals)

        except Exception as e:
            print(f"   ⚠️  Error processing {symbol}: {e}")
            continue

    print(f"\n4️⃣ Signal generation complete!")
    print(f"   Total signals generated: {len(all_signals)}")

    # Sort signals by timestamp
    if all_signals:
        signals_df = pd.DataFrame(all_signals)
        signals_df = signals_df.sort_values('timestamp').reset_index(drop=True)

        # Save to CSV
        signals_df.to_csv(signals_file, index=False)
        print(f"   Signals saved to: {signals_file}\n")

        # Summary
        print("📊 Signal Summary:")
        print(f"   Total Signals: {len(signals_df)}")
        if 'rule' in signals_df.columns:
            print(f"   Rule 6 Signals: {len(signals_df[signals_df['rule'] == 'Rule 6'])}")
            print(f"   Rule 8 Signals: {len(signals_df[signals_df['rule'] == 'Rule 8'])}")
        print(f"   Unique Symbols: {signals_df['symbol'].nunique()}")
        print()

        return signals_df
    else:
        print("   ⚠️  No signals generated!")
        return None


def run_backtest(signals_df: pd.DataFrame, backtest_cfg, strategy_cfg):
    """Run pyramid backtest on generated signals"""

    print("="*70)
    print("🎯 PHASE 2: RUNNING PYRAMID BACKTEST")
    print("="*70 + "\n")

    # Initialize backtest engine
    print("1️⃣ Initializing backtest engine...")
    engine = PyramidBacktestEngine(
        initial_balance=backtest_cfg.initial_balance,
        position_size=backtest_cfg.base_position_size,
        max_active_trades=backtest_cfg.max_active_trades,
        commission_rate=backtest_cfg.commission_rate,
        backtest_config=backtest_cfg,
        strategy_config=strategy_cfg
    )

    print(f"   Initial Balance: ${engine.initial_balance:,.0f}")
    print(f"   Position Size: ${engine.position_size:,.0f}")
    print(f"   Max Trades: {engine.max_active_trades}")
    print(f"   Commission: {engine.commission_rate*100:.3f}%\n")

    # Load candle data for all symbols
    print("2️⃣ Loading candle data...")
    data_fetcher = BybitDataFetcher(use_cache=True)  # Reuse cached data from Phase 1
    start_date = datetime.strptime(backtest_cfg.start_date, '%Y-%m-%d')
    end_date = datetime.strptime(backtest_cfg.end_date, '%Y-%m-%d')

    unique_symbols = signals_df['symbol'].unique()
    candle_data = {}

    for i, symbol in enumerate(unique_symbols, 1):
        if i % 50 == 0:
            print(f"   Progress: {i}/{len(unique_symbols)} symbols loaded...")

        try:
            start_ms = int(start_date.timestamp() * 1000)
            end_ms = int(end_date.timestamp() * 1000)
            df = data_fetcher.fetch_klines(
                symbol=symbol,
                interval=backtest_cfg.timeframe,
                start_time=start_ms,
                end_time=end_ms
            )
            if df is not None and len(df) > 0:
                # Index by timestamp for fast lookup
                df = df.set_index('timestamp')
                candle_data[symbol] = df
        except Exception as e:
            print(f"   ⚠️  Error loading {symbol}: {e}")
            continue

    print(f"   Loaded data for {len(candle_data)} symbols\n")

    # Process signals chronologically
    print("3️⃣ Processing signals chronologically...")
    total_signals = len(signals_df)

    for i, (idx, signal) in enumerate(signals_df.iterrows(), 1):
        if i % 100 == 0:
            pct = (i / total_signals) * 100
            print(f"   Progress: {i}/{total_signals} signals ({pct:.1f}%)")

        symbol = signal['symbol']
        timestamp = signal['timestamp']

        # Get current candle
        if symbol not in candle_data:
            continue

        try:
            candle = candle_data[symbol].loc[timestamp]
        except KeyError:
            continue

        # Process signal
        engine.process_signal(signal, candle)

        # Update all positions with current candle data
        current_candles = {}
        for sym in engine.active_positions.keys():
            if sym in candle_data:
                try:
                    current_candles[sym] = candle_data[sym].loc[timestamp]
                except KeyError:
                    pass

        if current_candles:
            engine.update_positions(current_candles, timestamp)

    # Close all remaining positions
    print(f"\n4️⃣ Closing remaining positions...")
    for symbol, position in list(engine.active_positions.items()):
        if symbol in candle_data:
            # Use last available price
            last_candle = candle_data[symbol].iloc[-1]
            exit_price = last_candle['close']

            pnl_info = position.calculate_pnl(exit_price, engine.commission_rate)

            trade_record = {
                'symbol': symbol,
                'entry_time': datetime.fromtimestamp(position.entries[0]['time'] / 1000, tz=timezone.utc),
                'exit_time': datetime.fromtimestamp(last_candle.name / 1000, tz=timezone.utc),
                'avg_entry_price': position.avg_entry_price,
                'exit_price': exit_price,
                'quantity': position.quantity,
                'exit_reason': 'force_close_eod',
                'net_pnl': pnl_info['net_pnl'],
                'return_pct': pnl_info['return_pct'],
                'duration_hours': pnl_info['duration_hours'],
                'entry_count': position.entry_count,
                'total_invested': pnl_info['total_invested'],
                'breakeven_triggered': position.breakeven_triggered,
                'rule': position.entries[0]['rule']
            }

            engine.closed_trades.append(trade_record)
            engine.balance += position.quantity * exit_price

    engine.active_positions.clear()

    print(f"   All positions closed\n")

    # Calculate statistics
    print("="*70)
    print("📊 BACKTEST RESULTS")
    print("="*70 + "\n")

    final_balance = engine.balance
    total_pnl = final_balance - engine.initial_balance
    total_return = (total_pnl / engine.initial_balance) * 100

    print(f"Initial Balance: ${engine.initial_balance:,.2f}")
    print(f"Final Balance: ${final_balance:,.2f}")
    print(f"Total P&L: ${total_pnl:,.2f}")
    print(f"Total Return: {total_return:.2f}%\n")

    print(f"Total Trades: {len(engine.closed_trades)}")
    print(f"Signals Processed: {engine.total_signals}")
    print(f"Signals Taken: {engine.signals_taken}")
    print(f"Signals Skipped (No Capital): {engine.signals_skipped_no_capital}")
    print(f"Signals Skipped (Max Trades): {engine.signals_skipped_max_trades}")
    print(f"Pyramided Entries: {engine.pyramided_entries}\n")

    # Win rate analysis
    if engine.closed_trades:
        trades_df = pd.DataFrame(engine.closed_trades)

        winning_trades = trades_df[trades_df['net_pnl'] > 0]
        losing_trades = trades_df[trades_df['net_pnl'] < 0]
        breakeven_trades = trades_df[trades_df['net_pnl'] == 0]

        win_rate = len(winning_trades) / len(trades_df) * 100
        avg_win = winning_trades['net_pnl'].mean() if len(winning_trades) > 0 else 0
        avg_loss = losing_trades['net_pnl'].mean() if len(losing_trades) > 0 else 0

        print(f"Winning Trades: {len(winning_trades)} ({win_rate:.1f}%)")
        print(f"Losing Trades: {len(losing_trades)} ({len(losing_trades)/len(trades_df)*100:.1f}%)")
        print(f"Breakeven Trades: {len(breakeven_trades)}")
        print(f"Average Win: ${avg_win:.2f}")
        print(f"Average Loss: ${avg_loss:.2f}")

        if avg_loss != 0:
            profit_factor = abs(winning_trades['net_pnl'].sum() / losing_trades['net_pnl'].sum()) if len(losing_trades) > 0 else float('inf')
            print(f"Profit Factor: {profit_factor:.2f}")

        print()

        # Save trade history
        output_dir = Path(backtest_cfg.results_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        trades_file = output_dir / f"trades_{timestamp_str}.csv"
        trades_df.to_csv(trades_file, index=False)
        print(f"Trade history saved to: {trades_file}")

        return trades_df
    else:
        print("⚠️  No trades executed!")
        return None


def main():
    parser = argparse.ArgumentParser(description='Run Backtesting V2')

    # Configuration
    parser.add_argument('--config', type=str, default=None,
                       help='Path to config directory (default: v2/config/)')

    # Override dates (optional)
    parser.add_argument('--start', type=str, default=None,
                       help='Start date YYYY-MM-DD (overrides config)')
    parser.add_argument('--end', type=str, default=None,
                       help='End date YYYY-MM-DD (overrides config)')

    # Override capital (optional)
    parser.add_argument('--balance', type=float, default=None,
                       help='Initial balance (overrides config)')
    parser.add_argument('--position-size', type=float, default=None,
                       help='Position size (overrides config)')
    parser.add_argument('--max-trades', type=int, default=None,
                       help='Max active trades (overrides config)')

    # Signal options
    parser.add_argument('--signals', type=str, default=None,
                       help='Use existing signals file (skip generation)')
    parser.add_argument('--regenerate', action='store_true',
                       help='Regenerate signals even if file exists')

    # Output options
    parser.add_argument('--output-dir', type=str, default=None,
                       help='Output directory (overrides config)')
    parser.add_argument('--no-pdf', action='store_true',
                       help='Skip PDF report generation')

    args = parser.parse_args()

    print("\n" + "="*70)
    print("🚀 BACKTESTING V2 - Production-Grade Pyramid Backtest")
    print("="*70 + "\n")

    # Load configuration
    print("📋 Loading configuration...")
    if args.config:
        config_dir = Path(args.config)
    else:
        config_dir = v2_dir / "config"

    try:
        backtest_cfg, strategy_cfg, risk_cfg = load_configs(config_dir)
        print(f"✅ Configuration loaded from: {config_dir}")
    except Exception as e:
        print(f"❌ Error loading configuration: {e}")
        return 1

    # Apply command-line overrides
    if args.start:
        backtest_cfg.start_date = args.start
        print(f"   Override: start_date = {args.start}")
    if args.end:
        backtest_cfg.end_date = args.end
        print(f"   Override: end_date = {args.end}")
    if args.balance:
        backtest_cfg.initial_balance = args.balance
        print(f"   Override: initial_balance = ${args.balance:,.0f}")
    if args.position_size:
        backtest_cfg.base_position_size = args.position_size
        print(f"   Override: position_size = ${args.position_size:,.0f}")
    if args.max_trades:
        backtest_cfg.max_active_trades = args.max_trades
        print(f"   Override: max_active_trades = {args.max_trades}")

    # Display configuration summary
    print("\n" + "="*70)
    print("⚙️  CONFIGURATION SUMMARY")
    print("="*70)
    print(f"Period: {backtest_cfg.start_date} to {backtest_cfg.end_date}")
    print(f"Capital: ${backtest_cfg.initial_balance:,.0f}")
    print(f"Position Size: ${backtest_cfg.base_position_size:,.0f}")
    print(f"Max Active Trades: {backtest_cfg.max_active_trades}")
    print(f"Universe: {backtest_cfg.universe_type}")
    print(f"Pump Threshold: {strategy_cfg.pump_threshold}%")
    print(f"Rules Enabled: ", end="")
    enabled_rules = []
    if strategy_cfg.rule_6_enabled:
        enabled_rules.append("Rule 6")
    if strategy_cfg.rule_8_enabled:
        enabled_rules.append("Rule 8")
    print(", ".join(enabled_rules))
    print(f"Stop Loss: {strategy_cfg.stop_loss_pct}%")
    print(f"Take Profit: {strategy_cfg.take_profit_pct}%")
    print(f"Breakeven: {'Enabled' if strategy_cfg.breakeven_enabled else 'Disabled'} @ {strategy_cfg.breakeven_trigger_pct}%")
    print(f"Pyramiding: {'Enabled' if backtest_cfg.pyramiding_enabled else 'Disabled'}")
    print("="*70 + "\n")

    # Phase 1: Signal Generation or Loading
    signals_file = args.signals
    if signals_file is None:
        # Generate default signals filename
        start_str = backtest_cfg.start_date.replace('-', '')
        end_str = backtest_cfg.end_date.replace('-', '')
        signals_dir = Path(backtest_cfg.signals_dir)
        signals_dir.mkdir(parents=True, exist_ok=True)
        signals_file = str(signals_dir / f"signals_{start_str}_{end_str}.csv")

    signals_path = Path(signals_file)

    # Phase 1: Generate or load signals
    signals_df = None

    if signals_path.exists() and not args.regenerate:
        print(f"📊 Using existing signals: {signals_file}")
        print(f"   (Use --regenerate to generate new signals)\n")

        try:
            signals_df = pd.read_csv(signals_file)
            print(f"✅ Loaded {len(signals_df)} signals from file\n")
        except Exception as e:
            print(f"❌ Error loading signals file: {e}")
            print("   Will regenerate signals...\n")
            signals_df = None

    if signals_df is None:
        # Generate signals
        signals_df = generate_signals(backtest_cfg, strategy_cfg, signals_file)

        if signals_df is None or len(signals_df) == 0:
            print("❌ No signals generated - cannot proceed with backtest")
            return 1

    # Phase 2: Run Backtest
    trades_df = run_backtest(signals_df, backtest_cfg, strategy_cfg)

    if trades_df is None or len(trades_df) == 0:
        print("\n⚠️  Backtest completed but no trades executed")
        print("   Cannot generate reports without trade data")
        return 1

    # Phase 3: Generate Reports
    if not args.no_pdf:
        print("\n" + "="*70)
        print("📊 PHASE 3: GENERATING REPORTS")
        print("="*70 + "\n")

        output_dir = Path(args.output_dir) if args.output_dir else Path(backtest_cfg.reports_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Prepare config dict for report
        report_config = {
            'start_date': backtest_cfg.start_date,
            'end_date': backtest_cfg.end_date,
            'initial_balance': backtest_cfg.initial_balance,
            'position_size': backtest_cfg.base_position_size,
            'max_active_trades': backtest_cfg.max_active_trades,
            'commission_rate': backtest_cfg.commission_rate,
            'universe_type': backtest_cfg.universe_type,
            'pump_threshold': strategy_cfg.pump_threshold,
            'stop_loss_pct': strategy_cfg.stop_loss_pct,
            'take_profit_pct': strategy_cfg.take_profit_pct,
        }

        # Generate complete report package
        report_gen = ReportGenerator(output_dir)
        outputs = report_gen.generate_complete_report(
            trades_df=trades_df,
            initial_balance=backtest_cfg.initial_balance,
            config=report_config
        )

        print(f"\n📁 All outputs saved to: {output_dir}")
        print(f"   Files generated:")
        for name, path in outputs.items():
            if path:
                print(f"   - {name}: {path.name}")

    print("\n" + "="*70)
    print("✅ BACKTEST COMPLETE")
    print("="*70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
