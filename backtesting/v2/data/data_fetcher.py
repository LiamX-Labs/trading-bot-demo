#!/usr/bin/env python3
"""
Data Fetcher for Backtesting System
Fetches OHLCV (Open, High, Low, Close, Volume) historical data from Bybit
"""

import sys
import os
from pathlib import Path
import time
import hmac
import hashlib
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict

# Add parent directory to path for imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from dotenv import load_dotenv
load_dotenv(parent_dir / ".env")


class BybitDataFetcher:
    """Fetches historical OHLCV data from Bybit for backtesting"""

    def __init__(self, use_cache: bool = False):
        self.use_cache = use_cache
        self.cache = None  # Cache disabled for now in V2

        # Load from environment or use defaults
        self.api_key = os.getenv('API_KEY', '')
        self.api_secret = os.getenv('API_SECRET', '')
        self.base_url = os.getenv('BASE_URL', 'https://api.bybit.com')
        self.recv_window = int(os.getenv('RECV_WINDOW', '5000'))

    def _get_server_time(self) -> str:
        """Get Bybit server time"""
        try:
            resp = requests.get(f"{self.base_url}/v5/market/time", timeout=3)
            resp.raise_for_status()
            data = resp.json()

            if "result" in data and "timeSecond" in data["result"]:
                server_time = int(data["result"]["timeSecond"]) * 1000
            elif "time" in data:
                server_time = int(data["time"])
            else:
                raise ValueError(f"Unexpected response format: {data}")

            return str(server_time)
        except Exception as e:
            print(f"⚠️ Failed to get server time: {e}")
            return str(int(datetime.now(timezone.utc).timestamp() * 1000))

    def fetch_klines(
        self,
        symbol: str,
        interval: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 200
    ) -> pd.DataFrame:
        """
        Fetch OHLCV kline/candlestick data from Bybit

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            interval: Candle interval (e.g., "1", "5", "15", "60", "240", "D")
            start_time: Start time in milliseconds
            end_time: End time in milliseconds
            limit: Number of candles to fetch (max 200 per request)

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        endpoint = "/v5/market/kline"
        all_klines = []

        # If no time range specified, fetch recent data
        if not start_time:
            end_time = int(datetime.now(timezone.utc).timestamp() * 1000)
            # Default to 200 candles back
            if interval == "1":
                start_time = end_time - (200 * 60 * 1000)  # 1 min
            elif interval == "5":
                start_time = end_time - (200 * 5 * 60 * 1000)  # 5 min
            elif interval == "15":
                start_time = end_time - (200 * 15 * 60 * 1000)  # 15 min
            elif interval == "60":
                start_time = end_time - (200 * 60 * 60 * 1000)  # 1 hour
            elif interval == "240":
                start_time = end_time - (200 * 4 * 60 * 60 * 1000)  # 4 hour
            elif interval == "D":
                start_time = end_time - (200 * 24 * 60 * 60 * 1000)  # 1 day
            else:
                start_time = end_time - (200 * 60 * 1000)  # Default 1 min

        if not end_time:
            end_time = int(datetime.now(timezone.utc).timestamp() * 1000)

        # Save original timestamps for caching (these will be modified during pagination)
        original_start_time = start_time
        original_end_time = end_time

        print(f"📥 Fetching {symbol} {interval}-interval klines...")
        print(f"   Range: {datetime.fromtimestamp(start_time/1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M')} to {datetime.fromtimestamp(end_time/1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M')}")

        # Check cache first (if enabled)
        if self.use_cache and self.cache:
            cached_df = self.cache.get(symbol, interval, original_start_time, original_end_time)
            if cached_df is not None:
                print(f"   ✅ Loaded {len(cached_df)} candles from cache")
                return cached_df

        current_start = start_time
        chunk_count = 0
        total_time_ms = end_time - start_time

        # Calculate expected number of chunks for progress tracking
        if interval == "5":
            interval_ms = 5 * 60 * 1000
        elif interval == "15":
            interval_ms = 15 * 60 * 1000
        elif interval == "60":
            interval_ms = 60 * 60 * 1000
        elif interval == "240":
            interval_ms = 240 * 60 * 1000
        elif interval == "D":
            interval_ms = 24 * 60 * 60 * 1000
        else:
            interval_ms = 60 * 1000

        expected_candles = total_time_ms // interval_ms
        expected_chunks = max(1, int(expected_candles // 200) + 1)

        original_end_time = end_time

        while True:
            chunk_count += 1

            # Calculate progress based on how much time range we've covered
            # Since we're working backwards from end_time, progress = how much we've gone back
            time_covered = original_end_time - end_time
            time_progress = (time_covered / total_time_ms) * 100
            progress_pct = min(100, int(time_progress))
            current_date = datetime.fromtimestamp(end_time/1000, tz=timezone.utc).strftime('%Y-%m-%d')

            # Update expected chunks dynamically based on actual progress
            if chunk_count > 1 and len(all_klines) > 0:
                # Estimate total chunks based on current progress
                estimated_total = int((chunk_count / time_progress) * 100) if time_progress > 0 else expected_chunks
                display_total = max(chunk_count, estimated_total)
            else:
                display_total = expected_chunks

            print(f"   📊 Progress: {progress_pct}% | Chunk {chunk_count}/{display_total} | Current: {current_date} | Candles: {len(all_klines)}", end='\r', flush=True)

            # Build params (no authentication needed for public endpoint)
            params = {
                "category": "linear",
                "symbol": symbol,
                "interval": interval,
                "start": str(current_start),
                "end": str(end_time),
                "limit": str(limit)
            }

            try:
                response = requests.get(
                    f"{self.base_url}{endpoint}",
                    params=params,
                    timeout=10
                )
                response.raise_for_status()
                data = response.json()

                if data["retCode"] != 0:
                    print(f"\n   ⚠️ API Error: {data['retMsg']}")
                    break

                result = data.get("result", {})
                klines = result.get("list", [])

                if not klines:
                    break

                all_klines.extend(klines)

                # Bybit returns data in REVERSE chronological order (newest first)
                # So klines[0] is newest, klines[-1] is oldest
                oldest_timestamp = int(klines[-1][0])
                newest_timestamp = int(klines[0][0])

                # If the oldest timestamp in this batch is <= start_time, we're done
                if oldest_timestamp <= start_time:
                    break

                # Move to next chunk - request data BEFORE the oldest timestamp we just got
                current_start = start_time
                end_time = oldest_timestamp - 1

                # Small delay to avoid rate limiting
                time.sleep(0.1)

            except Exception as e:
                print(f"\n   ❌ Error fetching chunk {chunk_count}: {e}")
                break

        print(f"\n✅ Fetched {len(all_klines)} candles across {chunk_count} chunks")

        if not all_klines:
            return pd.DataFrame()

        # Convert to DataFrame
        # Bybit kline format: [timestamp, open, high, low, close, volume, turnover]
        df = pd.DataFrame(all_klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'
        ])

        # Convert types
        df['timestamp'] = pd.to_numeric(df['timestamp'])
        df['open'] = pd.to_numeric(df['open'])
        df['high'] = pd.to_numeric(df['high'])
        df['low'] = pd.to_numeric(df['low'])
        df['close'] = pd.to_numeric(df['close'])
        df['volume'] = pd.to_numeric(df['volume'])
        df['turnover'] = pd.to_numeric(df['turnover'])

        # Add datetime column for convenience
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

        # Sort by timestamp (oldest first)
        df = df.sort_values('timestamp').reset_index(drop=True)

        # Remove turnover column (not needed for backtesting)
        df = df.drop('turnover', axis=1)

        # Save to cache (use ORIGINAL requested timestamps for exact key matching)
        if self.use_cache and self.cache and len(df) > 0:
            self.cache.put(symbol, interval, original_start_time, original_end_time, df)

        return df

    def fetch_multiple_symbols(
        self,
        symbols: List[str],
        interval: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch klines for multiple symbols

        Returns:
            Dictionary mapping symbol to DataFrame
        """
        data = {}
        total_symbols = len(symbols)

        for idx, symbol in enumerate(symbols, 1):
            print(f"\n{'='*60}")
            print(f"📊 Symbol {idx}/{total_symbols}: {symbol}")
            df = self.fetch_klines(symbol, interval, start_time, end_time)
            if not df.empty:
                data[symbol] = df
                print(f"✅ {symbol} complete ({idx}/{total_symbols})")
            else:
                print(f"⚠️ No data fetched for {symbol}")

            # Delay between symbols to avoid rate limiting
            time.sleep(0.5)

        print(f"\n{'='*60}")
        print(f"🎉 Data fetch complete: {len(data)}/{total_symbols} symbols successful")
        print(f"{'='*60}\n")

        return data

    def save_to_csv(self, df: pd.DataFrame, symbol: str, interval: str, output_dir: Path):
        """Save DataFrame to CSV file"""
        output_dir.mkdir(parents=True, exist_ok=True)

        start_date = df['datetime'].iloc[0].strftime('%Y%m%d')
        end_date = df['datetime'].iloc[-1].strftime('%Y%m%d')

        filename = f"{symbol}_{interval}_{start_date}_{end_date}.csv"
        filepath = output_dir / filename

        df.to_csv(filepath, index=False)
        print(f"💾 Saved to {filepath}")

        return filepath

    def load_from_csv(self, filepath: Path) -> pd.DataFrame:
        """Load DataFrame from CSV file"""
        df = pd.read_csv(filepath)
        df['datetime'] = pd.to_datetime(df['datetime'])
        return df


def main():
    """Example usage"""
    import argparse

    parser = argparse.ArgumentParser(description='Fetch historical OHLCV data from Bybit')
    parser.add_argument('--symbols', type=str, nargs='+',
                       default=['BTCUSDT', 'ETHUSDT'],
                       help='Symbols to fetch (default: BTCUSDT ETHUSDT)')
    parser.add_argument('--interval', type=str, default='5',
                       help='Candle interval: 1, 5, 15, 60, 240, D (default: 5)')
    parser.add_argument('--days', type=int, default=7,
                       help='Number of days of historical data (default: 7)')
    parser.add_argument('--output-dir', type=str, default='backtesting/data',
                       help='Output directory for CSV files')

    args = parser.parse_args()

    # Calculate time range
    end_time = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_time = end_time - (args.days * 24 * 60 * 60 * 1000)

    print(f"\n{'='*60}")
    print(f"📊 Bybit Historical Data Fetcher")
    print(f"{'='*60}\n")
    print(f"Symbols: {', '.join(args.symbols)}")
    print(f"Interval: {args.interval}")
    print(f"Period: Last {args.days} days")
    print(f"Output: {args.output_dir}")
    print(f"\n{'='*60}\n")

    fetcher = BybitDataFetcher()
    output_dir = Path(args.output_dir)

    data = fetcher.fetch_multiple_symbols(
        args.symbols,
        args.interval,
        start_time,
        end_time
    )

    print(f"\n{'='*60}")
    print(f"💾 Saving to CSV files...")
    print(f"{'='*60}\n")

    for symbol, df in data.items():
        fetcher.save_to_csv(df, symbol, args.interval, output_dir)

    print(f"\n{'='*60}")
    print(f"✅ Data fetch complete!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
