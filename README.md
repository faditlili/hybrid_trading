
# AI QUANT 4.0

AI QUANT is an advanced AI-assisted cryptocurrency market analysis and paper portfolio simulation system.

It combines public market data, technical indicators, multi-timeframe analysis, AI-assisted decision evaluation, news risk filtering, and simulated portfolio management.

> **PAPER TRADING ONLY**
>
> AI QUANT does not execute real cryptocurrency orders.
> All positions, fees, profits, and losses are simulated.

---

## 1. Features

### Market Analysis
- Public BingX market data.
- Multiple cryptocurrency pairs.
- Multi-timeframe analysis: 15m, 1h, and 4h.
- Technical indicator calculations.
- Market price monitoring.
- OHLCV data validation.

### AI Analysis
- Optional Hugging Face AI council.
- Multiple AI model opinions.
- BUY, SELL, and HOLD classification.
- Minimum model agreement requirement.
- Fail-closed behavior when AI is unavailable.
- AI analysis is advisory and cannot bypass risk controls.

### News Risk Filtering
- RSS news monitoring.
- Critical headline detection.
- English and Arabic risk keywords.
- News failures do not authorize new entries.
- Headlines do not independently create trade signals.

### Risk Management
- Aggregate open-position risk limit.
- Portfolio exposure limit.
- Dynamic equity-based calculations.
- Maximum open positions.
- Simulated stop-loss and take-profit.
- Trading fee simulation.
- Slippage simulation.

The aggregate theoretical risk of simultaneously open positions is limited to 10% of current portfolio equity, subject to the configured risk calculations.

This is a simulation control, not a guarantee of maximum real-world loss.

### Paper Trading
- Virtual starting balance.
- Simulated position opening and closing.
- Realized and unrealized PnL.
- Simulated trade history.
- SQLite persistence.
- Duplicate position protection.

### Dashboard
- Portfolio status.
- Current equity and cash.
- Portfolio exposure.
- Open-position risk.
- Remaining risk budget.
- Open simulated positions.
- Recent simulated trades.
- AI decision history.
- System status.

The dashboard is read-only and does not execute trades.

### Telegram
- Optional Telegram integration.
- Administrator-only commands.
- `/status` portfolio monitoring.
- `/positions` open-position monitoring.
- Automatic simulated trade opening notifications.
- Automatic simulated trade closing notifications.
- Trade notifications include relevant entry, exit, quantity, fees, PnL, and closing reason details.

Telegram failures must not stop the paper trading engine.

---

## 2. Technology Stack

- Python 3.11
- FastAPI
- Uvicorn
- Gradio
- Pandas
- NumPy
- pandas-ta
- aiohttp
- SQLite
- Hugging Face API (optional)
- python-telegram-bot (optional)
- Docker
- Render

---

## 3. Project Structure

```text
AI_QUANT/
│
├── .github/
│   └── workflows/
│       └── ci.yml
│
├── Dockerfile
├── render.yaml
├── requirements.txt
├── README.md
├── .env.example
│
├── config.py
├── main.py
├── engine.py
├── market_data.py
├── technical_analysis.py
├── decision_engine.py
├── ai_council.py
├── news_engine.py
├── paper_trading.py
├── database.py
├── dashboard.py
├── telegram_bot.py
│
└── tests/
    └── test_core.py
```

The SQLite database is created automatically using `DB_PATH`.

Do not commit database files containing private or personal information.

---

## 4. Requirements

- Python 3.11
- Internet access for public market data and optional external services.
- Optional Hugging Face token.
- Optional Telegram bot token and administrator ID.

---

## 5. Installation

Clone or download the project.

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
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---

## 6. Configuration

Configure the application through environment variables.

Important settings include:

| Variable | Purpose |
|---|---|
| HOST | Application host |
| PORT | Application port |
| DB_PATH | SQLite database location |
| SYMBOLS | Cryptocurrency pairs |
| TIMEFRAME | Primary analysis timeframe |
| TIMEFRAMES | Analysis timeframes |
| KLINE_LIMIT | Historical candle count |
| SCAN_INTERVAL_SECONDS | Market scan interval |
| MIN_SCORE_TO_ENTER | Minimum technical score |
| HF_TOKEN | Optional Hugging Face token |
| HF_MODELS | AI council models |
| TELEGRAM_TOKEN | Optional Telegram bot token |
| TELEGRAM_ADMIN_ID | Authorized Telegram administrator |

Never publish tokens or private credentials.

### Paper trading mode

The application must remain in paper trading mode.

```python
PAPER_MODE = True
```

The application must not contain or execute real exchange order operations.

---

## 7. Risk Management

AI QUANT uses two separate portfolio controls:

- Aggregate theoretical open-position risk: maximum 10% of current portfolio equity.
- Portfolio market exposure: maximum 10% of current portfolio equity.

These limits are calculated separately.

Portfolio equity is updated using available market prices and simulated realized and unrealized results.

The risk budget changes as portfolio equity changes.

A new position must be rejected if it would exceed the configured risk or exposure limits.

---

## 8. Running Locally

Start the application:

```bash
python main.py
```

Open the dashboard:

```text
http://127.0.0.1:7860/ui/
```

Health endpoint:

```text
http://127.0.0.1:7860/health
```

The actual port depends on the `PORT` environment variable.

---

## 9. API Endpoints

| Endpoint | Description |
|---|---|
| `/` | Application information |
| `/health` | Health check |
| `/api/health` | API health check |
| `/status` | Portfolio status |
| `/dashboard/status` | Dashboard portfolio data |
| `/dashboard/positions` | Open simulated positions |
| `/dashboard/trades` | Recent simulated trades |
| `/dashboard/decisions` | AI decision history |
| `/system/status` | Engine status |
| `/ui/` | Gradio dashboard |

The dashboard API is read-only.

**Access warning:** The dashboard and data endpoints do not require login. Anyone with access to the service URL may be able to read the exposed data.

---

## 10. Telegram Notifications

Telegram is optional.

When configured, the administrator can receive automatic notifications after simulated trade events.

Opening notifications include:
- Symbol.
- Entry price.
- Quantity.
- Stop-loss.
- Take-profit.

Closing notifications include:
- Symbol.
- Entry and exit prices.
- Quantity.
- Gross PnL.
- Fees.
- Net PnL.
- Closing reason.

Telegram notification failures must not interrupt market analysis or paper trading.

---

## 11. Docker

Build the image:

```bash
docker build -t ai-quant .
```

Run the container:

```bash
docker run \
  -p 7860:7860 \
  -v ai-quant-data:/data \
  -e DB_PATH=/data/ai_quant.db \
  ai-quant
```

The mounted volume preserves the SQLite database across container recreation.

---

## 12. Render Deployment

The project includes a `render.yaml` configuration.

Important deployment settings:

- Docker runtime.
- Health check: `/health`.
- Database path: `/data/ai_quant.db`.
- Persistent disk mounted at `/data`.

A persistent disk must be available and successfully mounted for database persistence.

Check Render's current plan and disk availability before deployment.

---

## 13. Testing

Compile Python files:

```bash
python -m compileall -q .
```

Run unit tests:

```bash
python -m unittest discover -s tests -v
```

The CI workflow runs compilation and unit tests on GitHub Actions.

A successful compilation does not prove that external APIs or every runtime integration is working.

---

## 14. Security

- Keep paper trading mode enabled.
- Never publish API tokens.
- Do not store private exchange credentials.
- Restrict access to Telegram administration.
- Protect database files and backups.
- Remember that the dashboard is public unless access is restricted externally.
- Use HTTPS for externally exposed services.

---

## 15. Disclaimer

AI QUANT is an educational software project for market analysis and simulated portfolio management.

It is not financial advice.

AI-generated analysis and market data may be inaccurate, delayed, incomplete, or unavailable.

Paper trading results do not guarantee future performance.

The application is designed for paper simulation only.

---

## 16. Project Information

**Application:** AI QUANT

**Version:** 4.0.0

**Analysis:** Advanced multi-timeframe

**Mode:** PAPER TRADING ONLY

**Market Data:** BingX public endpoints

**Database:** SQLite

**Runtime:** Python 3.11
```
