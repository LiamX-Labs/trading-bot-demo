# LXAlgo: Automated Crypto Trading Bot

## Overview

LXAlgo is an advanced, fully automated cryptocurrency trading bot designed for Bybit USDT perpetual contracts. It features robust risk management, dynamic symbol selection, and seamless Telegram integration for real-time alerts. The bot is optimized for cloud deployment (AWS EC2, Docker) and is suitable for both live and demo trading environments.

---

## Features

- **Dynamic Symbol Selection**: Monitors the top 100 USDT pairs by 24h volume, refreshing every 4 hours to adapt to market conditions.
- **Automated Trading**: Executes trades based on technical indicators and custom rules.
- **Breakeven Logic**: Automatically moves stop-loss to entry price when a trade reaches a configurable profit threshold.
- **Risk Management**: Includes daily and intraday drawdown protection, auto-expiry of stale trades, and position reconciliation.
- **Trade Persistence**: Recovers open trades after restarts using a persistent trade log.
- **Telegram Alerts**: Sends real-time notifications for trade actions, risk events, and system status.
- **Optimized for Cloud**: Low memory and CPU usage, suitable for AWS free tier and Docker environments.

---

## Quick Start (Docker)

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd lxalgo
   ```
2. **Configure environment variables:**
   - Copy `.env.example` to `.env` and fill in your Bybit API keys and Telegram bot info.
3. **Build and run with Docker Compose:**
   ```bash
   docker-compose up --build
   ```

---

## Manual Setup (Linux)

1. **Install dependencies:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Configure environment variables:**
   - Copy `.env.example` to `.env` and fill in your Bybit API keys and Telegram bot info.
3. **Run the bot:**
   ```bash
   python main.py
   ```

---

## Environment Variables (.env)

- `BYBIT_API_KEY`         - Your Bybit API key
- `BYBIT_API_SECRET`      - Your Bybit API secret
- `BYBIT_USE_DEMO`        - `true` for testnet, `false` for mainnet
- `TELEGRAM_BOT_TOKEN`    - Telegram bot token
- `TELEGRAM_CHAT_ID`      - Telegram chat ID for alerts

---

## Usage & Operation

- **Startup**: The bot fetches the top 100 USDT pairs and loads historical data.
- **Symbol Refresh**: Every 4 hours, the bot updates its symbol list and WebSocket subscriptions to always monitor the most relevant altcoins.
- **Trade Logic**: Trades are opened based on technical signals (RSI, volatility, volume, etc.).
- **Breakeven**: When a trade reaches the configured profit threshold (default: 8%), the stop-loss is moved to entry price.
- **Risk Management**: Includes auto-expiry (72h), daily/intraday drawdown checks, and reconciliation with Bybit positions.
- **Telegram Alerts**: All major events (trade open/close, breakeven, risk triggers, errors) are sent to your Telegram chat.

---

## Architecture

- `main.py`           - Main event loop, symbol management, monitors
- `order_manager.py`  - Trade execution, stop-loss, breakeven logic
- `risk_manager.py`   - Risk checks, drawdown, breakeven monitor
- `trade_tracker.py`  - Persistent trade log and recovery
- `telegram_alerts.py`- Telegram notification system
- `settings.py`       - Configurable parameters
- `Dockerfile`, `docker-compose.yml` - Containerization

---

## Troubleshooting

- **No trades opening?**
  - Check your Bybit API keys and permissions
  - Ensure your account has sufficient balance
- **No Telegram alerts?**
  - Verify your bot token and chat ID in `.env`
  - Check for 429 (rate limit) errors in logs
- **Bot not refreshing symbols?**
  - Ensure the bot is running continuously; symbol refresh occurs every 4 hours
- **Breakeven not triggering?**
  - Check the profit threshold in `settings.py` (`BREAKEVEN_THRESHOLD`)
  - Review logs for precision/tolerance issues

---

## License

MIT License 