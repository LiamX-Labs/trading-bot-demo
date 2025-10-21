#!/usr/bin/env python3
"""
Configuration Loader for Backtesting V2
Loads and validates YAML configuration files
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class BacktestConfig:
    """Backtest configuration dataclass"""
    # Period
    start_date: str
    end_date: str
    timezone: str

    # Capital
    initial_balance: float
    base_position_size: float
    max_active_trades: int

    # Universe
    min_volume_24h: float
    universe_type: str
    dynamic_universe: bool
    universe_snapshots_dir: str

    # Data
    timeframe: str
    data_dir: str
    min_data_bars: int

    # Execution
    commission_rate: float

    # Pyramiding
    pyramiding_enabled: bool

    # Cooldown
    symbol_cooldown_enabled: bool
    symbol_cooldown_hours: int

    # Output
    results_dir: str
    signals_dir: str
    reports_dir: str
    generate_pdf: bool

    # Raw config for access to all fields
    raw: Dict[str, Any]


@dataclass
class StrategyConfig:
    """Strategy configuration dataclass"""
    # Pump detection
    pump_enabled: bool
    pump_lookback: int
    pump_threshold: float

    # Indicators
    rsi_period: int
    volatility_period: int
    volume_change_period: int
    price_change_period: int

    # Rule 6
    rule_6_enabled: bool
    rule_6_rsi_threshold: float
    rule_6_volatility_threshold: float

    # Rule 8
    rule_8_enabled: bool
    rule_8_min_score: int
    rule_8_max_spread: float
    rule_8_rsi_threshold: int
    rule_8_volume_threshold: float
    rule_8_spread_threshold: float
    rule_8_volatility_threshold: float
    rule_8_price_threshold: float

    # Exits
    stop_loss_pct: float
    take_profit_pct: float
    breakeven_enabled: bool
    breakeven_trigger_pct: float
    breakeven_buffer_pct: float
    negative_pnl_exit_hours: int
    max_age_exit_hours: int

    # Raw config
    raw: Dict[str, Any]


@dataclass
class RiskConfig:
    """Risk management configuration dataclass"""
    max_active_trades: int
    position_size: float
    stop_loss_pct: float
    take_profit_pct: float
    commission_rate: float

    # Cooldown
    symbol_cooldown_hours: int

    # Raw config
    raw: Dict[str, Any]


class ConfigLoader:
    """Loads and validates configuration files"""

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize config loader

        Args:
            config_dir: Path to config directory. If None, uses default.
        """
        if config_dir is None:
            # Default to config directory in v2
            self.config_dir = Path(__file__).parent.parent / "config"
        else:
            self.config_dir = Path(config_dir)

        if not self.config_dir.exists():
            raise ValueError(f"Config directory not found: {self.config_dir}")

    def load_yaml(self, filename: str) -> Dict[str, Any]:
        """Load a YAML file"""
        filepath = self.config_dir / filename

        if not filepath.exists():
            raise FileNotFoundError(f"Config file not found: {filepath}")

        with open(filepath, 'r') as f:
            config = yaml.safe_load(f)

        return config

    def load_backtest_config(self) -> BacktestConfig:
        """Load backtest configuration"""
        raw = self.load_yaml("backtest_config.yaml")

        return BacktestConfig(
            # Period
            start_date=raw['period']['start_date'],
            end_date=raw['period']['end_date'],
            timezone=raw['period']['timezone'],

            # Capital
            initial_balance=raw['capital']['initial_balance'],
            base_position_size=raw['capital']['base_position_size'],
            max_active_trades=raw['capital']['max_active_trades'],

            # Universe
            min_volume_24h=raw['universe']['min_volume_24h'],
            universe_type=raw['universe']['universe_type'],
            dynamic_universe=raw['universe']['universe_type'] == 'dynamic',
            universe_snapshots_dir=raw['universe']['dynamic']['universe_snapshots_dir'],

            # Data
            timeframe=raw['data']['timeframe'],
            data_dir=raw['data']['data_dir'],
            min_data_bars=raw['data']['min_data_bars'],

            # Execution
            commission_rate=raw['execution']['commission_rate'],

            # Pyramiding
            pyramiding_enabled=raw['pyramiding']['enabled'],

            # Cooldown
            symbol_cooldown_enabled=raw['cooldown']['symbol_cooldown_enabled'],
            symbol_cooldown_hours=raw['cooldown']['symbol_cooldown_hours'],

            # Output
            results_dir=raw['output']['results_dir'],
            signals_dir=raw['output']['signals_dir'],
            reports_dir=raw['output']['reports_dir'],
            generate_pdf=raw['output']['generate_pdf'],

            # Raw
            raw=raw
        )

    def load_strategy_config(self) -> StrategyConfig:
        """Load strategy configuration"""
        raw = self.load_yaml("strategy_config.yaml")

        return StrategyConfig(
            # Pump detection
            pump_enabled=raw['entry']['pump_detection']['enabled'],
            pump_lookback=raw['entry']['pump_detection']['lookback_periods'],
            pump_threshold=raw['entry']['pump_detection']['threshold_pct'],

            # Indicators
            rsi_period=raw['indicators']['rsi']['period'],
            volatility_period=raw['indicators']['volatility']['period'],
            volume_change_period=raw['indicators']['volume_change']['period'],
            price_change_period=raw['indicators']['price_change']['period'],

            # Rule 6
            rule_6_enabled=raw['rule_6']['enabled'],
            rule_6_rsi_threshold=raw['rule_6']['conditions']['rsi_threshold'],
            rule_6_volatility_threshold=raw['rule_6']['conditions']['volatility_threshold'],

            # Rule 8
            rule_8_enabled=raw['rule_8']['enabled'],
            rule_8_min_score=raw['rule_8']['conditions']['min_score'],
            rule_8_max_spread=raw['rule_8']['conditions']['max_spread'],
            rule_8_rsi_threshold=raw['rule_8']['score_components']['rsi_strength']['threshold'],
            rule_8_volume_threshold=raw['rule_8']['score_components']['volume_surge']['threshold'],
            rule_8_spread_threshold=raw['rule_8']['score_components']['tight_spread']['threshold'],
            rule_8_volatility_threshold=raw['rule_8']['score_components']['volatility_present']['threshold'],
            rule_8_price_threshold=raw['rule_8']['score_components']['price_momentum']['threshold'],

            # Exits
            stop_loss_pct=raw['exits']['stop_loss']['percentage'],
            take_profit_pct=raw['exits']['take_profit']['percentage'],
            breakeven_enabled=raw['exits']['stop_loss']['breakeven']['enabled'],
            breakeven_trigger_pct=raw['exits']['stop_loss']['breakeven']['trigger_pct'],
            breakeven_buffer_pct=raw['exits']['stop_loss']['breakeven']['buffer_pct'],
            negative_pnl_exit_hours=raw['exits']['time_based']['negative_pnl_exit']['hours'],
            max_age_exit_hours=raw['exits']['time_based']['max_age_exit']['hours'],

            # Raw
            raw=raw
        )

    def load_risk_config(self) -> RiskConfig:
        """Load risk management configuration"""
        raw = self.load_yaml("risk_config.yaml")

        # Get position size from risk config or default to 200
        try:
            position_size = raw['risk']['position_sizing']['fixed_size_usd']
        except KeyError:
            position_size = 200.0  # Default

        return RiskConfig(
            max_active_trades=raw['position_limits']['max_active_trades'],
            position_size=position_size,
            stop_loss_pct=raw['stop_loss_management']['percentage'],
            take_profit_pct=raw['take_profit_management']['percentage'],
            commission_rate=raw['costs']['commission']['rate'] / 100.0,  # Convert to decimal
            symbol_cooldown_hours=raw['time_based_controls']['negative_pnl_timeout']['hours'],
            raw=raw
        )

    def load_all_configs(self) -> tuple[BacktestConfig, StrategyConfig, RiskConfig]:
        """Load all configuration files"""
        backtest = self.load_backtest_config()
        strategy = self.load_strategy_config()
        risk = self.load_risk_config()

        return backtest, strategy, risk

    def validate_config(self, config: BacktestConfig) -> bool:
        """
        Validate backtest configuration

        Returns:
            True if valid, raises ValueError if invalid
        """
        # Validate dates
        try:
            start = datetime.strptime(config.start_date, '%Y-%m-%d')
            end = datetime.strptime(config.end_date, '%Y-%m-%d')
            if start >= end:
                raise ValueError(f"Start date must be before end date")
        except ValueError as e:
            raise ValueError(f"Invalid date format: {e}")

        # Validate capital
        if config.initial_balance <= 0:
            raise ValueError("Initial balance must be positive")

        if config.base_position_size <= 0:
            raise ValueError("Position size must be positive")

        if config.base_position_size > config.initial_balance:
            raise ValueError("Position size cannot exceed initial balance")

        # Validate max trades
        if config.max_active_trades <= 0:
            raise ValueError("Max active trades must be positive")

        # Validate universe
        if config.universe_type not in ['static', 'dynamic']:
            raise ValueError(f"Invalid universe type: {config.universe_type}")

        # Validate commission
        if config.commission_rate < 0 or config.commission_rate > 1:
            raise ValueError("Commission rate must be between 0 and 1")

        return True


def load_configs(config_dir: Optional[Path] = None) -> tuple[BacktestConfig, StrategyConfig, RiskConfig]:
    """
    Convenience function to load all configs

    Args:
        config_dir: Path to config directory

    Returns:
        Tuple of (backtest_config, strategy_config, risk_config)
    """
    loader = ConfigLoader(config_dir)
    backtest, strategy, risk = loader.load_all_configs()

    # Validate
    loader.validate_config(backtest)

    return backtest, strategy, risk


if __name__ == "__main__":
    # Test loading configs
    print("Testing config loader...")

    try:
        backtest, strategy, risk = load_configs()

        print("\n✅ Backtest Config Loaded:")
        print(f"   Period: {backtest.start_date} to {backtest.end_date}")
        print(f"   Capital: ${backtest.initial_balance:,.0f}")
        print(f"   Position Size: ${backtest.base_position_size:,.0f}")
        print(f"   Max Trades: {backtest.max_active_trades}")
        print(f"   Universe: {backtest.universe_type}")

        print("\n✅ Strategy Config Loaded:")
        print(f"   Pump Threshold: {strategy.pump_threshold}%")
        print(f"   Rule 6: {'Enabled' if strategy.rule_6_enabled else 'Disabled'}")
        print(f"   Rule 8: {'Enabled' if strategy.rule_8_enabled else 'Disabled'}")
        print(f"   Stop Loss: {strategy.stop_loss_pct}%")
        print(f"   Take Profit: {strategy.take_profit_pct}%")

        print("\n✅ Risk Config Loaded:")
        print(f"   Max Active Trades: {risk.max_active_trades}")
        print(f"   Commission: {risk.commission_rate}%")

        print("\n✅ All configs loaded successfully!")

    except Exception as e:
        print(f"\n❌ Error loading configs: {e}")
        raise
