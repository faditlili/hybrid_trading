AI QUANT — Project Manifest

Version: 4.0.0
Project: AI QUANT
Exchange: BingX
Analysis Mode: Advanced
AI Scope: ALL
Trading Mode: Paper Trading (Simulation Only)

Project Structure

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

Core Features

- BingX market data integration.
- Advanced technical analysis.
- AI Council decision support.
- Market news analysis.
- Risk management based on total portfolio equity.
- Paper trading simulation.
- Telegram bot integration.
- Interactive dashboard.
- Database persistence.
- Automated CI validation.
- Docker deployment support.

Risk Management

- Risk allocation reference: 10% of total portfolio.
- Portfolio equity includes realized profits and losses.
- Simulation mode only.
- No real-money order execution.

Security

- Environment variables for sensitive configuration.
- No hardcoded API credentials.
- Input validation.
- Defensive error handling.
- Secure configuration management.

Important

This manifest documents the intended project structure and features. It does not replace the actual application configuration or implementation.
