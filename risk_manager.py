# risk_manager.py - AWS EC2 Free Tier Optimized Version

import asyncio
import time
from datetime import datetime, time as dtime, timezone, timedelta

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
    def __init__(self, active_trades: dict, enable_snapshot: bool = True):
        """
        active_trades: dict mapping (symbol, rule_id) -> metadata
        enable_snapshot: whether to schedule the midnight balance snapshot
        """
        self.active_trades = active_trades

        # Unrealized PnL drawdown state
        self.armed_unrealized = False
        self.peak_unrealized = 0.0
        self.activation_level = 2 * settings.BASE_POSITION_SIZE_USD

        # Daily balance drawdown state
        self.daily_balance_ref = None
        if enable_snapshot:
            self._schedule_midnight_snapshot()
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

    async def _snapshot_balance(self):
        try:
            self.daily_balance_ref = self.get_account_balance()
            send_telegram_message(f"📸 Daily balance: {self.daily_balance_ref:.2f} USDT")
        except Exception as e:
            logger.error(f"Failed to snapshot balance: {e}")
        finally:
            self._schedule_midnight_snapshot()

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
                close_all_positions(self.active_trades)
                self.armed_unrealized = False
                self.peak_unrealized = 0.0

    async def check_daily_balance_drawdown(self):
        """
        Check daily drawdown against midnight snapshot: liquidate at 25% drop.
        """
        if self.daily_balance_ref is None:
            return

        current = self.get_account_balance()
        drop = (self.daily_balance_ref - current) / self.daily_balance_ref
        if drop >= 0.25:
            send_telegram_message(
                f"⚠️ Daily balance drop ≥25% ({drop*100:.1f}%) — liquidating all positions."
            )
            close_all_positions(self.active_trades)

    async def check_break_even(self):
        """
        OPTIMIZED: Minimal logging version for AWS free tier
        """
        if not self.active_trades:
            return
        
        # REMOVED: All debug prints except essential ones
        
        for (symbol, rule_id) in list(self.active_trades.keys()):
            try:
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
                    continue
                
                lst = resp_data.get("result", {}).get("list", [])
                if not lst:
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

                if size == 0 or entry_price <= 0:
                    continue

                # Calculate profit percentage
                unreal_pct = ((mark_price - entry_price) / entry_price) * 100
                if side == "Sell":
                    unreal_pct = -unreal_pct

                BREAKEVEN_THRESHOLD = settings.BREAKEVEN_THRESHOLD

                if unreal_pct >= BREAKEVEN_THRESHOLD:
                    # Only print when actually triggering
                    print(f"🚀 Moving {symbol} to breakeven")
                    
                    # Check if SL already at breakeven
                    if abs(current_sl - entry_price) < 0.00001:
                        self.active_trades.pop((symbol, rule_id), None)
                        continue
                    
                    from order_manager import move_sl_to_breakeven
                    result = move_sl_to_breakeven(symbol)
                    
                    # Remove from tracking after successful update
                    if result.get("retCode") == 0:
                        self.active_trades.pop((symbol, rule_id), None)
                    
            except Exception as e:
                logger.error(f"Error checking {symbol}: {e}")