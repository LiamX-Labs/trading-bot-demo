# risk_manager.py - AWS EC2 Free Tier Optimized Version

import asyncio
import time
from datetime import datetime, time as dtime, timezone, timedelta
from typing import Tuple

import requests
import json

import settings
from order_manager import fetch_server_timestamp, generate_signature, close_all_positions
from telegram_alerts import send_telegram_message

import logging

# ─── Logger Configuration ─────────────────────────────────────────────────────
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)  # only warnings and above

# ─── Utility: retry wrapper for HTTP/API calls ─────────────────────────────────
def retry_request(fn, retries: int = 3, delay: float = 1.0):
    """
    Retry `fn()` up to `retries` times with `delay` seconds between attempts.
    """
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except Exception as e:
            logger.warning(f"Retry {attempt}/{retries} failed: {e}")
            if attempt == retries:
                logger.error("All retries failed.")
                raise
            time.sleep(delay)

def safe_float(value, default=0.0):
    """Safely convert value to float, handling empty strings and None"""
    if value is None or value == '':
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

# ─── RiskManager Class ────────────────────────────────────────────────────────
class RiskManager:
    def __init__(self, active_trades_getter, enable_snapshot: bool = True, trading_engine=None):
        """
        active_trades_getter: function that returns current active_trades dict
        enable_snapshot: whether to schedule the midnight balance snapshot
        trading_engine: reference to trading engine for breakeven management
        """
        self._get_active_trades = active_trades_getter
        self.trading_engine = trading_engine

        # Unrealized PnL drawdown state (legacy)
        self.armed_unrealized = False
        self.peak_unrealized = 0.0
        self.activation_level = 2 * settings.BASE_POSITION_SIZE_USD

        # Daily balance drawdown state (legacy)
        self.daily_balance_ref = None

        # ─── EQUITY-BASED DRAWDOWN SYSTEM ─────────────────────────────────────────
        # Daily equity tracking
        self.daily_equity_start = None
        self.daily_circuit_breaker_active = False
        self.daily_circuit_breaker_end_time = None

        # Weekly equity tracking
        self.weekly_equity_start = None
        self.weekly_equity_peak = None
        self.weekly_drawdown_level = 0  # 0=normal, 1=4% (reduced size), 2=6% (halted)
        self.weekly_halt_end_time = None
        self.position_size_multiplier = 1.0  # 1.0=full size, 0.5=half size
        self.weekly_max_drawdown = 0.0  # Track peak drawdown amount for recovery calculation

        # Initialize equity snapshots
        if enable_snapshot:
            self._schedule_midnight_snapshot()
            self._schedule_performance_analysis()

        # Check if we need to arm unrealized monitoring on startup
        self._check_initial_unrealized_state()
    
    def _check_initial_unrealized_state(self):
        """
        On startup, check if unrealized PnL is already above activation level
        """
        try:
            current_unrealized = self.compute_unrealized()
            if current_unrealized >= self.activation_level:
                self.armed_unrealized = True
                self.peak_unrealized = current_unrealized
                print(f"⚡ Unrealized monitoring armed on startup (PnL: ${current_unrealized:.2f})")
        except Exception as e:
            print(f"⚠️ Could not check initial unrealized state: {e}")

    def _schedule_midnight_snapshot(self):
        now = datetime.now(timezone.utc)
        next_mid = datetime.combine(now.date() + timedelta(days=1), dtime(0, 0), tzinfo=timezone.utc)
        delay = (next_mid - now).total_seconds()
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.call_later(delay, lambda: asyncio.create_task(self._snapshot_balance()))

    def _schedule_performance_analysis(self):
        """Schedule automated performance analysis tasks"""
        now = datetime.now(timezone.utc)

        # Schedule daily analysis (00:01 UTC)
        next_day = datetime.combine(now.date() + timedelta(days=1), dtime(0, 1), tzinfo=timezone.utc)
        delay_daily = (next_day - now).total_seconds()

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.call_later(delay_daily, lambda: asyncio.create_task(self._run_daily_performance_analysis()))

    async def _snapshot_balance(self):
        """Take daily equity snapshot and reset circuit breakers"""
        try:
            current_equity = self.get_current_equity()
            self.daily_balance_ref = self.get_account_balance()

            # Set daily equity start
            self.daily_equity_start = current_equity

            # Set weekly equity start if Monday
            now = datetime.now(timezone.utc)
            if now.weekday() == 0:  # Monday
                self.weekly_equity_start = current_equity
                self.weekly_equity_peak = current_equity
                self.weekly_drawdown_level = 0
                self.position_size_multiplier = 1.0
                send_telegram_message(f"📅 Weekly equity reset: ${current_equity:.2f}")

            # Reset daily circuit breaker
            self.daily_circuit_breaker_active = False
            self.daily_circuit_breaker_end_time = None

            send_telegram_message(f"📸 Daily equity snapshot: ${current_equity:.2f}")

        except Exception as e:
            logger.error(f"Failed to snapshot balance: {e}")
        finally:
            self._schedule_midnight_snapshot()
            self._schedule_performance_analysis()

    async def _run_daily_performance_analysis(self):
        """Run daily performance analysis at 00:01 UTC"""
        try:
            from performance_analysis.analyze_performance import BybitAPIClient, PerformanceAnalyzer, ReportGenerator
            import pandas as pd

            now = datetime.now(timezone.utc)
            yesterday = now - timedelta(days=1)

            start_ms = int(yesterday.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
            end_ms = int(yesterday.replace(hour=23, minute=59, second=59, microsecond=0).timestamp() * 1000)

            # Fetch trades
            api_client = BybitAPIClient()
            closed_pnl = api_client.get_position_closed_pnl(start_time=start_ms, end_time=end_ms, limit=50)

            if len(closed_pnl) > 0:
                trades_df = pd.DataFrame(closed_pnl)
                # Convert numeric fields to avoid type errors
                trades_df['closedPnl'] = pd.to_numeric(trades_df['closedPnl'])
                trades_df['createdTime'] = pd.to_numeric(trades_df['createdTime'])
                trades_df['updatedTime'] = pd.to_numeric(trades_df['updatedTime'])
                trades_df = trades_df.rename(columns={'avgEntryPrice': 'entryPrice', 'avgExitPrice': 'exitPrice'})

                analyzer = PerformanceAnalyzer(trades_df, initial_balance=10000)
                metrics = analyzer.calculate_metrics()

                report_gen = ReportGenerator(metrics, "Yesterday")
                summary = report_gen.generate_text_summary()

                try:
                    send_telegram_message(f"📊 Daily Performance Analysis\n{summary}")
                except Exception as tg_error:
                    logger.warning(f"Telegram notification failed: {tg_error}")
            else:
                try:
                    send_telegram_message(f"📊 Daily Performance: No trades closed yesterday")
                except Exception as tg_error:
                    logger.warning(f"Telegram notification failed: {tg_error}")

            # Check if it's Monday for weekly analysis
            if now.weekday() == 0:
                await self._run_weekly_performance_analysis()

            # Check if it's 1st of month for monthly analysis
            if now.day == 1:
                await self._run_monthly_performance_analysis()

        except Exception as e:
            logger.error(f"Failed to run daily performance analysis: {e}")
            send_telegram_message(f"⚠️ Daily performance analysis failed: {e}")

    async def _run_weekly_performance_analysis(self):
        """Run weekly performance analysis every Monday"""
        try:
            from performance_analysis.analyze_performance import BybitAPIClient, PerformanceAnalyzer, ReportGenerator
            import pandas as pd

            now = datetime.now(timezone.utc)
            week_ago = now - timedelta(days=7)

            start_ms = int(week_ago.timestamp() * 1000)
            end_ms = int(now.timestamp() * 1000)

            api_client = BybitAPIClient()
            closed_pnl = api_client.get_position_closed_pnl(start_time=start_ms, end_time=end_ms, limit=100)

            if len(closed_pnl) > 0:
                trades_df = pd.DataFrame(closed_pnl)
                # Convert numeric fields to avoid type errors
                trades_df['closedPnl'] = pd.to_numeric(trades_df['closedPnl'])
                trades_df['createdTime'] = pd.to_numeric(trades_df['createdTime'])
                trades_df['updatedTime'] = pd.to_numeric(trades_df['updatedTime'])
                trades_df = trades_df.rename(columns={'avgEntryPrice': 'entryPrice', 'avgExitPrice': 'exitPrice'})

                analyzer = PerformanceAnalyzer(trades_df, initial_balance=10000)
                metrics = analyzer.calculate_metrics()

                report_gen = ReportGenerator(metrics, "Last Week")
                summary = report_gen.generate_text_summary()

                try:
                    send_telegram_message(f"📊 Weekly Performance Analysis\n{summary}")
                except Exception as tg_error:
                    logger.warning(f"Telegram notification failed: {tg_error}")
            else:
                try:
                    send_telegram_message(f"📊 Weekly Performance: No trades closed last week")
                except Exception as tg_error:
                    logger.warning(f"Telegram notification failed: {tg_error}")

        except Exception as e:
            logger.error(f"Failed to run weekly performance analysis: {e}")

    async def _run_monthly_performance_analysis(self):
        """Run monthly performance analysis on 1st of month"""
        try:
            from performance_analysis.analyze_performance import BybitAPIClient, PerformanceAnalyzer, ReportGenerator
            import pandas as pd

            now = datetime.now(timezone.utc)
            month_ago = now - timedelta(days=30)

            start_ms = int(month_ago.timestamp() * 1000)
            end_ms = int(now.timestamp() * 1000)

            api_client = BybitAPIClient()
            closed_pnl = api_client.get_position_closed_pnl(start_time=start_ms, end_time=end_ms, limit=200)

            if len(closed_pnl) > 0:
                trades_df = pd.DataFrame(closed_pnl)
                # Convert numeric fields to avoid type errors
                trades_df['closedPnl'] = pd.to_numeric(trades_df['closedPnl'])
                trades_df['createdTime'] = pd.to_numeric(trades_df['createdTime'])
                trades_df['updatedTime'] = pd.to_numeric(trades_df['updatedTime'])
                trades_df = trades_df.rename(columns={'avgEntryPrice': 'entryPrice', 'avgExitPrice': 'exitPrice'})

                analyzer = PerformanceAnalyzer(trades_df, initial_balance=10000)
                metrics = analyzer.calculate_metrics()

                report_gen = ReportGenerator(metrics, "Last Month")
                summary = report_gen.generate_text_summary()

                try:
                    send_telegram_message(f"📊 Monthly Performance Analysis\n{summary}")
                except Exception as tg_error:
                    logger.warning(f"Telegram notification failed: {tg_error}")
            else:
                try:
                    send_telegram_message(f"📊 Monthly Performance: No trades closed last month")
                except Exception as tg_error:
                    logger.warning(f"Telegram notification failed: {tg_error}")

        except Exception as e:
            logger.error(f"Failed to run monthly performance analysis: {e}")

    def get_account_balance(self) -> float:
        """
        Fetch the USDT wallet balance via Bybit V5 wallet-balance endpoint,
        with retry logic to survive transient failures.
        """
        def _fetch():
            ts = fetch_server_timestamp()
            params = {"coin": "USDT", "accountType": "UNIFIED"}
            sig = generate_signature(ts, settings.RECV_WINDOW, params)
            headers = {
                'X-BAPI-API-KEY':     settings.API_KEY,
                'X-BAPI-SIGN':        sig,
                'X-BAPI-TIMESTAMP':   ts,
                'X-BAPI-RECV-WINDOW': settings.RECV_WINDOW
            }
            resp = requests.get(
                f"{settings.BASE_URL}/v5/account/wallet-balance",
                headers=headers,
                params=params
            ).json()
            if resp.get("retCode") != 0:
                raise RuntimeError(f"Bybit error: {resp.get('retMsg')}")
            for acct in resp["result"].get("list", []):
                for c in acct.get("coin", []):
                    if c.get("coin") == "USDT":
                        return float(c.get("walletBalance", 0))
            raise RuntimeError("USDT not found in wallet-balance response")
        return retry_request(_fetch)

    def compute_unrealized(self) -> float:
        """
        Fetch aggregated unrealized PnL from wallet-balance and return as float.
        """
        def _fetch_pnl():
            ts = fetch_server_timestamp()
            params = {"coin": "USDT", "accountType": "UNIFIED"}
            sig = generate_signature(ts, settings.RECV_WINDOW, params)
            headers = {
                'X-BAPI-API-KEY':     settings.API_KEY,
                'X-BAPI-SIGN':        sig,
                'X-BAPI-TIMESTAMP':   ts,
                'X-BAPI-RECV-WINDOW': settings.RECV_WINDOW
            }
            resp = requests.get(
                f"{settings.BASE_URL}/v5/account/wallet-balance",
                headers=headers,
                params=params
            ).json()
            if resp.get("retCode") != 0:
                raise RuntimeError(f"Bybit error: {resp.get('retMsg')}")
            for acct in resp["result"].get("list", []):
                for c in acct.get("coin", []):
                    if c.get("coin") == "USDT":
                        return safe_float(c.get("unrealisedPnl", 0))
            return 0.0
        return retry_request(_fetch_pnl)

    def get_current_equity(self) -> float:
        """
        Get current account equity (balance + unrealized PnL)
        """
        def _fetch_equity():
            ts = fetch_server_timestamp()
            params = {"coin": "USDT", "accountType": "UNIFIED"}
            sig = generate_signature(ts, settings.RECV_WINDOW, params)
            headers = {
                'X-BAPI-API-KEY':     settings.API_KEY,
                'X-BAPI-SIGN':        sig,
                'X-BAPI-TIMESTAMP':   ts,
                'X-BAPI-RECV-WINDOW': settings.RECV_WINDOW
            }
            resp = requests.get(
                f"{settings.BASE_URL}/v5/account/wallet-balance",
                headers=headers,
                params=params
            ).json()
            if resp.get("retCode") != 0:
                raise RuntimeError(f"Bybit error: {resp.get('retMsg')}")
            for acct in resp["result"].get("list", []):
                # Get totalEquity which includes unrealized PnL
                total_equity = safe_float(acct.get("totalEquity", 0))
                if total_equity > 0:
                    return total_equity
                # Fallback: calculate manually
                for c in acct.get("coin", []):
                    if c.get("coin") == "USDT":
                        balance = safe_float(c.get("walletBalance", 0))
                        unrealized = safe_float(c.get("unrealisedPnl", 0))
                        return balance + unrealized
            raise RuntimeError("USDT equity not found in wallet-balance response")
        return retry_request(_fetch_equity)

    def get_position_size_multiplier(self) -> float:
        """
        Get current position size multiplier based on weekly drawdown state
        Returns: 1.0 for full size, 0.5 for half size, 0.0 for halted
        """
        # Check if daily circuit breaker is active
        if self.daily_circuit_breaker_active:
            return 0.0

        # Check if weekly halt is active
        if self.weekly_drawdown_level == 2:
            return 0.0

        # Return current multiplier (1.0 or 0.5)
        return self.position_size_multiplier

    def is_trading_allowed(self) -> Tuple[bool, str]:
        """
        Check if trading is currently allowed
        Returns: (allowed: bool, reason: str)
        """
        now = datetime.now(timezone.utc)

        # Check daily circuit breaker
        if self.daily_circuit_breaker_active:
            if self.daily_circuit_breaker_end_time and now < self.daily_circuit_breaker_end_time:
                remaining = self.daily_circuit_breaker_end_time - now
                hours = int(remaining.total_seconds() / 3600)
                minutes = int((remaining.total_seconds() % 3600) / 60)
                return False, f"⛔ Daily circuit breaker active. Trading resumes in {hours}h {minutes}m"
            else:
                # Circuit breaker expired
                self.daily_circuit_breaker_active = False
                self.daily_circuit_breaker_end_time = None

        # Check weekly halt
        if self.weekly_drawdown_level == 2:
            if self.weekly_halt_end_time and now < self.weekly_halt_end_time:
                remaining = self.weekly_halt_end_time - now
                days = remaining.days
                hours = int(remaining.seconds / 3600)
                return False, f"⛔ Weekly halt active. Trading resumes in {days}d {hours}h (Monday 00:01 UTC)"
            else:
                # Weekly halt expired
                self.weekly_drawdown_level = 0
                self.position_size_multiplier = 1.0
                self.weekly_halt_end_time = None

        return True, "✅ Trading allowed"

    async def check_unrealized_drawdown(self):
        """
        Check intraday drawdown: arm at 2× base size, track peak, liquidate at 30% drawdown.
        """
        total_unrealized = self.compute_unrealized()
        if total_unrealized <= 0:
            self.armed_unrealized = False
            self.peak_unrealized = 0.0
            return

        if not self.armed_unrealized and total_unrealized >= self.activation_level:
            self.armed_unrealized = True
            self.peak_unrealized = total_unrealized

        if self.armed_unrealized:
            if total_unrealized > self.peak_unrealized:
                self.peak_unrealized = total_unrealized
            drawdown = (self.peak_unrealized - total_unrealized) / self.peak_unrealized
            if drawdown >= 0.30:
                send_telegram_message(
                    f"⚠️ Unrealized drawdown ≥30% ({drawdown*100:.1f}%) — liquidating all positions."
                )
                close_all_positions(self._get_active_trades())
                self.armed_unrealized = False
                self.peak_unrealized = 0.0

    async def check_daily_balance_drawdown(self):
        """
        Check daily drawdown against midnight snapshot: liquidate at 25% drop (LEGACY).
        """
        if self.daily_balance_ref is None:
            return

        current = self.get_account_balance()
        drop = (self.daily_balance_ref - current) / self.daily_balance_ref
        if drop >= 0.25:
            send_telegram_message(
                f"⚠️ Daily balance drop ≥25% ({drop*100:.1f}%) — liquidating all positions."
            )
            close_all_positions(self._get_active_trades())

    async def check_equity_drawdowns(self):
        """
        Check equity-based drawdown triggers (daily and weekly)
        """
        try:
            current_equity = self.get_current_equity()
            now = datetime.now(timezone.utc)

            # Initialize snapshots if not set
            if self.daily_equity_start is None:
                self.daily_equity_start = current_equity
                print(f"📊 Initialized daily equity: ${current_equity:.2f}")

            if self.weekly_equity_start is None:
                self.weekly_equity_start = current_equity
                self.weekly_equity_peak = current_equity
                print(f"📊 Initialized weekly equity: ${current_equity:.2f}")

            # ─── DAILY EQUITY DRAWDOWN (2% Circuit Breaker) ───────────────────────
            daily_drawdown = (self.daily_equity_start - current_equity) / self.daily_equity_start

            if daily_drawdown >= settings.DAILY_EQUITY_DRAWDOWN_THRESHOLD:
                if not self.daily_circuit_breaker_active:
                    # Trigger circuit breaker
                    self.daily_circuit_breaker_active = True

                    # Calculate pause end time (next day 00:01 UTC)
                    tomorrow = datetime.combine(
                        now.date() + timedelta(days=1),
                        dtime(0, 1),
                        tzinfo=timezone.utc
                    )
                    self.daily_circuit_breaker_end_time = tomorrow

                    remaining = tomorrow - now
                    hours = int(remaining.total_seconds() / 3600)
                    minutes = int((remaining.total_seconds() % 3600) / 60)

                    # Close all positions
                    send_telegram_message(
                        f"🚨 DAILY CIRCUIT BREAKER ACTIVATED\n\n"
                        f"Daily equity drawdown: {daily_drawdown*100:.2f}%\n"
                        f"Start equity: ${self.daily_equity_start:.2f}\n"
                        f"Current equity: ${current_equity:.2f}\n\n"
                        f"⛔ All positions closed\n"
                        f"⛔ Trading paused until {tomorrow.strftime('%Y-%m-%d %H:%M UTC')}\n"
                        f"⏱️ Countdown: {hours}h {minutes}m remaining"
                    )
                    close_all_positions(self._get_active_trades())
                    print(f"🚨 Daily circuit breaker triggered at {daily_drawdown*100:.2f}% drawdown")

            # ─── WEEKLY EQUITY DRAWDOWN (Progressive Risk Management) ─────────────
            # Update weekly peak
            if current_equity > self.weekly_equity_peak:
                self.weekly_equity_peak = current_equity

            weekly_drawdown = (self.weekly_equity_start - current_equity) / self.weekly_equity_start

            # Level 2: 6% Weekly Drawdown (Halt Trading)
            if weekly_drawdown >= settings.WEEKLY_EQUITY_DRAWDOWN_THRESHOLD_LEVEL2:
                if self.weekly_drawdown_level < 2:
                    self.weekly_drawdown_level = 2
                    self.position_size_multiplier = 0.0

                    # Calculate halt end time (next Monday 00:01 UTC)
                    days_until_monday = (7 - now.weekday()) % 7
                    if days_until_monday == 0:
                        days_until_monday = 7
                    next_monday = datetime.combine(
                        now.date() + timedelta(days=days_until_monday),
                        dtime(0, 1),
                        tzinfo=timezone.utc
                    )
                    self.weekly_halt_end_time = next_monday

                    remaining = next_monday - now
                    days = remaining.days
                    hours = int(remaining.seconds / 3600)

                    send_telegram_message(
                        f"🚨 WEEKLY TRADING HALT ACTIVATED\n\n"
                        f"Weekly equity drawdown: {weekly_drawdown*100:.2f}%\n"
                        f"Weekly start: ${self.weekly_equity_start:.2f}\n"
                        f"Current equity: ${current_equity:.2f}\n\n"
                        f"⛔ All positions closed\n"
                        f"⛔ Trading halted until Monday {next_monday.strftime('%Y-%m-%d %H:%M UTC')}\n"
                        f"⏱️ Countdown: {days}d {hours}h remaining"
                    )
                    close_all_positions(self._get_active_trades())
                    print(f"🚨 Weekly halt triggered at {weekly_drawdown*100:.2f}% drawdown")

            # Level 1: 4% Weekly Drawdown (Reduce Position Size)
            elif weekly_drawdown >= settings.WEEKLY_EQUITY_DRAWDOWN_THRESHOLD_LEVEL1:
                if self.weekly_drawdown_level < 1:
                    self.weekly_drawdown_level = 1
                    self.position_size_multiplier = settings.WEEKLY_POSITION_SIZE_REDUCTION

                    # Store the peak drawdown amount for recovery calculation
                    self.weekly_max_drawdown = self.weekly_equity_start - current_equity

                    send_telegram_message(
                        f"⚠️ WEEKLY POSITION SIZE REDUCTION\n\n"
                        f"Weekly equity drawdown: {weekly_drawdown*100:.2f}%\n"
                        f"Weekly start: ${self.weekly_equity_start:.2f}\n"
                        f"Current equity: ${current_equity:.2f}\n"
                        f"Loss amount: ${self.weekly_max_drawdown:.2f}\n\n"
                        f"📉 Position size reduced to {self.position_size_multiplier*100:.0f}%\n"
                        f"🔄 Full size restores after 50% loss recovery (${self.weekly_equity_start - self.weekly_max_drawdown * 0.5:.2f})"
                    )
                    print(f"⚠️ Position size reduced at {weekly_drawdown*100:.2f}% drawdown")

                # Check for recovery (restore full position size)
                elif self.weekly_drawdown_level == 1:
                    # Update peak drawdown if we dropped further
                    current_loss = self.weekly_equity_start - current_equity
                    if current_loss > self.weekly_max_drawdown:
                        self.weekly_max_drawdown = current_loss

                    # Recovery target: recover 50% of the PEAK loss
                    recovery_target = self.weekly_equity_start - (self.weekly_max_drawdown * settings.WEEKLY_RECOVERY_THRESHOLD)

                    if current_equity >= recovery_target:
                        self.weekly_drawdown_level = 0
                        self.position_size_multiplier = 1.0

                        send_telegram_message(
                            f"✅ POSITION SIZE RESTORED\n\n"
                            f"Recovered 50%+ of weekly losses\n"
                            f"Peak loss: ${self.weekly_max_drawdown:.2f}\n"
                            f"Current equity: ${current_equity:.2f}\n"
                            f"Recovery: ${current_equity - (self.weekly_equity_start - self.weekly_max_drawdown):.2f}\n"
                            f"📈 Position size restored to 100%"
                        )
                        print(f"✅ Position size restored to 100%")

                        # Reset max drawdown tracker
                        self.weekly_max_drawdown = 0.0

        except Exception as e:
            logger.error(f"Error checking equity drawdowns: {e}")
            print(f"❌ Equity drawdown check failed: {e}")

    async def check_break_even(self):
        """
        DEBUGGING: Added debug logging to identify breakeven issues
        """
        active_trades = self._get_active_trades()
        if not active_trades:
            return
        
        print(f"🔍 [{datetime.now().strftime('%H:%M:%S')}] Checking breakeven for {len(active_trades)} trades...")
        
        for (symbol, rule_id) in list(active_trades.keys()):
            try:
                print(f"🔍 Checking {symbol} ({rule_id})...")
                
                ts = fetch_server_timestamp()
                params = {"category": "linear", "symbol": symbol}
                sig = generate_signature(ts, settings.RECV_WINDOW, params)
                headers = {
                    'X-BAPI-API-KEY':     settings.API_KEY,
                    'X-BAPI-SIGN':        sig,
                    'X-BAPI-TIMESTAMP':   ts,
                    'X-BAPI-RECV-WINDOW': settings.RECV_WINDOW
                }
                
                resp = requests.get(
                    f"{settings.BASE_URL}/v5/position/list",
                    headers=headers,
                    params=params
                )
                
                resp_data = resp.json()
                if resp_data.get("retCode") != 0:
                    print(f"❌ API error for {symbol}: {resp_data.get('retMsg')}")
                    continue
                
                lst = resp_data.get("result", {}).get("list", [])
                if not lst:
                    print(f"❌ No position data for {symbol}")
                    continue

                pos = lst[0]
                
                # Extract all relevant fields using safe_float
                size = abs(safe_float(pos.get("size", 0)))
                
                avg_price_str = pos.get("avgPrice", "0")
                entry_price_str = pos.get("entryPrice", "0")
                
                entry_price = safe_float(avg_price_str)
                if entry_price <= 0:
                    entry_price = safe_float(entry_price_str)
                
                mark_price = safe_float(pos.get("markPrice", 0))
                if mark_price <= 0:
                    mark_price = safe_float(pos.get("lastPrice", 0))
                
                side = pos.get("side")
                current_sl = safe_float(pos.get("stopLoss", 0))

                print(f"📊 {symbol} - Size: {size}, Entry: {entry_price}, Mark: {mark_price}, Side: {side}, Current SL: {current_sl}")

                if size == 0 or entry_price <= 0:
                    print(f"❌ Invalid position data for {symbol} - Size: {size}, Entry: {entry_price}")
                    # Remove from tracking since position is closed
                    print(f"🔄 Removing closed position {symbol} ({rule_id}) from active_trades")
                    active_trades.pop((symbol, rule_id), None)
                    continue

                # Calculate profit percentage
                unreal_pct = ((mark_price - entry_price) / entry_price) * 100
                if side in ["Sell", "Short"]:
                    unreal_pct = -unreal_pct

                BREAKEVEN_THRESHOLD = settings.BREAKEVEN_THRESHOLD
                
                print(f"📈 {symbol} - Profit: {unreal_pct:.2f}%, Threshold: {BREAKEVEN_THRESHOLD}%")

                if unreal_pct >= BREAKEVEN_THRESHOLD:
                    print(f"🚀 Moving {symbol} to breakeven (Profit: {unreal_pct:.2f}% >= {BREAKEVEN_THRESHOLD}%)")
                    
                    # Check if SL already at breakeven with more reasonable tolerance
                    tolerance = 0.001  # 0.1% tolerance to account for tick size rounding
                    if abs(current_sl - entry_price) < tolerance:
                        print(f"✅ {symbol} already at breakeven (SL: {current_sl}, Entry: {entry_price}), removing from tracking")
                        active_trades.pop((symbol, rule_id), None)
                        print(f"📝 [{datetime.now().strftime('%H:%M:%S')}] Removed {symbol} ({rule_id}) from active_trades (already at breakeven). Total: {len(active_trades)}")
                        continue
                    
                    from order_manager import move_sl_to_breakeven
                    result = move_sl_to_breakeven(symbol)
                    
                    print(f"🔧 Breakeven result for {symbol}: {result}")
                    
                    # Move to breakeven tracking instead of removing completely
                    if result.get("retCode") == 0:
                        print(f"✅ Successfully moved {symbol} to breakeven, moving to breakeven tracking")
                        # Use trading engine to properly move the trade if available
                        if self.trading_engine:
                            success = self.trading_engine.move_trade_to_breakeven(symbol, rule_id)
                            if success:
                                print(f"📝 [{datetime.now().strftime('%H:%M:%S')}] Moved {symbol} ({rule_id}) to breakeven tracking. Remaining active: {len(active_trades)}")
                            else:
                                # Fallback: remove from active_trades dict
                                active_trades.pop((symbol, rule_id), None)
                                print(f"📝 [{datetime.now().strftime('%H:%M:%S')}] Removed {symbol} ({rule_id}) from active_trades (fallback). Total: {len(active_trades)}")
                        else:
                            # Fallback: just remove from active_trades
                            active_trades.pop((symbol, rule_id), None)
                            print(f"📝 [{datetime.now().strftime('%H:%M:%S')}] Removed {symbol} ({rule_id}) from active_trades (no engine ref). Total: {len(active_trades)}")
                    elif result.get("retCode") == 34040:
                        # "not modified" means already at breakeven
                        print(f"✅ {symbol} already at breakeven (API confirmed), moving to breakeven tracking")
                        if self.trading_engine:
                            success = self.trading_engine.move_trade_to_breakeven(symbol, rule_id)
                            if success:
                                print(f"📝 [{datetime.now().strftime('%H:%M:%S')}] Moved {symbol} ({rule_id}) to breakeven tracking (already at BE). Remaining active: {len(active_trades)}")
                            else:
                                active_trades.pop((symbol, rule_id), None)
                                print(f"📝 [{datetime.now().strftime('%H:%M:%S')}] Removed {symbol} ({rule_id}) from active_trades (fallback). Total: {len(active_trades)}")
                        else:
                            active_trades.pop((symbol, rule_id), None)
                            print(f"📝 [{datetime.now().strftime('%H:%M:%S')}] Removed {symbol} ({rule_id}) from active_trades (no engine ref). Total: {len(active_trades)}")
                    else:
                        print(f"❌ Failed to move {symbol} to breakeven: {result.get('retMsg')}")
                else:
                    print(f"⏳ {symbol} not ready for breakeven yet ({unreal_pct:.2f}% < {BREAKEVEN_THRESHOLD}%)")
                    
            except Exception as e:
                logger.error(f"Error checking {symbol}: {e}")
                print(f"❌ Exception checking {symbol}: {e}")
        
        print(f"🔍 [{datetime.now().strftime('%H:%M:%S')}] Breakeven check completed")