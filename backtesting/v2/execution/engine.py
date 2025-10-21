#!/usr/bin/env python3
"""
Pyramid Backtest Engine - Signal-Based Execution
Processes pre-generated signals chronologically with pyramiding support
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional
import argparse
import json

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from utils.config_loader import BacktestConfig, StrategyConfig


class Position:
    """Represents a trading position with pyramiding support"""

    def __init__(self, symbol: str, entry_time: int, entry_price: float,
                 quantity: float, rule: str, position_size_usd: float,
                 stop_loss_pct: float = 8.0, take_profit_pct: float = 30.0,
                 breakeven_trigger_pct: float = 8.0):
        self.symbol = symbol
        self.entries = [{
            'time': entry_time,
            'price': entry_price,
            'quantity': quantity,
            'rule': rule
        }]
        self.quantity = quantity
        self.avg_entry_price = entry_price
        self.position_size_usd = position_size_usd

        # Store config params
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.breakeven_trigger_pct = breakeven_trigger_pct

        # Risk management
        self.stop_loss = entry_price * (1 - stop_loss_pct / 100)
        self.take_profit = entry_price * (1 + take_profit_pct / 100)
        self.breakeven_triggered = False
        self.breakeven_price = None

        # Tracking
        self.max_price = entry_price
        self.entry_count = 1
        self.total_invested = position_size_usd

    def add_entry(self, entry_time: int, entry_price: float, quantity: float,
                  rule: str, position_size_usd: float):
        """Add another entry to existing position (pyramiding)"""
        self.entries.append({
            'time': entry_time,
            'price': entry_price,
            'quantity': quantity,
            'rule': rule
        })

        # Calculate new average entry price
        total_value = self.quantity * self.avg_entry_price + quantity * entry_price
        self.quantity += quantity
        self.avg_entry_price = total_value / self.quantity
        self.total_invested += position_size_usd
        self.entry_count += 1

        # Update stop loss to new average (if not at breakeven)
        if not self.breakeven_triggered:
            self.stop_loss = self.avg_entry_price * (1 - self.stop_loss_pct / 100)
        else:
            # If breakeven already triggered, update breakeven price
            buffer_pct = 0.0002  # 0.02% buffer above entry
            self.breakeven_price = self.avg_entry_price * (1 + buffer_pct)
            self.stop_loss = self.breakeven_price

    def update_max_price(self, current_price: float):
        """Track maximum price reached"""
        if current_price > self.max_price:
            self.max_price = current_price

    def check_breakeven(self, current_price: float) -> bool:
        """Check if position should move to breakeven"""
        if self.breakeven_triggered:
            return False

        profit_pct = ((current_price - self.avg_entry_price) / self.avg_entry_price) * 100

        if profit_pct >= self.breakeven_trigger_pct:
            self.breakeven_triggered = True
            buffer_pct = 0.0002  # 0.02% buffer above entry
            self.breakeven_price = self.avg_entry_price * (1 + buffer_pct)
            self.stop_loss = self.breakeven_price
            return True

        return False

    def check_exit(self, current_time: int, current_price: float,
                   open_price: float, high: float, low: float) -> Optional[Dict]:
        """
        Check if position should exit
        Uses OHLC to simulate intra-bar exits

        Returns exit info if position should close, None otherwise
        """
        # Check stop loss hit (using low of candle)
        if low <= self.stop_loss:
            exit_price = self.stop_loss
            if self.breakeven_triggered:
                reason = 'breakeven_sl'
            else:
                reason = 'stop_loss'
            return {
                'time': current_time,
                'price': exit_price,
                'reason': reason
            }

        # Check take profit hit (using high of candle)
        if high >= self.take_profit:
            return {
                'time': current_time,
                'price': self.take_profit,
                'reason': 'take_profit'
            }

        # Check time-based exits
        duration_hours = (current_time - self.entries[0]['time']) / (1000 * 3600)

        # Exit negative positions after 8 hours
        if duration_hours >= 8:
            current_pnl_pct = ((current_price - self.avg_entry_price) / self.avg_entry_price) * 100
            if current_pnl_pct < 0:
                return {
                    'time': current_time,
                    'price': current_price,
                    'reason': 'negative_pnl_8h'
                }

        # Exit all positions after 72 hours
        if duration_hours >= 72:
            return {
                'time': current_time,
                'price': current_price,
                'reason': 'time_limit_72h'
            }

        return None

    def calculate_pnl(self, exit_price: float, commission_rate: float) -> Dict:
        """Calculate P&L for position"""
        # Entry commission
        entry_commission = self.total_invested * commission_rate

        # Exit value and commission
        exit_value = self.quantity * exit_price
        exit_commission = exit_value * commission_rate

        # Net P&L
        gross_pnl = exit_value - self.total_invested
        net_pnl = gross_pnl - entry_commission - exit_commission

        # Duration
        duration_hours = (self.entries[-1]['time'] - self.entries[0]['time']) / (1000 * 3600)

        return {
            'gross_pnl': gross_pnl,
            'net_pnl': net_pnl,
            'total_commission': entry_commission + exit_commission,
            'entry_commission': entry_commission,
            'exit_commission': exit_commission,
            'return_pct': (net_pnl / self.total_invested) * 100,
            'duration_hours': duration_hours,
            'entry_count': self.entry_count,
            'avg_entry_price': self.avg_entry_price,
            'total_invested': self.total_invested
        }


class PyramidBacktestEngine:
    """Signal-based backtest engine with pyramiding support"""

    def __init__(self, initial_balance: float, position_size: float,
                 max_active_trades: int, commission_rate: float = 0.00055,
                 backtest_config: Optional[BacktestConfig] = None,
                 strategy_config: Optional[StrategyConfig] = None):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.position_size = position_size
        self.max_active_trades = max_active_trades
        self.commission_rate = commission_rate

        # Store configs
        self.backtest_config = backtest_config
        self.strategy_config = strategy_config

        # Extract risk params from config
        if strategy_config:
            self.stop_loss_pct = strategy_config.stop_loss_pct
            self.take_profit_pct = strategy_config.take_profit_pct
            self.breakeven_trigger_pct = strategy_config.breakeven_trigger_pct
        else:
            # Fallback defaults
            self.stop_loss_pct = 8.0
            self.take_profit_pct = 30.0
            self.breakeven_trigger_pct = 8.0

        # Position tracking
        self.active_positions: Dict[str, Position] = {}  # symbol -> Position
        self.closed_trades = []

        # Statistics
        self.total_signals = 0
        self.signals_taken = 0
        self.signals_skipped_no_capital = 0
        self.signals_skipped_max_trades = 0
        self.pyramided_entries = 0

    def count_non_breakeven_positions(self) -> int:
        """Count positions that haven't triggered breakeven yet"""
        return sum(1 for pos in self.active_positions.values()
                  if not pos.breakeven_triggered)

    def can_open_new_position(self) -> bool:
        """Check if we can open a new position (not symbol with existing position)"""
        non_breakeven = self.count_non_breakeven_positions()
        return non_breakeven < self.max_active_trades

    def process_signal(self, signal: pd.Series, current_candle: pd.Series):
        """
        Process a single entry signal

        Args:
            signal: Row from signals DataFrame
            current_candle: Current OHLC data for the symbol
        """
        self.total_signals += 1
        symbol = signal['symbol']

        # Check if we already have a position in this symbol
        if symbol in self.active_positions:
            # Pyramid: add to existing position
            position = self.active_positions[symbol]

            # Check if we have capital
            if self.balance < self.position_size:
                self.signals_skipped_no_capital += 1
                return

            # Add to position
            entry_price = signal['price']
            quantity = self.position_size / entry_price

            position.add_entry(
                entry_time=int(signal['timestamp']),
                entry_price=entry_price,
                quantity=quantity,
                rule=signal['rule'],
                position_size_usd=self.position_size
            )

            self.balance -= self.position_size
            self.pyramided_entries += 1
            self.signals_taken += 1

        else:
            # New position
            # Check if we can open new position (max trades limit)
            if not self.can_open_new_position():
                self.signals_skipped_max_trades += 1
                return

            # Check if we have capital
            if self.balance < self.position_size:
                self.signals_skipped_no_capital += 1
                return

            # Open new position
            entry_price = signal['price']
            quantity = self.position_size / entry_price

            position = Position(
                symbol=symbol,
                entry_time=int(signal['timestamp']),
                entry_price=entry_price,
                quantity=quantity,
                rule=signal['rule'],
                position_size_usd=self.position_size,
                stop_loss_pct=self.stop_loss_pct,
                take_profit_pct=self.take_profit_pct,
                breakeven_trigger_pct=self.breakeven_trigger_pct
            )

            self.active_positions[symbol] = position
            self.balance -= self.position_size
            self.signals_taken += 1

    def update_positions(self, candles: Dict[str, pd.Series], current_time: int):
        """
        Update all active positions with current candle data
        Check for exits and breakeven triggers
        """
        symbols_to_close = []

        for symbol, position in self.active_positions.items():
            if symbol not in candles:
                continue

            candle = candles[symbol]
            current_price = candle['close']

            # Update max price
            position.update_max_price(candle['high'])

            # Check for breakeven trigger
            position.check_breakeven(current_price)

            # Check for exit
            exit_info = position.check_exit(
                current_time=current_time,
                current_price=current_price,
                open_price=candle['open'],
                high=candle['high'],
                low=candle['low']
            )

            if exit_info:
                # Close position
                pnl_info = position.calculate_pnl(exit_info['price'], self.commission_rate)

                # Return capital
                exit_value = position.quantity * exit_info['price']
                self.balance += exit_value - pnl_info['exit_commission']

                # Record trade
                trade_record = {
                    'symbol': symbol,
                    'entry_time': datetime.fromtimestamp(position.entries[0]['time'] / 1000, tz=timezone.utc),
                    'exit_time': datetime.fromtimestamp(exit_info['time'] / 1000, tz=timezone.utc),
                    'avg_entry_price': position.avg_entry_price,
                    'exit_price': exit_info['price'],
                    'quantity': position.quantity,
                    'exit_reason': exit_info['reason'],
                    'net_pnl': pnl_info['net_pnl'],
                    'return_pct': pnl_info['return_pct'],
                    'duration_hours': pnl_info['duration_hours'],
                    'entry_count': position.entry_count,
                    'total_invested': pnl_info['total_invested'],
                    'breakeven_triggered': position.breakeven_triggered,
                    'rule': position.entries[0]['rule']
                }

                self.closed_trades.append(trade_record)
                symbols_to_close.append(symbol)

        # Remove closed positions
        for symbol in symbols_to_close:
            del self.active_positions[symbol]

    def run_backtest(self, signals_df: pd.DataFrame, candle_data: Dict[str, pd.DataFrame]):
        """
        Run the complete backtest

        Args:
            signals_df: DataFrame with all signals sorted by timestamp
            candle_data: Dict of {symbol: DataFrame} with OHLC data
        """
        print(f"\n{'='*60}")
        print(f"🚀 Running Pyramid Backtest")
        print(f"{'='*60}\n")
        print(f"Signals: {len(signals_df)}")
        print(f"Period: {signals_df['datetime'].min()} to {signals_df['datetime'].max()}")
        print(f"Initial Balance: ${self.initial_balance:,.2f}")
        print(f"Position Size: ${self.position_size:,.2f}")
        print(f"Max Active Trades: {self.max_active_trades}")
        print(f"\n{'='*60}\n")

        # Get unique timestamps for processing
        unique_times = sorted(signals_df['timestamp'].unique())

        for idx, current_time in enumerate(unique_times):
            if idx % 1000 == 0:
                progress = (idx / len(unique_times)) * 100
                print(f"Progress: {progress:.1f}% | Active: {len(self.active_positions)} | "
                      f"Closed: {len(self.closed_trades)} | Balance: ${self.balance:,.2f}")

            # Get all signals at this timestamp
            current_signals = signals_df[signals_df['timestamp'] == current_time]

            # Get current candles for all active positions
            current_candles = {}
            for symbol in list(self.active_positions.keys()):
                if symbol in candle_data:
                    symbol_df = candle_data[symbol]
                    matching_candles = symbol_df[symbol_df['timestamp'] == current_time]
                    if len(matching_candles) > 0:
                        current_candles[symbol] = matching_candles.iloc[0]

            # Update existing positions first (check exits, breakeven)
            self.update_positions(current_candles, current_time)

            # Process new signals
            for _, signal in current_signals.iterrows():
                symbol = signal['symbol']

                # Get current candle for this symbol
                if symbol in candle_data:
                    symbol_df = candle_data[symbol]
                    matching_candles = symbol_df[symbol_df['timestamp'] == current_time]
                    if len(matching_candles) > 0:
                        current_candle = matching_candles.iloc[0]
                        self.process_signal(signal, current_candle)

        # Close any remaining positions at end
        if self.active_positions:
            print(f"\n⚠️ Closing {len(self.active_positions)} remaining positions at end of period")
            final_time = unique_times[-1]
            final_candles = {}
            for symbol in self.active_positions.keys():
                if symbol in candle_data:
                    symbol_df = candle_data[symbol]
                    final_row = symbol_df[symbol_df['timestamp'] <= final_time].iloc[-1]
                    final_candles[symbol] = final_row

            # Force close with 'manual' reason
            for symbol, position in list(self.active_positions.items()):
                if symbol in final_candles:
                    candle = final_candles[symbol]
                    exit_info = {
                        'time': final_time,
                        'price': candle['close'],
                        'reason': 'manual'
                    }

                    pnl_info = position.calculate_pnl(exit_info['price'], self.commission_rate)
                    exit_value = position.quantity * exit_info['price']
                    self.balance += exit_value - pnl_info['exit_commission']

                    trade_record = {
                        'symbol': symbol,
                        'entry_time': datetime.fromtimestamp(position.entries[0]['time'] / 1000, tz=timezone.utc),
                        'exit_time': datetime.fromtimestamp(exit_info['time'] / 1000, tz=timezone.utc),
                        'avg_entry_price': position.avg_entry_price,
                        'exit_price': exit_info['price'],
                        'quantity': position.quantity,
                        'exit_reason': exit_info['reason'],
                        'net_pnl': pnl_info['net_pnl'],
                        'return_pct': pnl_info['return_pct'],
                        'duration_hours': pnl_info['duration_hours'],
                        'entry_count': position.entry_count,
                        'total_invested': pnl_info['total_invested'],
                        'breakeven_triggered': position.breakeven_triggered,
                        'rule': position.entries[0]['rule']
                    }

                    self.closed_trades.append(trade_record)

            self.active_positions.clear()

        print(f"\n{'='*60}")
        print(f"✅ Backtest Complete")
        print(f"{'='*60}\n")

    def get_results(self) -> Dict:
        """Calculate and return backtest results"""
        if not self.closed_trades:
            return self._empty_results()

        trades_df = pd.DataFrame(self.closed_trades)

        # Basic stats
        total_trades = len(trades_df)

        # CORRECTED: Breakeven = trades between -0.5% and +0.5% return
        # This captures trades that hit breakeven and closed near entry price
        winning_trades = len(trades_df[trades_df['return_pct'] > 0.5])
        losing_trades = len(trades_df[trades_df['return_pct'] < -0.5])
        breakeven_trades = len(trades_df[(trades_df['return_pct'] >= -0.5) & (trades_df['return_pct'] <= 0.5)])

        # Strike rates (separate percentages)
        win_strike_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        loss_strike_rate = (losing_trades / total_trades * 100) if total_trades > 0 else 0
        be_strike_rate = (breakeven_trades / total_trades * 100) if total_trades > 0 else 0

        # IMPORTANT: Include breakeven trades in win rate (protected capital = win)
        effective_wins = winning_trades + breakeven_trades
        effective_win_rate = (effective_wins / total_trades * 100) if total_trades > 0 else 0

        # P&L
        total_pnl = trades_df['net_pnl'].sum()
        gross_profit = trades_df[trades_df['net_pnl'] > 0]['net_pnl'].sum()
        gross_loss = abs(trades_df[trades_df['net_pnl'] < 0]['net_pnl'].sum())

        # Metrics
        avg_win = gross_profit / winning_trades if winning_trades > 0 else 0
        avg_loss = gross_loss / losing_trades if losing_trades > 0 else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # Pyramiding stats
        pyramided_trades = len(trades_df[trades_df['entry_count'] > 1])
        avg_entries_per_trade = trades_df['entry_count'].mean()

        # Equity curve for drawdown calculation
        trades_df_sorted = trades_df.sort_values('exit_time').copy()
        trades_df_sorted['cumulative_pnl'] = trades_df_sorted['net_pnl'].cumsum()
        trades_df_sorted['equity'] = self.initial_balance + trades_df_sorted['cumulative_pnl']
        trades_df_sorted['running_max'] = trades_df_sorted['equity'].cummax()
        trades_df_sorted['drawdown'] = trades_df_sorted['equity'] - trades_df_sorted['running_max']
        trades_df_sorted['drawdown_pct'] = (trades_df_sorted['drawdown'] / trades_df_sorted['running_max']) * 100

        max_drawdown = trades_df_sorted['drawdown'].min()
        max_drawdown_pct = trades_df_sorted['drawdown_pct'].min()

        # Additional metrics
        largest_win = trades_df['net_pnl'].max()
        largest_loss = trades_df['net_pnl'].min()

        # Sharpe ratio (simplified)
        returns = trades_df_sorted['net_pnl'].values
        sharpe_ratio = (np.mean(returns) / np.std(returns)) * np.sqrt(252) if np.std(returns) > 0 else 0

        # Exit reason breakdown
        exit_reasons = trades_df['exit_reason'].value_counts().to_dict()

        return {
            'initial_balance': self.initial_balance,
            'final_balance': self.balance,
            'total_return': self.balance - self.initial_balance,
            'total_return_pct': ((self.balance - self.initial_balance) / self.initial_balance) * 100,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'breakeven_trades': breakeven_trades,
            'win_strike_rate': win_strike_rate,  # % of trades that are wins
            'loss_strike_rate': loss_strike_rate,  # % of trades that are losses
            'be_strike_rate': be_strike_rate,  # % of trades that are breakeven
            'effective_win_rate': effective_win_rate,  # Wins + BE as wins
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'profit_factor': profit_factor,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'avg_trade_pnl': trades_df['net_pnl'].mean(),
            'avg_duration_hours': trades_df['duration_hours'].mean(),
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown_pct,
            'largest_win': largest_win,
            'largest_loss': largest_loss,
            'sharpe_ratio': sharpe_ratio,
            'pyramided_trades': pyramided_trades,
            'avg_entries_per_trade': avg_entries_per_trade,
            'total_signals': self.total_signals,
            'signals_taken': self.signals_taken,
            'signals_skipped_capital': self.signals_skipped_no_capital,
            'signals_skipped_max_trades': self.signals_skipped_max_trades,
            'pyramided_entries': self.pyramided_entries,
            'breakeven_triggered_count': len(trades_df[trades_df['breakeven_triggered'] == True]),
            'exit_reasons': exit_reasons,
            'equity_curve': trades_df_sorted[['exit_time', 'equity', 'cumulative_pnl', 'drawdown_pct']].to_dict('records'),
            'trades': self.closed_trades,
            'trades_df': trades_df_sorted  # For chart generation
        }

    def _empty_results(self) -> Dict:
        """Return empty results structure"""
        return {
            'initial_balance': self.initial_balance,
            'final_balance': self.balance,
            'total_return': 0,
            'total_return_pct': 0,
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'breakeven_trades': 0,
            'win_rate': 0,
            'gross_profit': 0,
            'gross_loss': 0,
            'profit_factor': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'avg_trade_pnl': 0,
            'avg_duration_hours': 0,
            'pyramided_trades': 0,
            'avg_entries_per_trade': 0,
            'total_signals': self.total_signals,
            'signals_taken': 0,
            'signals_skipped_capital': 0,
            'signals_skipped_max_trades': 0,
            'pyramided_entries': 0,
            'breakeven_triggered_count': 0,
            'trades': []
        }


def validate_and_fetch_data(signals_df: pd.DataFrame, data_dir: Path, interval: str = '5') -> Dict[str, pd.DataFrame]:
    """
    Validate data availability and fetch missing data if needed

    Args:
        signals_df: DataFrame with signals
        data_dir: Directory containing candle data
        interval: Candle interval (default: 5)

    Returns:
        Dict of {symbol: DataFrame} with complete data
    """
    from backtesting.data_fetcher import BybitDataFetcher
    fetcher = BybitDataFetcher()

    # Get required symbols and date range
    symbols = signals_df['symbol'].unique()
    start_ms = signals_df['timestamp'].min()
    end_ms = signals_df['timestamp'].max()

    start_date = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
    end_date = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc)

    print(f"\n{'='*60}")
    print(f"🔍 Validating Data Availability")
    print(f"{'='*60}\n")
    print(f"Required Period: {start_date.strftime('%Y-%m-%d %H:%M')} to {end_date.strftime('%Y-%m-%d %H:%M')}")
    print(f"Symbols Needed: {len(symbols)}")

    candle_data = {}
    symbols_ok = []
    symbols_missing = []
    symbols_incomplete = []

    # Check each symbol's data
    for idx, symbol in enumerate(symbols):
        if (idx + 1) % 20 == 0:
            print(f"Checking... {idx+1}/{len(symbols)}")

        csv_files = list(data_dir.glob(f"{symbol}_{interval}_*.csv"))

        if not csv_files:
            symbols_missing.append(symbol)
            continue

        # Load data from earliest file (max coverage)
        csv_file = sorted(csv_files)[0]
        df = fetcher.load_from_csv(csv_file)

        # Check if data covers required range
        data_start_ms = df['timestamp'].min()
        data_end_ms = df['timestamp'].max()

        # Allow 10-minute buffer for data range (2 candles on 5-min interval)
        buffer_ms = 10 * 60 * 1000

        if data_start_ms > (start_ms + buffer_ms) or data_end_ms < (end_ms - buffer_ms):
            symbols_incomplete.append({
                'symbol': symbol,
                'file': csv_file.name,
                'has_start': datetime.fromtimestamp(data_start_ms / 1000, tz=timezone.utc),
                'has_end': datetime.fromtimestamp(data_end_ms / 1000, tz=timezone.utc),
                'df': df
            })
        else:
            candle_data[symbol] = df
            symbols_ok.append(symbol)

    # Report status
    print(f"\n{'='*60}")
    print(f"📊 Data Validation Results")
    print(f"{'='*60}\n")
    print(f"✅ Complete Data: {len(symbols_ok)} symbols")
    print(f"⚠️  Incomplete Data: {len(symbols_incomplete)} symbols")
    print(f"❌ Missing Data: {len(symbols_missing)} symbols")

    # Fetch missing/incomplete data if needed
    symbols_to_fetch = []

    if symbols_missing:
        print(f"\n🔍 Missing data for {len(symbols_missing)} symbols:")
        for i in range(min(10, len(symbols_missing))):
            print(f"   - {symbols_missing[i]}")
        if len(symbols_missing) > 10:
            print(f"   ... and {len(symbols_missing) - 10} more")
        symbols_to_fetch.extend(symbols_missing)

    if symbols_incomplete:
        print(f"\n⚠️  Incomplete data for {len(symbols_incomplete)} symbols:")
        for i in range(min(10, len(symbols_incomplete))):
            info = symbols_incomplete[i]
            print(f"   - {info['symbol']}: has {info['has_start'].strftime('%Y-%m-%d')} to {info['has_end'].strftime('%Y-%m-%d')}")
        if len(symbols_incomplete) > 10:
            print(f"   ... and {len(symbols_incomplete) - 10} more")
        symbols_to_fetch.extend([s['symbol'] for s in symbols_incomplete])

    # Auto-fetch missing/incomplete data
    if symbols_to_fetch:
        print(f"\n{'='*60}")
        print(f"📥 Fetching Missing/Incomplete Data")
        print(f"{'='*60}\n")
        print(f"Fetching {len(symbols_to_fetch)} symbols from Bybit API...")
        print(f"This may take a few minutes...\n")

        new_data = fetcher.fetch_multiple_symbols(
            symbols_to_fetch,
            interval,
            start_ms,
            end_ms
        )

        # Save to CSV
        print(f"\n💾 Saving fetched data to CSV...")
        for symbol, df in new_data.items():
            if len(df) > 0:
                fetcher.save_to_csv(df, symbol, interval, data_dir)
                candle_data[symbol] = df
                print(f"   ✅ {symbol}: {len(df)} candles")

        print(f"\n✅ Fetched and saved data for {len(new_data)} symbols")

    print(f"\n{'='*60}")
    print(f"✅ Data Validation Complete")
    print(f"{'='*60}\n")
    print(f"Total symbols ready: {len(candle_data)}/{len(symbols)}")

    if len(candle_data) < len(symbols):
        missing_final = len(symbols) - len(candle_data)
        print(f"\n⚠️  Warning: {missing_final} symbols still have no data (will be skipped)")

    return candle_data


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description='Run pyramid backtest from pre-generated signals')

    parser.add_argument('--signals', type=str, required=True,
                       help='Path to signals CSV file')
    parser.add_argument('--data-dir', type=str, default='backtesting/data',
                       help='Directory with candle data')
    parser.add_argument('--initial-balance', type=float, default=10000,
                       help='Initial balance (default: 10000)')
    parser.add_argument('--position-size', type=float, default=200,
                       help='Position size per trade (default: 200)')
    parser.add_argument('--max-trades', type=int, default=30,
                       help='Max concurrent non-breakeven positions (default: 30)')
    parser.add_argument('--output', type=str, default='backtesting/reports/pyramid_backtest_results.csv',
                       help='Output file for results')
    parser.add_argument('--no-fetch', action='store_true',
                       help='Disable auto-fetching of missing data')

    args = parser.parse_args()

    # Load signals
    print(f"📥 Loading signals from {args.signals}...")
    signals_df = pd.read_csv(args.signals)
    print(f"✅ Loaded {len(signals_df)} signals")

    symbols = signals_df['symbol'].unique()
    print(f"📊 Unique symbols: {len(symbols)}")

    # Validate and load candle data (with auto-fetch if needed)
    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    if args.no_fetch:
        # Old behavior: just load existing data
        print(f"\n📥 Loading candle data (no auto-fetch)...")
        from backtesting.data_fetcher import BybitDataFetcher
        fetcher = BybitDataFetcher()
        candle_data = {}

        for symbol in symbols:
            csv_files = list(data_dir.glob(f"{symbol}_5_*.csv"))
            if csv_files:
                csv_file = sorted(csv_files)[0]
                df = fetcher.load_from_csv(csv_file)
                candle_data[symbol] = df

        print(f"✅ Loaded candle data for {len(candle_data)} symbols")
    else:
        # New behavior: validate and auto-fetch missing data
        candle_data = validate_and_fetch_data(signals_df, data_dir)

    # Run backtest
    engine = PyramidBacktestEngine(
        initial_balance=args.initial_balance,
        position_size=args.position_size,
        max_active_trades=args.max_trades
    )

    engine.run_backtest(signals_df, candle_data)

    # Get and display results
    results = engine.get_results()

    print(f"\n{'='*60}")
    print(f"📊 Results Summary")
    print(f"{'='*60}\n")
    print(f"Final Balance: ${results['final_balance']:,.2f}")
    print(f"Total Return: ${results['total_return']:,.2f} ({results['total_return_pct']:.2f}%)")
    print(f"Total Trades: {results['total_trades']}")
    print(f"  Wins: {results['winning_trades']} | Losses: {results['losing_trades']} | Breakeven: {results['breakeven_trades']}")
    print(f"\n📈 Strike Rates:")
    print(f"  Win Rate: {results['win_strike_rate']:.2f}% ({results['winning_trades']} trades >0.5% profit)")
    print(f"  Loss Rate: {results['loss_strike_rate']:.2f}% ({results['losing_trades']} trades <-0.5% loss)")
    print(f"  Breakeven Rate: {results['be_strike_rate']:.2f}% ({results['breakeven_trades']} trades ±0.5%)")
    print(f"  Effective Win Rate: {results['effective_win_rate']:.2f}% (wins + breakeven)")
    print(f"\nProfit Factor: {results['profit_factor']:.2f}")
    print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
    print(f"Max Drawdown: ${results['max_drawdown']:,.2f} ({results['max_drawdown_pct']:.2f}%)")
    print(f"Avg Trade P&L: ${results['avg_trade_pnl']:.2f}")
    print(f"Avg Duration: {results['avg_duration_hours']:.2f}h")
    print(f"\n💰 Best/Worst:")
    print(f"  Largest Win: ${results['largest_win']:,.2f}")
    print(f"  Largest Loss: ${results['largest_loss']:,.2f}")
    print(f"\n🔄 Pyramiding:")
    print(f"  Pyramided Trades: {results['pyramided_trades']}")
    print(f"  Avg Entries/Trade: {results['avg_entries_per_trade']:.2f}")
    print(f"  Pyramided Entries: {results['pyramided_entries']}")
    print(f"\n📊 Signals:")
    print(f"  Total Signals: {results['total_signals']}")
    print(f"  Signals Taken: {results['signals_taken']}")
    print(f"  Skipped (Capital): {results['signals_skipped_capital']}")
    print(f"  Skipped (Max Trades): {results['signals_skipped_max_trades']}")
    print(f"{'='*60}\n")

    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    trades_df = pd.DataFrame(results['trades'])
    trades_df.to_csv(output_path, index=False)
    print(f"💾 Saved results to {output_path}")

    # Save summary JSON
    summary_path = output_path.parent / f"{output_path.stem}_summary.json"
    summary = {k: v for k, v in results.items() if k not in ['trades', 'equity_curve']}
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"📋 Saved summary to {summary_path}")

    # Generate PDF report
    print(f"\n📄 Generating professional PDF report...")
    pdf_path = generate_pdf_report(results, output_path.parent / f"{output_path.stem}_report.pdf")
    if pdf_path:
        print(f"✅ PDF report saved to {pdf_path}")


def generate_pdf_report(results: Dict, output_path: Path) -> Optional[Path]:
    """Generate professional PDF performance report with charts"""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from io import BytesIO
    except ImportError:
        print("⚠️ reportlab or matplotlib not installed. Install with: pip install reportlab matplotlib")
        print("📄 Skipping PDF generation...")
        return None

    # Generate charts first
    trades_df = results.get('trades_df')
    if trades_df is None or len(trades_df) == 0:
        print("⚠️ No trade data available for charts")
        return None

    chart_dir = output_path.parent / 'charts'
    chart_dir.mkdir(exist_ok=True)

    # Chart 1: Equity Curve
    equity_chart_path = chart_dir / 'equity_curve.png'
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(trades_df['exit_time'], trades_df['equity'], linewidth=2, color='#1f77b4')
    ax.axhline(y=results['initial_balance'], color='gray', linestyle='--', alpha=0.5, label='Initial Balance')
    ax.set_title('Equity Curve', fontsize=14, fontweight='bold')
    ax.set_xlabel('Date')
    ax.set_ylabel('Account Balance ($)')
    ax.grid(True, alpha=0.3)
    ax.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(equity_chart_path, dpi=150, bbox_inches='tight')
    plt.close()

    # Chart 2: Drawdown
    drawdown_chart_path = chart_dir / 'drawdown.png'
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.fill_between(trades_df['exit_time'], trades_df['drawdown_pct'], 0,
                     color='red', alpha=0.3, label='Drawdown')
    ax.plot(trades_df['exit_time'], trades_df['drawdown_pct'], linewidth=1.5, color='darkred')
    ax.set_title('Drawdown Over Time', fontsize=14, fontweight='bold')
    ax.set_xlabel('Date')
    ax.set_ylabel('Drawdown (%)')
    ax.grid(True, alpha=0.3)
    ax.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(drawdown_chart_path, dpi=150, bbox_inches='tight')
    plt.close()

    # Chart 3: PnL Distribution
    distribution_chart_path = chart_dir / 'pnl_distribution.png'
    fig, ax = plt.subplots(figsize=(10, 4))
    pnl_values = [t['net_pnl'] for t in results['trades']]
    ax.hist(pnl_values, bins=50, color='#1f77b4', alpha=0.7, edgecolor='black')
    ax.axvline(x=0, color='red', linestyle='--', linewidth=2, label='Break Even')
    ax.set_title('P&L Distribution', fontsize=14, fontweight='bold')
    ax.set_xlabel('Net P&L ($)')
    ax.set_ylabel('Number of Trades')
    ax.grid(True, alpha=0.3, axis='y')
    ax.legend()
    plt.tight_layout()
    plt.savefig(distribution_chart_path, dpi=150, bbox_inches='tight')
    plt.close()

    # Chart 4: Cumulative PnL
    cumulative_chart_path = chart_dir / 'cumulative_pnl.png'
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.fill_between(trades_df['exit_time'], 0, trades_df['cumulative_pnl'],
                     where=(trades_df['cumulative_pnl'] >= 0), color='green', alpha=0.3, label='Profit')
    ax.fill_between(trades_df['exit_time'], 0, trades_df['cumulative_pnl'],
                     where=(trades_df['cumulative_pnl'] < 0), color='red', alpha=0.3, label='Loss')
    ax.plot(trades_df['exit_time'], trades_df['cumulative_pnl'], linewidth=2, color='black')
    ax.set_title('Cumulative P&L', fontsize=14, fontweight='bold')
    ax.set_xlabel('Date')
    ax.set_ylabel('Cumulative P&L ($)')
    ax.grid(True, alpha=0.3)
    ax.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(cumulative_chart_path, dpi=150, bbox_inches='tight')
    plt.close()

    # Create document
    doc = SimpleDocTemplate(str(output_path), pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1f77b4'),
        spaceAfter=20,
        alignment=TA_CENTER
    )
    title = Paragraph("Pyramid Backtest Performance Report", title_style)
    story.append(title)
    story.append(Spacer(1, 0.2*inch))

    # Metadata
    meta_text = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    story.append(Paragraph(meta_text, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))

    # Key Performance Metrics Table
    story.append(Paragraph("📊 Key Performance Metrics", styles['Heading2']))
    story.append(Spacer(1, 0.1*inch))

    kpi_data = [
        ['Metric', 'Value'],
        ['Initial Balance', f"${results['initial_balance']:,.2f}"],
        ['Final Balance', f"${results['final_balance']:,.2f}"],
        ['Total Return', f"${results['total_return']:,.2f} ({results['total_return_pct']:.2f}%)"],
        ['Total Trades', str(results['total_trades'])],
        ['Profit Factor', f"{results['profit_factor']:.2f}"],
        ['Sharpe Ratio', f"{results['sharpe_ratio']:.2f}"],
        ['Max Drawdown', f"${results['max_drawdown']:,.2f} ({results['max_drawdown_pct']:.2f}%)"],
    ]

    kpi_table = Table(kpi_data, colWidths=[3*inch, 2.5*inch])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f77b4')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 0.3*inch))

    # Strike Rate Analysis
    story.append(Paragraph("🎯 Strike Rate Analysis", styles['Heading2']))
    story.append(Spacer(1, 0.1*inch))

    strike_data = [
        ['Category', 'Count', 'Rate'],
        ['Winning Trades (>0.5%)', str(results['winning_trades']), f"{results['win_strike_rate']:.2f}%"],
        ['Losing Trades (<-0.5%)', str(results['losing_trades']), f"{results['loss_strike_rate']:.2f}%"],
        ['Breakeven Trades (±0.5%)', str(results['breakeven_trades']), f"{results['be_strike_rate']:.2f}%"],
        ['Effective Win Rate', f"{results['winning_trades'] + results['breakeven_trades']}", f"{results['effective_win_rate']:.2f}%"],
    ]

    strike_table = Table(strike_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
    strike_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f77b4')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(strike_table)
    story.append(Spacer(1, 0.3*inch))

    # Trade Statistics
    story.append(Paragraph("📈 Trade Statistics", styles['Heading2']))
    story.append(Spacer(1, 0.1*inch))

    trade_stats_data = [
        ['Metric', 'Value'],
        ['Gross Profit', f"${results['gross_profit']:,.2f}"],
        ['Gross Loss', f"${results['gross_loss']:,.2f}"],
        ['Avg Win', f"${results['avg_win']:,.2f}"],
        ['Avg Loss', f"${results['avg_loss']:,.2f}"],
        ['Largest Win', f"${results['largest_win']:,.2f}"],
        ['Largest Loss', f"${results['largest_loss']:,.2f}"],
        ['Avg Duration', f"{results['avg_duration_hours']:.2f}h"],
    ]

    trade_table = Table(trade_stats_data, colWidths=[3*inch, 2.5*inch])
    trade_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f77b4')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(trade_table)
    story.append(Spacer(1, 0.3*inch))

    # Pyramiding Statistics
    story.append(Paragraph("🔄 Pyramiding Statistics", styles['Heading2']))
    story.append(Spacer(1, 0.1*inch))

    pyramid_data = [
        ['Metric', 'Value'],
        ['Pyramided Trades', str(results['pyramided_trades'])],
        ['Avg Entries per Trade', f"{results['avg_entries_per_trade']:.2f}"],
        ['Total Pyramided Entries', str(results['pyramided_entries'])],
        ['Breakeven Triggered', str(results['breakeven_triggered_count'])],
    ]

    pyramid_table = Table(pyramid_data, colWidths=[3*inch, 2.5*inch])
    pyramid_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f77b4')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(pyramid_table)
    story.append(Spacer(1, 0.3*inch))

    # Exit Reasons
    story.append(Paragraph("🚪 Exit Reasons Breakdown", styles['Heading2']))
    story.append(Spacer(1, 0.1*inch))

    exit_data = [['Exit Reason', 'Count']]
    for reason, count in results['exit_reasons'].items():
        exit_data.append([reason.replace('_', ' ').title(), str(count)])

    exit_table = Table(exit_data, colWidths=[3*inch, 2.5*inch])
    exit_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f77b4')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(exit_table)
    story.append(PageBreak())

    # Performance Charts
    story.append(Paragraph("📊 Performance Charts", styles['Heading2']))
    story.append(Spacer(1, 0.2*inch))

    # Chart 1: Equity Curve
    story.append(Paragraph("Equity Curve", styles['Heading3']))
    story.append(Spacer(1, 0.1*inch))
    equity_img = Image(str(equity_chart_path), width=6.5*inch, height=2.6*inch)
    story.append(equity_img)
    story.append(Spacer(1, 0.3*inch))

    # Chart 2: Cumulative PnL
    story.append(Paragraph("Cumulative P&L", styles['Heading3']))
    story.append(Spacer(1, 0.1*inch))
    cumulative_img = Image(str(cumulative_chart_path), width=6.5*inch, height=2.6*inch)
    story.append(cumulative_img)
    story.append(PageBreak())

    # Chart 3: Drawdown
    story.append(Paragraph("Drawdown Analysis", styles['Heading3']))
    story.append(Spacer(1, 0.1*inch))
    drawdown_img = Image(str(drawdown_chart_path), width=6.5*inch, height=2.6*inch)
    story.append(drawdown_img)
    story.append(Spacer(1, 0.3*inch))

    # Chart 4: PnL Distribution
    story.append(Paragraph("P&L Distribution", styles['Heading3']))
    story.append(Spacer(1, 0.1*inch))
    distribution_img = Image(str(distribution_chart_path), width=6.5*inch, height=2.6*inch)
    story.append(distribution_img)

    # Build PDF
    doc.build(story)

    print(f"📊 Charts saved to: {chart_dir}")
    return output_path


if __name__ == "__main__":
    main()
