#!/usr/bin/env python3
"""
Generate reports from existing trades CSV
"""
import sys
from pathlib import Path
import pandas as pd

# Add v2 directory to path
v2_dir = Path(__file__).parent.parent
sys.path.insert(0, str(v2_dir))

from analytics.reports import ReportGenerator

# Load trades
trades_file = v2_dir / "results" / "trades_20251018_043213.csv"
trades_df = pd.read_csv(trades_file)

print(f"Loaded {len(trades_df)} trades from {trades_file.name}")

# Configuration
initial_balance = 5000
report_config = {
    'start_date': '2025-09-05',
    'end_date': '2025-10-17',
    'initial_balance': 5000,
    'position_size': 200,
    'max_active_trades': 30,
    'commission_rate': 0.00055,
    'universe_type': 'dynamic',
    'pump_threshold': 8.0,
    'stop_loss_pct': 8.0,
    'take_profit_pct': 30.0,
}

# Generate reports
output_dir = v2_dir / "reports"
output_dir.mkdir(parents=True, exist_ok=True)

report_gen = ReportGenerator(output_dir)
outputs = report_gen.generate_complete_report(
    trades_df=trades_df,
    initial_balance=initial_balance,
    config=report_config
)

print(f"\n📁 All outputs saved to: {output_dir}")
print(f"   Files generated:")
for name, path in outputs.items():
    if path:
        print(f"   - {name}: {path.name}")

print("\n✅ Report generation complete!")
