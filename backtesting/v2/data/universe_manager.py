#!/usr/bin/env python3
"""
Token Universe Scanner
Scans Bybit for USDT tokens with >$10M volume twice per week (Monday & Thursday)
Saves historical snapshots for reproducible backtesting
"""

import sys
from pathlib import Path
import json
import requests
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
import time
import os

# Add parent directory to path for imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from dotenv import load_dotenv
load_dotenv(parent_dir / ".env")

from utils.config_loader import BacktestConfig


class TokenUniverseScanner:
    """Scans and stores historical token universe snapshots"""

    def __init__(self, output_dir: Path = None, config: Optional[BacktestConfig] = None):
        # Use config or environment variable or default
        self.base_url = os.getenv('BASE_URL', 'https://api.bybit.com')

        # Volume filter from config or default
        if config:
            self.volume_filter_usd = config.volume_filter_usd if hasattr(config, 'volume_filter_usd') else 10_000_000
        else:
            self.volume_filter_usd = 10_000_000  # $10M minimum volume

        # Default to parent directory's token_universe if not specified
        if output_dir:
            self.output_dir = output_dir
        else:
            # Try V1 location first (backtesting/token_universe/)
            v1_universe_dir = Path(__file__).parent.parent.parent / "token_universe"
            if v1_universe_dir.exists():
                self.output_dir = v1_universe_dir
            else:
                # Fallback to V2 location
                self.output_dir = Path(__file__).parent / "token_universe"

        self.output_dir.mkdir(parents=True, exist_ok=True)

    def fetch_symbols_for_date(self, target_date: datetime) -> Dict:
        """
        Fetch symbols with >$10M volume for a specific date

        Note: Bybit API returns current 24h volume, so this is best run
        on the actual day. For historical data, we approximate.
        """
        try:
            print(f"📊 Scanning tokens for {target_date.strftime('%Y-%m-%d')}...")

            resp = requests.get(
                f"{self.base_url}/v5/market/tickers",
                params={"category": "linear"},
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("retCode") != 0:
                print(f"❌ API Error: {data.get('retMsg')}")
                return None

            symbols_data = []

            for ticker in data.get("result", {}).get("list", []):
                symbol = ticker.get("symbol", "")
                volume_24h = float(ticker.get("turnover24h", 0))
                price = float(ticker.get("lastPrice", 0))
                volume_change = float(ticker.get("volume24h", 0))
                price_change_pct = float(ticker.get("price24hPcnt", 0)) * 100

                # Filter: USDT pairs with >$10M volume
                if symbol.endswith("USDT") and volume_24h > self.volume_filter_usd:
                    symbols_data.append({
                        "symbol": symbol,
                        "volume_24h_usd": round(volume_24h, 2),
                        "price": round(price, 8),
                        "volume_24h_base": round(volume_change, 4),
                        "price_change_24h_pct": round(price_change_pct, 2)
                    })

            # Sort by volume (highest first)
            symbols_data.sort(key=lambda x: x["volume_24h_usd"], reverse=True)

            # Create snapshot
            snapshot = {
                "scan_date": target_date.strftime("%Y-%m-%d"),
                "scan_timestamp": target_date.isoformat(),
                "volume_filter_usd": self.volume_filter_usd,
                "total_symbols": len(symbols_data),
                "symbols": [s["symbol"] for s in symbols_data],
                "symbols_detailed": symbols_data,
                "top_10_by_volume": [
                    f"{s['symbol']} (${s['volume_24h_usd']:,.0f})"
                    for s in symbols_data[:10]
                ]
            }

            print(f"✅ Found {len(symbols_data)} symbols with >${self.volume_filter_usd:,} volume")
            print(f"   Top 5: {', '.join([s['symbol'] for s in symbols_data[:5]])}")

            return snapshot

        except Exception as e:
            print(f"❌ Error scanning tokens: {e}")
            return None

    def save_snapshot(self, snapshot: Dict, filename: Optional[str] = None) -> Path:
        """Save snapshot to JSON file"""
        if filename is None:
            filename = f"universe_{snapshot['scan_date']}.json"

        filepath = self.output_dir / filename

        with open(filepath, 'w') as f:
            json.dump(snapshot, f, indent=2)

        print(f"💾 Saved snapshot to {filepath}")
        return filepath

    def load_snapshot(self, date_str: str) -> Optional[Dict]:
        """Load snapshot for a specific date"""
        filepath = self.output_dir / f"universe_{date_str}.json"

        if not filepath.exists():
            print(f"⚠️ No snapshot found for {date_str}")
            return None

        with open(filepath, 'r') as f:
            return json.load(f)

    def get_symbols_for_date(self, target_date: datetime) -> List[str]:
        """
        Get symbols for a specific date
        Uses Monday/Thursday snapshots with forward-fill logic
        """
        date_str = target_date.strftime("%Y-%m-%d")

        # Try exact date first
        snapshot = self.load_snapshot(date_str)
        if snapshot:
            return snapshot["symbols"]

        # Find the most recent Monday or Thursday before this date
        scan_date = self.get_previous_scan_date(target_date)
        scan_date_str = scan_date.strftime("%Y-%m-%d")

        print(f"📅 Using {scan_date_str} snapshot for {date_str}")
        snapshot = self.load_snapshot(scan_date_str)

        if snapshot:
            return snapshot["symbols"]

        print(f"⚠️ No snapshot available for {date_str} or prior scan dates")
        return []

    def get_previous_scan_date(self, target_date: datetime) -> datetime:
        """
        Get the most recent Monday or Thursday before target_date
        Scan days: Monday (0) and Thursday (3)
        """
        current = target_date

        # Go back day by day until we find a Monday or Thursday
        while True:
            weekday = current.weekday()
            if weekday in [0, 3]:  # Monday or Thursday
                return current
            current = current - timedelta(days=1)

    def get_next_scan_date(self, current_date: datetime) -> datetime:
        """Get the next Monday or Thursday after current_date"""
        current = current_date + timedelta(days=1)

        while True:
            weekday = current.weekday()
            if weekday in [0, 3]:  # Monday or Thursday
                return current
            current = current + timedelta(days=1)

    def generate_historical_snapshots(
        self,
        start_date: datetime,
        end_date: datetime,
        delay_seconds: float = 1.0,
        daily: bool = False
    ) -> List[Path]:
        """
        Generate snapshots for all Monday/Thursday dates in a range (or daily if specified)

        Note: This generates snapshots with current data (not historical)
        Best used to create snapshots going forward, not retroactively
        """
        saved_files = []
        current = start_date

        print(f"\n{'='*60}")
        print(f"Generating Token Universe Snapshots")
        print(f"{'='*60}\n")
        print(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        if daily:
            print(f"Scan Days: DAILY")
        else:
            print(f"Scan Days: Monday & Thursday")
        print(f"Volume Filter: >${self.volume_filter_usd:,} USD")
        print(f"\n{'='*60}\n")

        while current <= end_date:
            weekday = current.weekday()

            # Check if we should scan this day
            should_scan = daily or weekday in [0, 3]  # Daily or Monday/Thursday

            if should_scan:
                day_name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][weekday]
                print(f"📅 {day_name}, {current.strftime('%Y-%m-%d')}")

                # Check if snapshot already exists
                filename = f"universe_{current.strftime('%Y-%m-%d')}.json"
                filepath = self.output_dir / filename

                if filepath.exists():
                    print(f"   ⏭️  Snapshot already exists, skipping...")
                else:
                    # Fetch and save
                    snapshot = self.fetch_symbols_for_date(current)

                    if snapshot:
                        saved_path = self.save_snapshot(snapshot)
                        saved_files.append(saved_path)

                    # Delay to avoid rate limiting
                    if delay_seconds > 0:
                        time.sleep(delay_seconds)

                print()

            current += timedelta(days=1)

        print(f"{'='*60}")
        print(f"✅ Generated {len(saved_files)} new snapshots")
        print(f"{'='*60}\n")

        return saved_files

    def scan_today(self) -> Optional[Path]:
        """Scan and save token universe for today"""
        today = datetime.now(timezone.utc).date()
        today_dt = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)

        # Check if today is Monday or Thursday
        weekday = today_dt.weekday()
        if weekday not in [0, 3]:
            day_name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][weekday]
            print(f"⚠️ Today is {day_name}, not a scan day (Monday/Thursday)")
            print(f"   Next scan: {self.get_next_scan_date(today_dt).strftime('%Y-%m-%d')}")
            return None

        snapshot = self.fetch_symbols_for_date(today_dt)

        if snapshot:
            return self.save_snapshot(snapshot)

        return None

    def list_available_snapshots(self) -> List[str]:
        """List all available snapshot dates"""
        snapshots = sorted(self.output_dir.glob("universe_*.json"))
        dates = [s.stem.replace("universe_", "") for s in snapshots]
        return dates

    def get_summary(self) -> Dict:
        """Get summary of available snapshots"""
        dates = self.list_available_snapshots()

        if not dates:
            return {
                "total_snapshots": 0,
                "date_range": None,
                "snapshots": []
            }

        # Load first and last for summary
        first_snapshot = self.load_snapshot(dates[0])
        last_snapshot = self.load_snapshot(dates[-1])

        return {
            "total_snapshots": len(dates),
            "date_range": f"{dates[0]} to {dates[-1]}",
            "first_snapshot": {
                "date": dates[0],
                "symbols": first_snapshot["total_symbols"] if first_snapshot else 0
            },
            "last_snapshot": {
                "date": dates[-1],
                "symbols": last_snapshot["total_symbols"] if last_snapshot else 0
            },
            "all_dates": dates
        }


def main():
    """Command-line interface"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Token Universe Scanner - Track tradeable tokens over time',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan today (if Monday or Thursday)
  python backtesting/token_universe_scanner.py --scan-today

  # Generate historical snapshots for date range
  python backtesting/token_universe_scanner.py --start 2025-09-01 --end 2025-10-13

  # List available snapshots
  python backtesting/token_universe_scanner.py --list

  # Show summary
  python backtesting/token_universe_scanner.py --summary

  # Get symbols for specific date
  python backtesting/token_universe_scanner.py --get-symbols 2025-10-13
        """
    )

    parser.add_argument('--scan-today', action='store_true',
                       help='Scan and save token universe for today')
    parser.add_argument('--start', type=str,
                       help='Start date for historical scan (YYYY-MM-DD)')
    parser.add_argument('--end', type=str,
                       help='End date for historical scan (YYYY-MM-DD)')
    parser.add_argument('--list', action='store_true',
                       help='List all available snapshot dates')
    parser.add_argument('--summary', action='store_true',
                       help='Show summary of available snapshots')
    parser.add_argument('--get-symbols', type=str,
                       help='Get symbols for a specific date (YYYY-MM-DD)')
    parser.add_argument('--output-dir', type=str,
                       default='backtesting/token_universe',
                       help='Output directory (default: backtesting/token_universe)')
    parser.add_argument('--daily', action='store_true',
                       help='Generate daily snapshots instead of Monday/Thursday only')

    args = parser.parse_args()

    scanner = TokenUniverseScanner(output_dir=Path(args.output_dir))

    if args.scan_today:
        print(f"\n{'='*60}")
        print(f"Scanning Today's Token Universe")
        print(f"{'='*60}\n")
        result = scanner.scan_today()
        if result:
            print(f"\n✅ Snapshot saved successfully")
        else:
            print(f"\n❌ Scan failed or not a scan day")

    elif args.start and args.end:
        start = datetime.strptime(args.start, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        end = datetime.strptime(args.end, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        scanner.generate_historical_snapshots(start, end, daily=args.daily)

    elif args.list:
        dates = scanner.list_available_snapshots()
        print(f"\n📅 Available Snapshots ({len(dates)} total):\n")
        for date in dates:
            snapshot = scanner.load_snapshot(date)
            if snapshot:
                print(f"   {date} - {snapshot['total_symbols']} symbols")

    elif args.summary:
        summary = scanner.get_summary()
        print(f"\n📊 Token Universe Summary\n")
        print(f"{'='*60}")
        print(f"Total Snapshots: {summary['total_snapshots']}")
        if summary['date_range']:
            print(f"Date Range: {summary['date_range']}")
            print(f"First Snapshot: {summary['first_snapshot']['date']} ({summary['first_snapshot']['symbols']} symbols)")
            print(f"Last Snapshot: {summary['last_snapshot']['date']} ({summary['last_snapshot']['symbols']} symbols)")
        print(f"{'='*60}\n")

    elif args.get_symbols:
        target = datetime.strptime(args.get_symbols, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        symbols = scanner.get_symbols_for_date(target)
        print(f"\n📊 Symbols for {args.get_symbols}:\n")
        print(f"Total: {len(symbols)}")
        print(f"Symbols: {', '.join(symbols[:20])}")
        if len(symbols) > 20:
            print(f"... and {len(symbols) - 20} more")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
