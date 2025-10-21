#!/usr/bin/env python3
"""
Signal Generator for Backtesting
Pre-processes all candle data and generates entry signals chronologically
"""

import sys
import json
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional
import argparse

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from strategy.rules import TradingStrategy
from data.data_fetcher import BybitDataFetcher
from utils.config_loader import BacktestConfig, StrategyConfig


class SignalGenerator:
    """Generates all trading signals from historical data"""

    def __init__(self,
                 start_date: datetime,
                 end_date: datetime,
                 use_dynamic_universe: bool = False,
                 backtest_config: Optional[BacktestConfig] = None,
                 strategy_config: Optional[StrategyConfig] = None):
        self.start_date = start_date
        self.end_date = end_date
        self.strategy = TradingStrategy(config=strategy_config)
        self.signals = []
        self.use_dynamic_universe = use_dynamic_universe
        self.universe_scanner = None

        # Store configs
        self.backtest_config = backtest_config
        self.strategy_config = strategy_config

        if use_dynamic_universe:
            from data.universe_manager import TokenUniverseScanner
            self.universe_scanner = TokenUniverseScanner()

    def generate_signals_for_symbol(self, symbol: str, df: pd.DataFrame) -> List[Dict]:
        """
        Generate all signals for a single symbol

        Returns list of signals with:
        - timestamp
        - symbol
        - price
        - rule (6 or 8)
        - indicators (RSI, volatility, etc.)
        """
        symbol_signals = []

        # Ensure data is sorted by time
        df = df.sort_values('timestamp').reset_index(drop=True)

        # Filter to date range
        start_ms = int(self.start_date.timestamp() * 1000)
        end_ms = int(self.end_date.timestamp() * 1000)
        df = df[(df['timestamp'] >= start_ms) & (df['timestamp'] <= end_ms)].copy()

        if len(df) < 150:  # Need minimum bars for indicators (matches live system)
            return symbol_signals

        # Generate signals for the entire dataframe
        df_with_signals = self.strategy.generate_signals(df)

        # Extract signals
        for idx, row in df_with_signals.iterrows():
            if row['signal_side'] == 'Buy' and row['signal_rule'] is not None:
                # If using dynamic universe, check if symbol was in universe at this time
                if self.use_dynamic_universe and self.universe_scanner:
                    signal_date = datetime.fromtimestamp(row['timestamp'] / 1000, tz=timezone.utc)
                    symbols_at_date = self.universe_scanner.get_symbols_for_date(signal_date)

                    # Skip signal if symbol was not in universe at this time
                    if symbol not in symbols_at_date:
                        continue

                signal_data = {
                    'timestamp': row['timestamp'],
                    'datetime': datetime.fromtimestamp(row['timestamp'] / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                    'symbol': symbol,
                    'price': row['close'],
                    'rule': row['signal_rule'],
                    'rsi': row.get('rsi', None),
                    'volatility': row.get('volatility', None),
                    'spread': row.get('spread', None),
                    'volume_score': None,  # Not calculated in strategy
                    'pump_pct': None  # Not stored in row
                }
                symbol_signals.append(signal_data)

        return symbol_signals

    def generate_all_signals(self, symbol_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Generate signals for all symbols and return sorted by timestamp

        Args:
            symbol_data: Dict of {symbol: DataFrame}

        Returns:
            DataFrame with all signals sorted chronologically
        """
        print(f"\n{'='*60}")
        print(f"📊 Generating Entry Signals")
        print(f"{'='*60}\n")
        print(f"Period: {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}")
        print(f"Symbols: {len(symbol_data)}")
        print(f"\n{'='*60}\n")

        all_signals = []

        for idx, (symbol, df) in enumerate(symbol_data.items(), 1):
            print(f"📈 Processing {symbol} ({idx}/{len(symbol_data)})...", end='')

            signals = self.generate_signals_for_symbol(symbol, df)
            all_signals.extend(signals)

            print(f" {len(signals)} signals")

        # Convert to DataFrame and sort by timestamp
        signals_df = pd.DataFrame(all_signals)

        if len(signals_df) > 0:
            signals_df = signals_df.sort_values('timestamp').reset_index(drop=True)

        print(f"\n{'='*60}")
        print(f"✅ Generated {len(signals_df)} total signals")
        print(f"{'='*60}\n")

        return signals_df

    def save_signals(self, signals_df: pd.DataFrame, output_path: Path):
        """Save signals to CSV"""
        signals_df.to_csv(output_path, index=False)
        print(f"💾 Saved signals to {output_path}")

        # Also save summary JSON
        summary = {
            'total_signals': len(signals_df),
            'period': {
                'start': self.start_date.strftime('%Y-%m-%d'),
                'end': self.end_date.strftime('%Y-%m-%d')
            },
            'by_rule': signals_df['rule'].value_counts().to_dict() if len(signals_df) > 0 else {},
            'by_symbol': signals_df['symbol'].value_counts().head(10).to_dict() if len(signals_df) > 0 else {}
        }

        summary_path = output_path.parent / f"{output_path.stem}_summary.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"📋 Saved summary to {summary_path}")

        # Print summary
        print(f"\n{'='*60}")
        print(f"📊 Signal Summary")
        print(f"{'='*60}\n")
        print(f"Total Signals: {summary['total_signals']}")
        if summary['by_rule']:
            print(f"\nBy Rule:")
            for rule, count in summary['by_rule'].items():
                print(f"  {rule}: {count}")
        if summary['by_symbol']:
            print(f"\nTop 10 Symbols:")
            for symbol, count in list(summary['by_symbol'].items())[:10]:
                print(f"  {symbol}: {count}")
        print(f"\n{'='*60}")


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description='Generate trading signals from historical data')

    parser.add_argument('--start', type=str, required=True,
                       help='Start date YYYY-MM-DD')
    parser.add_argument('--end', type=str, required=True,
                       help='End date YYYY-MM-DD')
    parser.add_argument('--data-dir', type=str, default='backtesting/data',
                       help='Directory with cached data (default: backtesting/data)')
    parser.add_argument('--output', type=str, default='backtesting/signals/signals.csv',
                       help='Output file path (default: backtesting/signals/signals.csv)')
    parser.add_argument('--use-universe', action='store_true',
                       help='Use token universe snapshot for symbol filtering (static - start date only)')
    parser.add_argument('--dynamic-universe', action='store_true',
                       help='Use dynamic token universe (checks universe for each signal date)')
    parser.add_argument('--interval', type=str, default='5',
                       help='Candle interval (default: 5)')

    args = parser.parse_args()

    # Parse dates
    start_date = datetime.strptime(args.start, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    end_date = datetime.strptime(args.end, '%Y-%m-%d').replace(tzinfo=timezone.utc)

    # Determine universe mode
    use_dynamic = args.dynamic_universe
    use_static = args.use_universe and not args.dynamic_universe

    # Load symbols
    if use_static:
        from backtesting.token_universe_scanner import TokenUniverseScanner
        scanner = TokenUniverseScanner()
        symbols = scanner.get_symbols_for_date(start_date)
        print(f"🌐 Using STATIC token universe (from {start_date.strftime('%Y-%m-%d')}): {len(symbols)} symbols")
    elif use_dynamic:
        # Get union of all symbols across the period for data loading
        from backtesting.token_universe_scanner import TokenUniverseScanner
        scanner = TokenUniverseScanner()

        # Get symbols from start and end dates (approximation)
        symbols_start = set(scanner.get_symbols_for_date(start_date))
        symbols_end = set(scanner.get_symbols_for_date(end_date))
        symbols = list(symbols_start | symbols_end)

        print(f"🌐 Using DYNAMIC token universe")
        print(f"   Symbols at start ({start_date.strftime('%Y-%m-%d')}): {len(symbols_start)}")
        print(f"   Symbols at end ({end_date.strftime('%Y-%m-%d')}): {len(symbols_end)}")
        print(f"   Total symbols to process: {len(symbols)} (union)")
    else:
        # Get all symbols from data directory
        data_dir = Path(args.data_dir)
        csv_files = list(data_dir.glob(f"*_{args.interval}_*.csv"))
        symbols = list(set([f.name.split('_')[0] for f in csv_files]))
        print(f"📂 Found {len(symbols)} symbols in {data_dir}")

    # Load data for all symbols
    print(f"\n📥 Loading historical data...")
    data_dir = Path(args.data_dir)
    symbol_data = {}
    fetcher = BybitDataFetcher()

    for symbol in symbols:
        csv_files = list(data_dir.glob(f"{symbol}_{args.interval}_*.csv"))
        if csv_files:
            # Use earliest file for maximum coverage
            csv_file = sorted(csv_files)[0]
            df = fetcher.load_from_csv(csv_file)
            symbol_data[symbol] = df
            print(f"   ✅ {symbol}: {len(df)} candles")

    print(f"\n✅ Loaded {len(symbol_data)} symbols")

    # Generate signals
    generator = SignalGenerator(start_date, end_date, use_dynamic_universe=use_dynamic)
    signals_df = generator.generate_all_signals(symbol_data)

    # Save signals
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    generator.save_signals(signals_df, output_path)


if __name__ == "__main__":
    main()
