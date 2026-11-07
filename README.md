AI QUANT 4.0

AI QUANT is an advanced AI-assisted cryptocurrency market analysis and paper portfolio simulation system.

It combines public market data, technical indicators, multi-timeframe analysis, AI-assisted decision evaluation, news risk filtering, and simulated portfolio management.

«PAPER TRADING ONLY

AI QUANT does not execute real cryptocurrency orders.
All positions, fees, profits, and losses are simulated.
No private exchange endpoints or real order execution are used.»

---

1. Features

Market Analysis

- Public BingX market data.
- Multiple cryptocurrency pairs.
- Multi-timeframe analysis: 15m, 1h, and 4h.
- Technical indicator calculations.
- Market price monitoring.
- OHLCV data validation.
- Historical candle analysis.

AI Analysis

- Optional Hugging Face AI council.
- Multiple AI model opinions.
- BUY, SELL, and HOLD classification.
- Minimum model agreement requirement.
- Fail-closed behavior when AI is unavailable.
- AI analysis is advisory and cannot bypass risk controls.

News Risk Filtering

- RSS news monitoring.
- Critical headline detection.
- English and Arabic risk keywords.
- News failures do not authorize new entries.
- Headlines do not independently create trade signals.

Risk Management

- Aggregate open-position risk limit.
- Portfolio exposure limit.
- Dynamic equity-based calculations.
- Maximum open positions.
- Simulated stop-loss and take-profit.
- Trading fee simulation.
- Slippage simulation.
- Duplicate position protection.

The aggregate theoretical risk of simultaneously open positions is limited to 10% of current portfolio equity.

The portfolio exposure limit is a separate control, also configured at 10% of current portfolio equity.

Both limits are calculated independently.

These are simulation controls and do not guarantee maximum real-world losses.

Paper Trading

- Virtual starting balance.
- Simulated position opening and closing.
- Realized and unrealized PnL.
- Simulated trade history.
- SQLite persistence.
- Dynamic portfolio equity calculations.
- Risk-budget recalculation.

Dashboard

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

Telegram

- Optional Telegram integration.
- Administrator-only commands.
- "/status" portfolio monitoring.
- "/positions" open-position monitoring.
- Automatic simulated trade opening notifications.
- Automatic simulated trade closing notifications.
- Opening notifications include entry price, quantity, stop-loss, and take-profit.
- Closing notifications include entry and exit prices, fees, PnL, and closing reason.

Telegram notification failures must not stop the paper trading engine.

---

2. Technology Stack

- Python 3.11
- FastAPI
- Uvicorn
- Gradio
- Pandas
- NumPy
- pandas-ta-classic
- aiohttp
- SQLite
- Hugging Face API (optional)
- python-telegram-bot (optional)
- Docker
- Render

---

3. Project Structure

AI_QUANT/
│
├── .github/
│   └── workflows/
│       └── ci.yml
│
├── .dockerignore
├── .gitignore
├── .env.example
├── Dockerfile
├── render.yaml
├── requirements.txt
├── README.md
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

The SQLite database is created automatically using the "DB_PATH" environment variable.

Do not commit database files containing private or personal information.

---

4. Requirements

- Python 3.11.
- Internet access for public market data and optional external services.
- Optional Hugging Face API token.
- Optional Telegram bot token and administrator ID.
- Docker for containerized deployment.

---

5. Installation

Clone or download the project.

Create a virtual environment:

python -m venv venv

Activate it on Windows:

venv\Scripts\activate

Activate it on Linux:

source venv/bin/activate

Upgrade pip:

python -m pip install --upgrade pip

Install dependencies:

python -m pip install -r requirements.txt

---

6. Configuration

Configure the application through environment variables.

Main settings

Variable| Purpose
"HOST"| Application host
"PORT"| Application port
"DB_PATH"| SQLite database location
"SYMBOLS"| Cryptocurrency pairs
"TIMEFRAMES"| Analysis timeframes
"KLINE_LIMIT"| Historical candle count
"SCAN_INTERVAL_SECONDS"| Market scan interval
"STARTING_BALANCE"| Initial virtual balance
"MIN_SCORE_TO_ENTER"| Minimum technical score
"MAX_OPEN_POSITIONS"| Maximum simultaneous positions

Risk settings

Variable| Purpose
"PORTFOLIO_RISK_FRACTION"| Aggregate theoretical open-position risk limit
"PORTFOLIO_EXPOSURE_LIMIT"| Maximum portfolio market exposure
"FEE_RATE"| Simulated trading fee
"SLIPPAGE_BPS"| Simulated slippage
"STOP_ATR_MULTIPLIER"| Stop-loss ATR multiplier
"TARGET_R_MULTIPLIER"| Take-profit reward multiplier

AI settings

Variable| Purpose
"HF_TOKEN"| Optional Hugging Face token
"HF_API_URL"| Hugging Face API endpoint
"HF_MODELS"| AI council models
"AI_TIMEOUT_SECONDS"| AI request timeout
"AI_MIN_MODELS"| Minimum AI models
"AI_MIN_AGREEMENT"| Minimum model agreement

Telegram settings

Variable| Purpose
"TELEGRAM_TOKEN"| Optional Telegram bot token
"TELEGRAM_ADMIN_ID"| Authorized Telegram administrator

Network and dashboard settings

Variable| Purpose
"HTTP_TIMEOUT_SECONDS"| Network request timeout
"NEWS_REFRESH_SECONDS"| News refresh interval
"API_URL"| Dashboard backend URL
"DASHBOARD_HTTP_TIMEOUT"| Dashboard API timeout
"LOG_LEVEL"| Application logging level

Refer to ".env.example" for the available configuration template.

Never publish tokens or private credentials.

Paper trading mode

The application must remain in paper trading mode.

PAPER_MODE = True

This setting is enforced by the application configuration.

The application must not execute real exchange orders.

---

7. Risk Management

AI QUANT uses two separate portfolio controls.

Aggregate theoretical open-position risk

The maximum combined theoretical risk of all simultaneously open positions is:

Portfolio Equity × 10%

The system calculates the remaining risk budget before accepting a new simulated position.

Portfolio exposure

The maximum portfolio exposure is independently configured as:

Portfolio Equity × 10%

Exposure and theoretical risk are not the same measurement.

Dynamic equity

Portfolio equity is recalculated using available market prices and simulated realized and unrealized results.

The risk budget changes as portfolio equity changes.

A new position must be rejected if opening it would exceed either configured limit.

These controls apply to the paper simulation only.

---

8. Running Locally

Start the application:

uvicorn main:app --host 0.0.0.0 --port 7860

Open the dashboard:

http://127.0.0.1:7860/ui/

Health endpoint:

http://127.0.0.1:7860/health

API health endpoint:

http://127.0.0.1:7860/api/health

The actual port depends on the "PORT" environment variable.

---

9. API Endpoints

Endpoint| Description
"/"| Application information
"/health"| Health check
"/api/health"| API health check
"/status"| Portfolio status
"/dashboard/status"| Dashboard portfolio data
"/dashboard/positions"| Open simulated positions
"/dashboard/trades"| Recent simulated trades
"/dashboard/decisions"| AI decision history
"/system/status"| Engine status
"/ui/"| Gradio dashboard

The dashboard API is read-only.

Access warning

The dashboard and data endpoints do not require login.

Anyone with access to the service URL may be able to read the exposed portfolio and simulation data.

Do not expose sensitive information through dashboard endpoints.

---

10. Telegram Notifications

Telegram integration is optional.

When configured, the administrator can receive automatic notifications after simulated trade events.

Opening notifications

Include:

- Symbol.
- Entry price.
- Quantity.
- Stop-loss.
- Take-profit.
- Position value.
- Opening fee.

Closing notifications

Include:

- Symbol.
- Entry price.
- Exit price.
- Quantity.
- Gross PnL.
- Entry and exit fees.
- Total fees.
- Net PnL.
- Closing reason.

Telegram notification failures must not interrupt market analysis or paper trading.

Available administrator commands:

/status
/positions

---

11. Docker

Build the image:

docker build -t ai-quant .

Run the container with persistent local storage:

docker run \
  -p 7860:7860 \
  -v ai-quant-data:/data \
  -e DB_PATH=/data/ai_quant.db \
  ai-quant

The mounted Docker volume preserves the SQLite database across container recreation, provided the volume is retained.

The Dockerfile uses "/data/ai_quant.db" as its default database path.

---

12. Render Deployment

The project includes a "render.yaml" configuration for Render Free.

Important deployment settings:

- Docker runtime.
- Health check: "/health".
- Database path: "/tmp/ai_quant.db".
- No persistent disk on the Free plan.

Render Free limitations

- The service may sleep after a period without incoming traffic.
- The SQLite database is stored on temporary filesystem storage.
- Database contents may be lost after restarts, redeployments, or instance replacement.
- Health checks do not guarantee that the service will remain continuously awake.
- Continuous uptime and persistent storage are not guaranteed by the Free plan.

Future persistent storage configuration

When upgrading to a Render plan that supports persistent disks:

1. Add a persistent disk.
2. Mount it at "/data".
3. Change the database environment variable to:

DB_PATH=/data/ai_quant.db

4. Verify that the disk is mounted and writable.

Check Render's current plan features and pricing before enabling persistent storage.

---

13. Testing

Compile Python files:

python -m compileall -q .

Run unit tests:

python -m unittest discover -s tests -v

The GitHub Actions CI workflow performs dependency installation, Python compilation, and unit testing.

A successful compilation does not prove that external APIs, market data endpoints, or every runtime integration are working correctly.

External integrations should be tested separately.

---

14. Security

- Keep paper trading mode enabled.
- Never publish API tokens.
- Do not store private exchange credentials.
- Restrict access to Telegram administration.
- Protect database files and backups.
- Remember that the dashboard is public unless access is restricted externally.
- Use HTTPS for externally exposed services.
- Do not expose sensitive information through public API endpoints.

---

15. Disclaimer

AI QUANT is an educational software project for cryptocurrency market analysis and simulated portfolio management.

It is not financial advice.

AI-generated analysis and market data may be inaccurate, delayed, incomplete, or unavailable.

Paper trading results do not guarantee future performance.

The application is designed for paper simulation only and does not execute real cryptocurrency orders.

---

16. Project Information

Application: AI QUANT

Version: 4.0.0

Exchange Data Source: BingX public market endpoints

Analysis: Advanced multi-timeframe

AI Scope: All supported analysis components

Trading Mode: PAPER TRADING ONLY

Database: SQLite

Runtime: Python 3.11

Deployment: Docker / Render
