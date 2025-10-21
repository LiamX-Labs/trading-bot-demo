#!/usr/bin/env python3
"""
Performance Analysis Script for Bybit Trading Strategy
Analyzes closed trades and generates MyFXBook-style performance reports with charts
"""

import os
import sys
import json
import hmac
import hashlib
import requests
import time
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import argparse

# Add parent directory to path for imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from dotenv import load_dotenv
load_dotenv(parent_dir / ".env")

# Import settings
import settings
from telegram_alerts import send_telegram_message


class BybitAPIClient:
    """Bybit API client for fetching trade history"""

    def __init__(self):
        self.api_key = settings.API_KEY
        self.api_secret = settings.API_SECRET
        self.base_url = settings.BASE_URL
        self.recv_window = settings.RECV_WINDOW
        self._time_offset_cache = None
        self._last_sync_time = 0
        self._sync_interval = 300  # 5 minutes

    def _get_server_time(self) -> str:
        """Get Bybit server time with caching"""
        current_time = time.time()

        # Use cached offset if available and recent
        if self._time_offset_cache is not None and (current_time - self._last_sync_time) < self._sync_interval:
            local_time = int(datetime.now(timezone.utc).timestamp() * 1000)
            return str(local_time + self._time_offset_cache)

        # Sync with server
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Try the public time endpoint
                resp = requests.get(f"{self.base_url}/v5/market/time", timeout=3)
                resp.raise_for_status()
                data = resp.json()

                # Handle different response formats
                if "result" in data and "timeSecond" in data["result"]:
                    server_time = int(data["result"]["timeSecond"]) * 1000
                elif "time" in data:
                    server_time = int(data["time"])
                else:
                    raise ValueError(f"Unexpected response format: {data}")

                local_time = int(datetime.now(timezone.utc).timestamp() * 1000)

                # Calculate and cache offset
                self._time_offset_cache = server_time - local_time
                self._last_sync_time = current_time

                return str(server_time)

            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(0.2)
                    continue

                # Fallback: use cached offset or local time
                print(f"⚠️ Failed to get server time after {max_retries} attempts: {e}")
                local_time = int(datetime.now(timezone.utc).timestamp() * 1000)
                if self._time_offset_cache is not None:
                    return str(local_time + self._time_offset_cache)
                return str(local_time)

    def _generate_signature(self, timestamp: str, params: dict) -> str:
        """Generate HMAC SHA256 signature for Bybit API"""
        # Build query string maintaining insertion order (dict order in Python 3.7+)
        # NOTE: Bybit expects the params as they will appear in the URL (URL-encoded)
        from urllib.parse import urlencode
        param_str = urlencode(params)
        sign_str = f"{timestamp}{self.api_key}{self.recv_window}{param_str}"

        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            sign_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return signature

    def get_position_closed_pnl(self, symbol: str = "", category: str = "linear",
                               start_time: Optional[int] = None,
                               end_time: Optional[int] = None,
                               limit: int = 50) -> List[Dict]:
        """
        Fetch closed P&L records from Bybit
        This gives us the actual realized P&L for closed positions

        Note: Bybit API limits time range to 7 days per request.
        For longer periods, this method automatically splits into multiple requests.
        """
        endpoint = "/v5/position/closed-pnl"
        all_pnl = []

        # If no time range specified, fetch recent data
        if not start_time or not end_time:
            return self._fetch_closed_pnl_chunk(endpoint, symbol, category, start_time, end_time, limit)

        # Calculate time range in milliseconds
        MAX_RANGE_MS = 7 * 24 * 60 * 60 * 1000  # 7 days in milliseconds
        time_range = end_time - start_time

        # If range is within 7 days, fetch directly
        if time_range <= MAX_RANGE_MS:
            return self._fetch_closed_pnl_chunk(endpoint, symbol, category, start_time, end_time, limit)

        # Split into 7-day chunks
        print(f"📅 Time range exceeds 7 days, splitting into chunks...")
        current_start = start_time
        chunk_count = 0

        while current_start < end_time:
            # Calculate chunk end time (7 days or until end_time)
            chunk_end = min(current_start + MAX_RANGE_MS, end_time)
            chunk_count += 1

            # Fetch this chunk
            chunk_start_date = datetime.fromtimestamp(current_start / 1000, tz=timezone.utc).strftime('%Y-%m-%d')
            chunk_end_date = datetime.fromtimestamp(chunk_end / 1000, tz=timezone.utc).strftime('%Y-%m-%d')
            print(f"   Chunk {chunk_count}: {chunk_start_date} to {chunk_end_date}")

            chunk_data = self._fetch_closed_pnl_chunk(endpoint, symbol, category, current_start, chunk_end, limit)
            all_pnl.extend(chunk_data)

            # Move to next chunk
            current_start = chunk_end + 1  # Add 1ms to avoid overlap

            # Small delay to avoid rate limiting
            if current_start < end_time:
                time.sleep(0.2)

        print(f"✅ Fetched total of {len(all_pnl)} records across {chunk_count} chunks")
        return all_pnl

    def _fetch_closed_pnl_chunk(self, endpoint: str, symbol: str, category: str,
                                start_time: Optional[int], end_time: Optional[int],
                                limit: int) -> List[Dict]:
        """
        Fetch a single chunk of closed P&L data (max 7 days)
        Handles pagination via cursor
        """
        chunk_pnl = []
        cursor = None

        while True:
            timestamp = self._get_server_time()

            # Build params in consistent order
            params = {
                "category": category,
                "limit": str(limit),
            }

            if symbol:
                params["symbol"] = symbol
            if start_time:
                params["startTime"] = str(start_time)
            if end_time:
                params["endTime"] = str(end_time)
            if cursor:
                params["cursor"] = cursor

            signature = self._generate_signature(timestamp, params)

            headers = {
                "X-BAPI-API-KEY": self.api_key,
                "X-BAPI-SIGN": signature,
                "X-BAPI-SIGN-TYPE": "2",
                "X-BAPI-TIMESTAMP": timestamp,
                "X-BAPI-RECV-WINDOW": self.recv_window,
            }

            try:
                response = requests.get(
                    f"{self.base_url}{endpoint}",
                    params=params,
                    headers=headers,
                    timeout=10
                )
                response.raise_for_status()
                data = response.json()

                if data["retCode"] != 0:
                    print(f"   ⚠️ API Error: {data['retMsg']}")
                    break

                result = data.get("result", {})
                pnl_records = result.get("list", [])
                chunk_pnl.extend(pnl_records)

                cursor = result.get("nextPageCursor", "")
                if not cursor or len(pnl_records) == 0:
                    break

                # Small delay between pagination requests
                time.sleep(0.1)

            except Exception as e:
                print(f"   ❌ Error fetching chunk: {e}")
                break

        return chunk_pnl


class PerformanceAnalyzer:
    """Analyzes trading performance with MyFXBook-style metrics"""

    def __init__(self, trades_df: pd.DataFrame, initial_balance: float = 10000):
        """
        Initialize analyzer with trades dataframe

        Args:
            trades_df: DataFrame with columns: symbol, entryPrice, exitPrice,
                      closedPnl, qty, side, createdTime, updatedTime
            initial_balance: Starting account balance
        """
        self.trades_df = trades_df
        self.initial_balance = initial_balance

    def calculate_metrics(self) -> Dict:
        """Calculate comprehensive performance metrics"""
        if len(self.trades_df) == 0:
            return self._empty_metrics()

        df = self.trades_df.copy()

        # Basic metrics
        total_trades = len(df)
        winning_trades = len(df[df['closedPnl'] > 0])
        losing_trades = len(df[df['closedPnl'] < 0])
        breakeven_trades = len(df[df['closedPnl'] == 0])

        # P&L metrics
        total_pnl = df['closedPnl'].sum()
        gross_profit = df[df['closedPnl'] > 0]['closedPnl'].sum()
        gross_loss = abs(df[df['closedPnl'] < 0]['closedPnl'].sum())

        # Win rate
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        # Average metrics
        avg_win = gross_profit / winning_trades if winning_trades > 0 else 0
        avg_loss = gross_loss / losing_trades if losing_trades > 0 else 0
        avg_trade = total_pnl / total_trades if total_trades > 0 else 0

        # Profit factor
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # Largest win/loss
        largest_win = df['closedPnl'].max() if total_trades > 0 else 0
        largest_loss = df['closedPnl'].min() if total_trades > 0 else 0

        # Calculate equity curve and drawdown
        df = df.sort_values('updatedTime')
        df['cumulative_pnl'] = df['closedPnl'].cumsum()
        df['equity'] = self.initial_balance + df['cumulative_pnl']

        # Drawdown calculation
        df['running_max'] = df['equity'].cummax()
        df['drawdown'] = df['equity'] - df['running_max']
        df['drawdown_pct'] = (df['drawdown'] / df['running_max'] * 100)

        max_drawdown = df['drawdown'].min()
        max_drawdown_pct = df['drawdown_pct'].min()

        # Current values
        current_equity = df['equity'].iloc[-1] if len(df) > 0 else self.initial_balance
        total_return = ((current_equity - self.initial_balance) / self.initial_balance * 100)

        # Consecutive wins/losses
        df['is_win'] = df['closedPnl'] > 0
        df['streak'] = df['is_win'].ne(df['is_win'].shift()).cumsum()
        win_streaks = df[df['is_win']].groupby('streak').size()
        loss_streaks = df[~df['is_win']].groupby('streak').size()

        max_consecutive_wins = win_streaks.max() if len(win_streaks) > 0 else 0
        max_consecutive_losses = loss_streaks.max() if len(loss_streaks) > 0 else 0

        # Average trade duration
        df['duration_hours'] = (
            pd.to_datetime(df['updatedTime'], unit='ms') -
            pd.to_datetime(df['createdTime'], unit='ms')
        ).dt.total_seconds() / 3600
        avg_trade_duration = df['duration_hours'].mean()

        # Risk-reward ratio
        risk_reward_ratio = avg_win / avg_loss if avg_loss > 0 else float('inf')

        # Expectancy
        expectancy = (win_rate / 100 * avg_win) - ((100 - win_rate) / 100 * avg_loss)

        # Recovery factor
        recovery_factor = total_pnl / abs(max_drawdown) if max_drawdown != 0 else float('inf')

        # Sharpe ratio (simplified - assumes daily trades)
        if len(df) > 1:
            daily_returns = df['closedPnl'].values
            sharpe_ratio = (np.mean(daily_returns) / np.std(daily_returns)) * np.sqrt(252) if np.std(daily_returns) > 0 else 0
        else:
            sharpe_ratio = 0

        # Trading frequency
        if len(df) > 1:
            time_span = (df['updatedTime'].max() - df['updatedTime'].min()) / (1000 * 86400)  # days
            trades_per_day = total_trades / time_span if time_span > 0 else 0
        else:
            trades_per_day = 0

        # Best/worst day
        df['date'] = pd.to_datetime(df['updatedTime'], unit='ms').dt.date
        daily_pnl = df.groupby('date')['closedPnl'].sum()
        best_day = daily_pnl.max() if len(daily_pnl) > 0 else 0
        worst_day = daily_pnl.min() if len(daily_pnl) > 0 else 0

        return {
            # Basic stats
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'breakeven_trades': breakeven_trades,
            'win_rate': win_rate,

            # P&L
            'total_pnl': total_pnl,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'net_profit': total_pnl,

            # Returns
            'initial_balance': self.initial_balance,
            'final_balance': current_equity,
            'total_return_pct': total_return,

            # Average metrics
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'avg_trade': avg_trade,
            'avg_trade_duration_hours': avg_trade_duration,

            # Risk metrics
            'profit_factor': profit_factor,
            'risk_reward_ratio': risk_reward_ratio,
            'expectancy': expectancy,
            'sharpe_ratio': sharpe_ratio,

            # Drawdown
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown_pct,
            'recovery_factor': recovery_factor,

            # Extremes
            'largest_win': largest_win,
            'largest_loss': largest_loss,
            'max_consecutive_wins': max_consecutive_wins,
            'max_consecutive_losses': max_consecutive_losses,
            'best_day': best_day,
            'worst_day': worst_day,

            # Activity
            'trades_per_day': trades_per_day,

            # Equity curve data
            'equity_curve': df[['updatedTime', 'equity', 'cumulative_pnl', 'drawdown_pct']].to_dict('records'),

            # For charting
            'trade_details': df[['updatedTime', 'closedPnl', 'symbol', 'side']].to_dict('records')
        }

    def _empty_metrics(self) -> Dict:
        """Return empty metrics when no trades"""
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'breakeven_trades': 0,
            'win_rate': 0,
            'total_pnl': 0,
            'gross_profit': 0,
            'gross_loss': 0,
            'net_profit': 0,
            'initial_balance': self.initial_balance,
            'final_balance': self.initial_balance,
            'total_return_pct': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'avg_trade': 0,
            'avg_trade_duration_hours': 0,
            'profit_factor': 0,
            'risk_reward_ratio': 0,
            'expectancy': 0,
            'sharpe_ratio': 0,
            'max_drawdown': 0,
            'max_drawdown_pct': 0,
            'recovery_factor': 0,
            'largest_win': 0,
            'largest_loss': 0,
            'max_consecutive_wins': 0,
            'max_consecutive_losses': 0,
            'best_day': 0,
            'worst_day': 0,
            'trades_per_day': 0,
            'equity_curve': [],
            'trade_details': []
        }


class ChartGenerator:
    """Generates charts for performance reports"""

    @staticmethod
    def create_charts(metrics: Dict, output_dir: Path, period_name: str):
        """Create all performance charts"""
        try:
            import matplotlib
            matplotlib.use('Agg')  # Non-interactive backend
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
            from matplotlib.ticker import FuncFormatter
        except ImportError:
            print("⚠️ matplotlib not installed. Install with: pip install matplotlib")
            print("📊 Skipping chart generation...")
            return {}

        if metrics['total_trades'] == 0:
            print("⚠️ No trades to chart")
            return {}

        charts = {}

        # Set style
        plt.style.use('seaborn-v0_8-darkgrid')

        # 1. Equity Curve
        try:
            equity_data = pd.DataFrame(metrics['equity_curve'])
            equity_data['datetime'] = pd.to_datetime(equity_data['updatedTime'], unit='ms')

            fig, ax = plt.subplots(figsize=(10, 6))
            ax.plot(equity_data['datetime'], equity_data['equity'],
                   linewidth=2, color='#2E86AB', label='Equity')
            ax.axhline(y=metrics['initial_balance'], color='gray',
                      linestyle='--', alpha=0.5, label='Initial Balance')

            ax.set_xlabel('Date', fontsize=11)
            ax.set_ylabel('Equity ($)', fontsize=11)
            ax.set_title(f'Equity Curve - {period_name}', fontsize=14, fontweight='bold')
            ax.legend()
            ax.grid(True, alpha=0.3)

            # Format x-axis
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            plt.xticks(rotation=45)

            plt.tight_layout()
            equity_path = output_dir / f'equity_curve_{period_name.replace(" ", "_")}.png'
            plt.savefig(equity_path, dpi=150, bbox_inches='tight')
            plt.close()
            charts['equity_curve'] = equity_path
            print(f"✅ Generated equity curve chart")
        except Exception as e:
            print(f"⚠️ Failed to create equity curve: {e}")

        # 2. Drawdown Chart
        try:
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.fill_between(equity_data['datetime'], equity_data['drawdown_pct'],
                           0, color='#A23B72', alpha=0.6)
            ax.plot(equity_data['datetime'], equity_data['drawdown_pct'],
                   linewidth=1.5, color='#A23B72')

            ax.set_xlabel('Date', fontsize=11)
            ax.set_ylabel('Drawdown (%)', fontsize=11)
            ax.set_title(f'Drawdown - {period_name}', fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            plt.xticks(rotation=45)

            plt.tight_layout()
            dd_path = output_dir / f'drawdown_{period_name.replace(" ", "_")}.png'
            plt.savefig(dd_path, dpi=150, bbox_inches='tight')
            plt.close()
            charts['drawdown'] = dd_path
            print(f"✅ Generated drawdown chart")
        except Exception as e:
            print(f"⚠️ Failed to create drawdown chart: {e}")

        # 3. Win/Loss Distribution
        try:
            trade_data = pd.DataFrame(metrics['trade_details'])
            wins = trade_data[trade_data['closedPnl'] > 0]['closedPnl']
            losses = trade_data[trade_data['closedPnl'] < 0]['closedPnl']

            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

            # Histogram
            ax1.hist(wins, bins=20, color='#06A77D', alpha=0.7, label='Wins', edgecolor='black')
            ax1.hist(losses, bins=20, color='#D62246', alpha=0.7, label='Losses', edgecolor='black')
            ax1.set_xlabel('P&L ($)', fontsize=11)
            ax1.set_ylabel('Frequency', fontsize=11)
            ax1.set_title('Win/Loss Distribution', fontsize=12, fontweight='bold')
            ax1.legend()
            ax1.grid(True, alpha=0.3)

            # Pie chart
            sizes = [metrics['winning_trades'], metrics['losing_trades'], metrics['breakeven_trades']]
            labels = [f"Wins ({metrics['winning_trades']})",
                     f"Losses ({metrics['losing_trades']})",
                     f"BE ({metrics['breakeven_trades']})"]
            colors = ['#06A77D', '#D62246', '#FFA500']

            # Only show non-zero slices
            non_zero = [(s, l, c) for s, l, c in zip(sizes, labels, colors) if s > 0]
            if non_zero:
                sizes, labels, colors = zip(*non_zero)
                ax2.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
                ax2.set_title('Win/Loss Ratio', fontsize=12, fontweight='bold')

            plt.tight_layout()
            dist_path = output_dir / f'distribution_{period_name.replace(" ", "_")}.png'
            plt.savefig(dist_path, dpi=150, bbox_inches='tight')
            plt.close()
            charts['distribution'] = dist_path
            print(f"✅ Generated distribution chart")
        except Exception as e:
            print(f"⚠️ Failed to create distribution chart: {e}")

        # 4. Cumulative P&L
        try:
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.plot(equity_data['datetime'], equity_data['cumulative_pnl'],
                   linewidth=2, color='#F18F01', label='Cumulative P&L')
            ax.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
            ax.fill_between(equity_data['datetime'], equity_data['cumulative_pnl'], 0,
                           where=(equity_data['cumulative_pnl'] >= 0),
                           color='#06A77D', alpha=0.3, interpolate=True)
            ax.fill_between(equity_data['datetime'], equity_data['cumulative_pnl'], 0,
                           where=(equity_data['cumulative_pnl'] < 0),
                           color='#D62246', alpha=0.3, interpolate=True)

            ax.set_xlabel('Date', fontsize=11)
            ax.set_ylabel('Cumulative P&L ($)', fontsize=11)
            ax.set_title(f'Cumulative P&L - {period_name}', fontsize=14, fontweight='bold')
            ax.legend()
            ax.grid(True, alpha=0.3)
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            plt.xticks(rotation=45)

            plt.tight_layout()
            pnl_path = output_dir / f'cumulative_pnl_{period_name.replace(" ", "_")}.png'
            plt.savefig(pnl_path, dpi=150, bbox_inches='tight')
            plt.close()
            charts['cumulative_pnl'] = pnl_path
            print(f"✅ Generated cumulative P&L chart")
        except Exception as e:
            print(f"⚠️ Failed to create cumulative P&L chart: {e}")

        return charts


class ReportGenerator:
    """Generates performance reports in various formats"""

    def __init__(self, metrics: Dict, period_name: str):
        self.metrics = metrics
        self.period_name = period_name

    def generate_text_summary(self) -> str:
        """Generate text summary for Telegram/console"""
        m = self.metrics

        summary = f"""
📊 **Performance Report - {self.period_name}**

**Overview:**
Total Trades: {m['total_trades']}
Win Rate: {m['win_rate']:.2f}%
Wins: {m['winning_trades']} | Losses: {m['losing_trades']} | BE: {m['breakeven_trades']}

**P&L:**
Net Profit: ${m['net_profit']:.2f}
Total Return: {m['total_return_pct']:.2f}%
Gross Profit: ${m['gross_profit']:.2f}
Gross Loss: ${m['gross_loss']:.2f}

**Performance Metrics:**
Profit Factor: {m['profit_factor']:.2f}
Expectancy: ${m['expectancy']:.2f}
Sharpe Ratio: {m['sharpe_ratio']:.2f}
Risk/Reward: {m['risk_reward_ratio']:.2f}

**Trade Analysis:**
Avg Win: ${m['avg_win']:.2f}
Avg Loss: ${m['avg_loss']:.2f}
Avg Trade: ${m['avg_trade']:.2f}
Largest Win: ${m['largest_win']:.2f}
Largest Loss: ${m['largest_loss']:.2f}

**Risk Metrics:**
Max Drawdown: ${m['max_drawdown']:.2f} ({m['max_drawdown_pct']:.2f}%)
Recovery Factor: {m['recovery_factor']:.2f}
Best Day: ${m['best_day']:.2f}
Worst Day: ${m['worst_day']:.2f}

**Activity:**
Trades/Day: {m['trades_per_day']:.2f}
Avg Duration: {m['avg_trade_duration_hours']:.2f}h
Max Consecutive Wins: {m['max_consecutive_wins']}
Max Consecutive Losses: {m['max_consecutive_losses']}
"""
        return summary.strip()

    def save_to_json(self, output_dir: Path):
        """Save detailed metrics to JSON"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"performance_{self.period_name.replace(' ', '_')}_{timestamp}.json"
        filepath = output_dir / filename

        # Remove trade_details for cleaner JSON (too verbose)
        save_metrics = {k: v for k, v in self.metrics.items() if k != 'trade_details'}

        with open(filepath, 'w') as f:
            json.dump(save_metrics, f, indent=2, default=str)

        print(f"✅ Saved JSON report to {filepath}")
        return filepath

    def save_to_pdf(self, output_dir: Path, charts: Dict = None):
        """Save report to PDF with embedded charts"""
        try:
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        except ImportError:
            print("⚠️ reportlab not installed. Install with: pip install reportlab")
            print("📄 Skipping PDF generation...")
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"performance_{self.period_name.replace(' ', '_')}_{timestamp}.pdf"
        filepath = output_dir / filename

        doc = SimpleDocTemplate(str(filepath), pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f77b4'),
            spaceAfter=30,
            alignment=TA_CENTER
        )

        title = Paragraph(f"Trading Performance Report<br/>{self.period_name}", title_style)
        story.append(title)
        story.append(Spacer(1, 0.2*inch))

        # Report metadata
        meta_style = styles['Normal']
        meta_text = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}<br/>Account: {'Demo' if settings.USE_DEMO else 'Live'}"
        story.append(Paragraph(meta_text, meta_style))
        story.append(Spacer(1, 0.3*inch))

        m = self.metrics

        # Summary table
        summary_data = [
            ['Metric', 'Value'],
            ['Total Trades', str(m['total_trades'])],
            ['Win Rate', f"{m['win_rate']:.2f}%"],
            ['Net Profit', f"${m['net_profit']:.2f}"],
            ['Total Return', f"{m['total_return_pct']:.2f}%"],
            ['Profit Factor', f"{m['profit_factor']:.2f}"],
            ['Sharpe Ratio', f"{m['sharpe_ratio']:.2f}"],
            ['Max Drawdown', f"${m['max_drawdown']:.2f} ({m['max_drawdown_pct']:.2f}%)"],
        ]

        summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f77b4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
        ]))

        story.append(Paragraph("Performance Summary", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        story.append(summary_table)
        story.append(Spacer(1, 0.3*inch))

        # Add charts if available
        if charts:
            story.append(PageBreak())
            story.append(Paragraph("Performance Charts", styles['Heading2']))
            story.append(Spacer(1, 0.2*inch))

            # Equity Curve
            if 'equity_curve' in charts and charts['equity_curve'].exists():
                img = Image(str(charts['equity_curve']), width=6*inch, height=3.6*inch)
                story.append(img)
                story.append(Spacer(1, 0.3*inch))

            # Drawdown
            if 'drawdown' in charts and charts['drawdown'].exists():
                img = Image(str(charts['drawdown']), width=6*inch, height=3.6*inch)
                story.append(img)
                story.append(Spacer(1, 0.3*inch))

            # Distribution
            if 'distribution' in charts and charts['distribution'].exists():
                story.append(PageBreak())
                img = Image(str(charts['distribution']), width=6.5*inch, height=2.7*inch)
                story.append(img)
                story.append(Spacer(1, 0.3*inch))

            # Cumulative P&L
            if 'cumulative_pnl' in charts and charts['cumulative_pnl'].exists():
                img = Image(str(charts['cumulative_pnl']), width=6*inch, height=3.6*inch)
                story.append(img)

        # Detailed metrics on new page
        story.append(PageBreak())

        detailed_data = [
            ['Category', 'Metric', 'Value'],
            ['Trading', 'Winning Trades', str(m['winning_trades'])],
            ['Trading', 'Losing Trades', str(m['losing_trades'])],
            ['Trading', 'Breakeven Trades', str(m['breakeven_trades'])],
            ['Trading', 'Avg Trade Duration', f"{m['avg_trade_duration_hours']:.2f}h"],
            ['Trading', 'Trades per Day', f"{m['trades_per_day']:.2f}"],
            ['P&L', 'Gross Profit', f"${m['gross_profit']:.2f}"],
            ['P&L', 'Gross Loss', f"${m['gross_loss']:.2f}"],
            ['P&L', 'Avg Win', f"${m['avg_win']:.2f}"],
            ['P&L', 'Avg Loss', f"${m['avg_loss']:.2f}"],
            ['P&L', 'Largest Win', f"${m['largest_win']:.2f}"],
            ['P&L', 'Largest Loss', f"${m['largest_loss']:.2f}"],
            ['Risk', 'Expectancy', f"${m['expectancy']:.2f}"],
            ['Risk', 'Risk/Reward Ratio', f"{m['risk_reward_ratio']:.2f}"],
            ['Risk', 'Recovery Factor', f"{m['recovery_factor']:.2f}"],
            ['Risk', 'Best Day', f"${m['best_day']:.2f}"],
            ['Risk', 'Worst Day', f"${m['worst_day']:.2f}"],
            ['Streaks', 'Max Consecutive Wins', str(m['max_consecutive_wins'])],
            ['Streaks', 'Max Consecutive Losses', str(m['max_consecutive_losses'])],
        ]

        detailed_table = Table(detailed_data, colWidths=[1.5*inch, 2.5*inch, 1.5*inch])
        detailed_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f77b4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))

        story.append(Paragraph("Detailed Metrics", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        story.append(detailed_table)

        # Build PDF
        doc.build(story)
        print(f"✅ Saved PDF report to {filepath}")
        return filepath


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description='Analyze Bybit trading performance')
    parser.add_argument('--period', type=str, default='1w',
                       help='Analysis period: 1w (1 week), 1m (1 month), or custom format YYYY-MM-DD:YYYY-MM-DD')
    parser.add_argument('--initial-balance', type=float, default=10000,
                       help='Initial account balance for calculations (default: 10000)')
    parser.add_argument('--no-telegram', action='store_true',
                       help='Skip sending Telegram notification')
    parser.add_argument('--no-pdf', action='store_true',
                       help='Skip PDF generation')
    parser.add_argument('--no-charts', action='store_true',
                       help='Skip chart generation')

    args = parser.parse_args()

    # Parse period
    now = datetime.now(timezone.utc)

    if args.period == '1w':
        start_time = now - timedelta(days=7)
        period_name = "Last_1_Week"
    elif args.period == '1m':
        start_time = now - timedelta(days=30)
        period_name = "Last_1_Month"
    elif ':' in args.period:
        # Custom period: YYYY-MM-DD:YYYY-MM-DD
        try:
            start_str, end_str = args.period.split(':')
            start_time = datetime.strptime(start_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            end_time = datetime.strptime(end_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            period_name = f"{start_str}_to_{end_str}"
        except ValueError:
            print("❌ Invalid custom period format. Use: YYYY-MM-DD:YYYY-MM-DD")
            return
    else:
        print("❌ Invalid period. Use: 1w, 1m, or YYYY-MM-DD:YYYY-MM-DD")
        return

    # Set end time if not custom
    if ':' not in args.period:
        end_time = now

    start_ms = int(start_time.timestamp() * 1000)
    end_ms = int(end_time.timestamp() * 1000)

    print(f"\n{'='*60}")
    print(f"📊 Starting Performance Analysis: {period_name.replace('_', ' ')}")
    print(f"{'='*60}\n")

    # Initialize API client
    print("🔌 Connecting to Bybit API...")
    api_client = BybitAPIClient()

    # Fetch closed P&L data
    print(f"📥 Fetching closed trades from {start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}...")
    closed_pnl = api_client.get_position_closed_pnl(
        start_time=start_ms,
        end_time=end_ms,
        limit=50
    )

    print(f"✅ Retrieved {len(closed_pnl)} closed positions")

    if len(closed_pnl) == 0:
        print("⚠️ No trades found for the specified period")
        print("\n💡 Tips:")
        print("  - Verify you have closed positions in this date range")
        print("  - Check if API credentials have correct permissions")
        print("  - Ensure you're using the correct account (demo/live)")
        return

    # Convert to DataFrame
    trades_df = pd.DataFrame(closed_pnl)

    # Ensure required columns and convert types
    trades_df['closedPnl'] = pd.to_numeric(trades_df['closedPnl'])
    trades_df['avgEntryPrice'] = pd.to_numeric(trades_df['avgEntryPrice'])
    trades_df['avgExitPrice'] = pd.to_numeric(trades_df['avgExitPrice'])
    trades_df['qty'] = pd.to_numeric(trades_df['qty'])
    trades_df['createdTime'] = pd.to_numeric(trades_df['createdTime'])
    trades_df['updatedTime'] = pd.to_numeric(trades_df['updatedTime'])

    # Rename columns for consistency
    trades_df = trades_df.rename(columns={
        'avgEntryPrice': 'entryPrice',
        'avgExitPrice': 'exitPrice'
    })

    print(f"\n📈 Analyzing performance...")

    # Analyze performance
    analyzer = PerformanceAnalyzer(trades_df, initial_balance=args.initial_balance)
    metrics = analyzer.calculate_metrics()

    # Generate charts
    charts = {}
    if not args.no_charts:
        print(f"\n📊 Generating performance charts...")
        docs_dir = Path(__file__).parent.parent / "docs"
        docs_dir.mkdir(exist_ok=True)
        charts = ChartGenerator.create_charts(metrics, docs_dir, period_name)

    # Generate reports
    print(f"\n📄 Generating reports...")

    docs_dir = Path(__file__).parent.parent / "docs"
    docs_dir.mkdir(exist_ok=True)

    report_gen = ReportGenerator(metrics, period_name.replace('_', ' '))

    # Save JSON
    report_gen.save_to_json(docs_dir)

    # Save PDF (if not disabled and reportlab available)
    if not args.no_pdf:
        report_gen.save_to_pdf(docs_dir, charts=charts)

    # Print summary to console
    summary = report_gen.generate_text_summary()
    print(f"\n{summary}\n")

    # Send to Telegram (if not disabled)
    if not args.no_telegram:
        print("📱 Sending summary to Telegram...")
        try:
            send_telegram_message(summary)
            print("✅ Telegram notification sent")
        except Exception as e:
            print(f"❌ Failed to send Telegram notification: {e}")

    print(f"\n{'='*60}")
    print("✅ Performance analysis complete!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
