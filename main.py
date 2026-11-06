import os
import asyncio
import logging

import uvicorn
import gradio as gr

from contextlib import asynccontextmanager
from types import SimpleNamespace
from fastapi import FastAPI

from database import Database
from market_data import MarketData
from ai_council import AICouncil
from news_engine import NewsEngine
from paper_trading import PaperTrader
from engine import TradingEngine
from dashboard import build_dashboard
from telegram_bot import TelegramController


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger("AI_QUANT")


# إنشاء الخدمات
db = Database()

market = MarketData()
ai = AICouncil()
news = NewsEngine()

trader = PaperTrader(db)

engine = TradingEngine(
    market=market,
    ai=ai,
    news=news,
    trader=trader,
    db=db
)

telegram = TelegramController(
    engine=engine,
    trader=trader
)

# واجهة موحدة للوحة التحكم
controller = SimpleNamespace(
    engine=engine,
    trader=trader,
    db=db
)

scanner_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):

    global scanner_task

    logger.info("Starting AI QUANT")

    try:

        await engine.start()

        scanner_task = asyncio.create_task(
            engine.run_forever(),
            name="ai-quant-scanner"
        )

        try:
            await telegram.start()

        except Exception:
            logger.exception(
                "Telegram startup failed; dashboard remains available"
            )

        logger.info("AI QUANT started successfully")

        yield

    finally:

        logger.info("Stopping AI QUANT")

        engine.stop()

        if scanner_task:

            scanner_task.cancel()

            try:
                await scanner_task

            except asyncio.CancelledError:
                pass

            except Exception:
                logger.exception(
                    "Scanner shutdown failed"
                )

            scanner_task = None

        try:
            await telegram.close()

        except Exception:
            logger.exception(
                "Telegram shutdown failed"
            )

        try:
            await engine.close()

        except Exception:
            logger.exception(
                "Engine shutdown failed"
            )

        try:
            db.close()

        except Exception:
            logger.exception(
                "Database shutdown failed"
            )

        logger.info("AI QUANT stopped")


app = FastAPI(
    title="AI QUANT",
    description="Automated paper-trading simulation",
    version="2.0",
    lifespan=lifespan
)


@app.get("/health")
async def health():

    scanner_running = (
        scanner_task is not None
        and not scanner_task.done()
    )

    return {
        "system": "AI QUANT",
        "status": (
            "ONLINE"
            if scanner_running
            else "DEGRADED"
        ),
        "paper_trading_only": True,
        "scanner_running": scanner_running,
        "market_regime": engine.market_regime,
        "last_scan": engine.last_scan,
        "last_error": engine.last_error
    }


@app.get("/api/status")
async def api_status():

    summary = trader.get_summary()

    return {
        "mode": "PAPER ONLY",
        "balance": summary["balance"],
        "equity": summary["equity"],
        "realized_pnl": summary["realized_pnl"],
        "unrealized_pnl": summary["unrealized_pnl"],
        "open_positions": len(summary["positions"]),
        "market_regime": engine.market_regime,
        "last_scan": engine.last_scan
    }


# إنشاء واجهة Gradio
demo = build_dashboard(controller)

app = gr.mount_gradio_app(
    app,
    demo,
    path="/"
)


if __name__ == "__main__":

    port = int(
        os.environ.get("PORT", 7860)
    )

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
