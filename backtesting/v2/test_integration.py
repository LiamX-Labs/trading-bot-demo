#!/usr/bin/env python3
"""Test config integration with all modules"""

import sys
from pathlib import Path

# Add v2 directory to path
v2_dir = Path(__file__).parent
sys.path.insert(0, str(v2_dir))

from utils.config_loader import load_configs
from strategy.rules import TradingStrategy
from strategy.signal_generator import SignalGenerator
from execution.engine import PyramidBacktestEngine, Position
from data.universe_manager import TokenUniverseScanner

def test_config_integration():
    """Test that all modules work with config system"""

    print("=" * 70)
    print("🧪 TESTING CONFIG INTEGRATION")
    print("=" * 70 + "\n")

    # Load configs
    print("1️⃣ Loading configurations...")
    config_dir = v2_dir / "config"
    backtest_cfg, strategy_cfg, risk_cfg = load_configs(config_dir)
    print(f"   ✅ Loaded from: {config_dir}\n")

    # Test TradingStrategy with config
    print("2️⃣ Testing TradingStrategy with config...")
    strategy = TradingStrategy(config=strategy_cfg)
    print(f"   ✅ RSI Period: {strategy.rsi_period}")
    print(f"   ✅ Volatility Period: {strategy.volatility_period}")
    print(f"   ✅ Pump Threshold: {strategy.pump_threshold}%")
    print(f"   ✅ Pump Lookback: {strategy.pump_lookback} bars\n")

    # Test SignalGenerator with config
    print("3️⃣ Testing SignalGenerator with config...")
    from datetime import datetime
    start = datetime(2025, 9, 5)
    end = datetime(2025, 10, 17)
    signal_gen = SignalGenerator(
        start_date=start,
        end_date=end,
        use_dynamic_universe=True,
        backtest_config=backtest_cfg,
        strategy_config=strategy_cfg
    )
    print(f"   ✅ Signal generator initialized")
    print(f"   ✅ Strategy pump threshold: {signal_gen.strategy.pump_threshold}%\n")

    # Test PyramidBacktestEngine with config
    print("4️⃣ Testing PyramidBacktestEngine with config...")
    engine = PyramidBacktestEngine(
        initial_balance=backtest_cfg.initial_balance,
        position_size=backtest_cfg.base_position_size,
        max_active_trades=backtest_cfg.max_active_trades,
        commission_rate=backtest_cfg.commission_rate,
        backtest_config=backtest_cfg,
        strategy_config=strategy_cfg
    )
    print(f"   ✅ Engine initialized")
    print(f"   ✅ Initial Balance: ${engine.initial_balance:,.0f}")
    print(f"   ✅ Position Size: ${engine.position_size:,.0f}")
    print(f"   ✅ Max Trades: {engine.max_active_trades}")
    print(f"   ✅ Stop Loss: {engine.stop_loss_pct}%")
    print(f"   ✅ Take Profit: {engine.take_profit_pct}%")
    print(f"   ✅ Breakeven Trigger: {engine.breakeven_trigger_pct}%\n")

    # Test Position with config params
    print("5️⃣ Testing Position with config params...")
    position = Position(
        symbol="BTCUSDT",
        entry_time=1000000,
        entry_price=50000.0,
        quantity=0.004,
        rule="Rule 8",
        position_size_usd=200.0,
        stop_loss_pct=strategy_cfg.stop_loss_pct,
        take_profit_pct=strategy_cfg.take_profit_pct,
        breakeven_trigger_pct=strategy_cfg.breakeven_trigger_pct
    )
    print(f"   ✅ Position created")
    print(f"   ✅ Entry Price: ${position.avg_entry_price:,.2f}")
    print(f"   ✅ Stop Loss: ${position.stop_loss:,.2f} ({position.stop_loss_pct}%)")
    print(f"   ✅ Take Profit: ${position.take_profit:,.2f} ({position.take_profit_pct}%)\n")

    # Test TokenUniverseScanner with config
    print("6️⃣ Testing TokenUniverseScanner with config...")
    scanner = TokenUniverseScanner(config=backtest_cfg)
    print(f"   ✅ Scanner initialized")
    print(f"   ✅ Volume Filter: ${scanner.volume_filter_usd:,}\n")

    print("=" * 70)
    print("✅ ALL TESTS PASSED - Config integration working!")
    print("=" * 70)

if __name__ == "__main__":
    test_config_integration()
