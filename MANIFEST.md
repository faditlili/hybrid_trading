AI QUANT — Project Manifest

Version: 4.0.0
Project: AI QUANT
Exchange: BingX
Analysis Mode: Advanced
AI Scope: ALL
Trading Mode: Paper Trading (Simulation Only)

---

1. Project Structure

AI-QUANT/
├── .github/
│   └── workflows/
│       └── ci.yml
├── .dockerignore
├── .gitignore
├── .env.example
├── Dockerfile
├── README.md
├── MANIFEST.md
├── requirements.txt
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
└── telegram_bot.py

2. Core Features

- BingX public market-data integration.
- Advanced multi-timeframe technical analysis.
- AI Council decision support.
- Market news analysis and risk filtering.
- Portfolio-wide risk management.
- Paper trading simulation.
- Automatic Telegram trade notifications.
- Interactive read-only dashboard.
- SQLite database persistence.
- Automated CI validation.
- Docker deployment support.
- Render deployment support.
- Health monitoring endpoint.

3. Risk Management

- Maximum aggregate open-position risk: 10% of current total portfolio equity.
- The 10% limit applies to all simultaneously open positions combined, not to each position individually.
- Portfolio equity reflects realized profits and losses and current position valuations.
- New simulated positions must respect the remaining portfolio risk budget.
- Market exposure has a separate configurable limit.
- Position sizing must respect available simulated cash.
- Stop-loss and take-profit levels are calculated by the simulation engine.
- Risk limits must be checked before every simulated position opening.

4. Trading Mode

- Paper trading only.
- No real-money trading.
- No real exchange order execution.
- No private exchange trading endpoints.
- No exchange API trading credentials required.
- All positions and transactions are simulated and stored locally.

5. AI Council

- Supports multiple AI models.
- Uses configurable Hugging Face API settings.
- Requires a configurable minimum number of model responses.
- Uses an agreement threshold for consensus.
- AI responses are advisory and cannot independently bypass risk controls.
- Unavailable, invalid, or conflicting AI responses must fail safely.

6. Market Analysis

- Exchange: BingX.
- Supported default symbols:
  - BTC-USDT
  - ETH-USDT
  - BNB-USDT
  - SOL-USDT
  - XRP-USDT
- Multi-timeframe analysis:
  - 15m
  - 1h
  - 4h
- Technical indicators include EMA, RSI, MACD, ATR, and volume analysis.
- News headlines act as a risk filter and do not independently generate trade signals.

7. Telegram Integration

- Optional Telegram bot.
- Admin-only commands.
- "/status" for system status.
- "/positions" for open simulated positions.
- Automatic notification when a simulated position opens.
- Automatic notification when a simulated position closes.
- Opening and closing notifications include relevant trade details.
- Telegram failures must never stop the trading simulation.
- Notifications must only be sent after the corresponding database transaction succeeds.

8. Dashboard

- Interactive read-only dashboard.
- Displays account and portfolio information.
- Displays open simulated positions.
- Displays trade history.
- Displays recent decisions.
- No username/password prompt.
- Dashboard endpoints are unauthenticated; access to the service URL should therefore be restricted appropriately.

9. Database

- SQLite persistence.
- Account balance and equity tracking.
- Open and closed position records.
- Trade history.
- Decision history.
- Event logging.
- Database migration support.
- Persistent storage recommended for deployment.

10. Security

- Environment variables for sensitive configuration.
- No hardcoded API credentials.
- No real exchange trading credentials.
- Input validation.
- Defensive error handling.
- Safe HTTP request timeouts.
- Restricted CORS configuration.
- No secrets committed to Git.
- ".env.example" contains placeholders only.

11. Deployment

- Python 3.11.
- Docker support.
- Render deployment configuration.
- Configurable host and port.
- Persistent database path: "/data/ai_quant.db".
- Health endpoint: "/health".
- Single application worker for SQLite consistency.

12. Automated Validation

- Python compilation checks.
- Unit tests.
- Technical indicator validation.
- Portfolio risk-limit validation.
- Position-opening and closing tests.
- Database persistence tests.
- Fail-safe AI response tests.

13. Important Safety Requirements

- The application must remain in simulation mode.
- No real exchange orders may be submitted.
- No code path may bypass portfolio risk limits.
- AI decisions must not override safety checks.
- Invalid market data must not authorize a simulated entry.
- Failed news checks must not authorize a new entry.
- Failed notifications must not interrupt the engine.

14. Project Status

This manifest documents the intended architecture, project structure, and required features of AI QUANT 4.0.

It does not independently verify that every feature has been implemented or tested.

Final project readiness requires source-code integration, dependency validation, unit testing, and deployment checks.

---

AI QUANT 4.0
Paper Trading — Simulation Only
