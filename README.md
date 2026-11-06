
# AI QUANT 3.1

AI QUANT is an AI-assisted cryptocurrency market analysis and paper trading system.

It combines:
- Market data from Binance.
- Technical indicators.
- AI-based decision analysis.
- Market regime detection.
- News analysis.
- Simulated portfolio management.
- Risk management.
- SQLite database.
- Gradio dashboard.
- Optional Telegram monitoring.

> IMPORTANT: AI QUANT operates in PAPER TRADING MODE ONLY.
> It does not execute real cryptocurrency orders.

---

## 1. Project Features

### Market Analysis
- Binance public market data.
- Multiple cryptocurrency pairs.
- 15-minute timeframe.
- Technical indicator calculations.
- Market liquidity filtering.

### AI Analysis
- AI-assisted market evaluation.
- BUY, SELL, HOLD decisions.
- AI approval scoring.
- News sentiment context.

### Risk Management
- Simulated position sizing.
- Stop-loss calculations.
- Take-profit calculations.
- Trading fee simulation.
- Slippage simulation.
- Maximum open positions.
- Portfolio exposure limits.

### Paper Trading
- Simulated account balance.
- Virtual positions.
- Unrealized PnL.
- Realized PnL.
- Simulated trade history.
- SQLite persistence.

### Dashboard
- Account overview.
- Market regime.
- Scanner statistics.
- AI decision history.
- Open paper positions.
- Closed paper trades.
- System events.
- Manual market scanning.
- Automatic dashboard refresh.

### Telegram
- Optional Telegram integration.
- Status monitoring.
- Manual scan command.
- Position monitoring.
- Administrator authorization.

---

## 2. Project Structure

```text
AI_QUANT/
│
├── .github/
│
├── Dockerfile
│
├── README.md
│
├── requirements.txt
│
├── config.py
│
├── main.py
│
├── engine.py
│
├── market_data.py
│
├── technical_analysis.py
│
├── decision_engine.py
│
├── ai_council.py
│
├── news_engine.py
│
├── paper_trading.py
│
├── database.py
│
├── dashboard.py
│
├── telegram_bot.py
│
└── ai_quant.db
```

The database file is created automatically when the application initializes, depending on the configured database path.

---

## 3. Requirements

- Python 3.11
- Internet connection
- Binance public market data access
- Optional Hugging Face API token
- Optional Telegram bot token

---

## 4. Installation

Clone or download the project.

Open a terminal inside the project directory.

Create a virtual environment:

```bash
python -m venv venv
```

Activate it on Windows:

```bash
venv\Scripts\activate
```

Activate it on Linux:

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 5. Configuration

Configure the project using environment variables.

Important settings include:

| Variable | Description |
|---|---|
| HOST | Application host |
| PORT | Dashboard port |
| DB_PATH | SQLite database path |
| HF_TOKEN | Optional Hugging Face token |
| TELEGRAM_BOT_TOKEN | Optional Telegram token |
| TELEGRAM_ADMIN_ID | Authorized Telegram administrator |

Never publish API tokens or private credentials.

The application must remain configured with:

```python
PAPER_MODE = True
```

Do not disable paper mode.

---

## 6. Running AI QUANT

Start the application:

```bash
python main.py
```

Open the dashboard:

```text
http://127.0.0.1:7860
```

The port may differ if configured differently.

---

## 7. Dashboard

The dashboard provides:

- Available balance.
- Total equity.
- Realized PnL.
- Unrealized PnL.
- Reserved capital.
- Win rate.
- Open positions.
- Scanner status.
- Market regime.
- AI decision history.
- Closed paper trades.
- System events.

Dashboard data refreshes automatically every 15 seconds.

---

## 8. Paper Trading

All trading operations are simulated.

The system uses configured parameters for:

- Initial balance.
- Risk per trade.
- Maximum allocation.
- Trading fees.
- Simulated slippage.
- Stop-loss distance.
- Take-profit distance.
- Maximum open positions.

Paper trading results are simulations, not predictions or guarantees of future performance.

---

## 9. Database

AI QUANT uses SQLite to store:

- Account information.
- Open positions.
- Closed trades.
- Trading decisions.
- System events.

Keep regular backups of the database.

Do not delete the database while the application is running.

---

## 10. Docker

Build the Docker image:

```bash
docker build -t ai-quant .
```

Run the container:

```bash
docker run -p 7860:7860 ai-quant
```

For persistent database storage, configure a suitable mounted volume and DB_PATH.

---

## 11. Security

- Never publish API tokens.
- Do not expose the dashboard publicly without authentication and network restrictions.
- Restrict access to Telegram administration.
- Protect database backups.
- Keep PAPER_MODE enabled.

The public health and status endpoints are intended for operational monitoring, not financial account access.

---

## 12. Disclaimer

AI QUANT is an educational software project for cryptocurrency market analysis and simulated trading.

It is not financial advice.

Simulated performance does not guarantee real-world performance.

Market data, AI analysis, and technical indicators may be inaccurate or unavailable.

The software is designed to operate in paper trading mode only.

---

## 13. Project Version

**Application:** AI QUANT

**Version:** 3.1.0

**Mode:** PAPER TRADING ONLY

**Python:** 3.11
