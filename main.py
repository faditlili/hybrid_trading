import os
import asyncio
import logging

from contextlib import asynccontextmanager
from types import SimpleNamespace

import gradio as gr
import uvicorn

from fastapi import FastAPI

from database import Database
from market_data import MarketData
from ai_council import AICouncil
from news_engine import NewsEngine
from paper_trading import PaperTrader
from engine import TradingEngine
from dashboard import create_dashboard
from telegram_bot import TelegramController

from config import (
    HOST,
    DEFAULT_PORT,
    APP_NAME,
    APP_VERSION
)


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "%(message)s"
    )
)

logger = logging.getLogger(__name__)


# --------------------------------------------------
# CORE COMPONENTS
# --------------------------------------------------

db = Database()

market = MarketData()

ai = AICouncil()

news = NewsEngine()

trader = PaperTrader(db)

engine = TradingEngine(
    market,
    ai,
    news,
    trader,
    db
)

telegram = TelegramController(
    engine,
    trader
)

controller = SimpleNamespace(
    engine=engine,
    trader=trader,
    db=db
)


scanner_task = None


# --------------------------------------------------
# APPLICATION LIFECYCLE
# --------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):

    global scanner_task

    logger.info(
        "Starting %s version %s",
        APP_NAME,
        APP_VERSION
    )

    try:

        await engine.start()

        scanner_task = asyncio.create_task(
            engine.run_forever(),
            name="AI_QUANT_SCANNER"
        )

        try:

            await telegram.start()

        except Exception:

            logger.exception(
                "Telegram startup failed"
            )

        logger.info(
            "Application startup completed"
        )

        yield

    finally:

        logger.info(
            "Application shutdown started"
        )

        engine.running = False

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

        logger.info(
            "Application shutdown completed"
        )


# --------------------------------------------------
# FASTAPI
# --------------------------------------------------

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    lifespan=lifespan
)


@app.get("/health")
async def health():

    return {
        "status": "ok",
        "application": APP_NAME,
        "version": APP_VERSION,
        "running": engine.running,
        "paper_trading_only": True,
        "market_regime": engine.market_regime,
        "last_scan": engine.last_scan,
        "last_error": engine.last_error,
        "scanner_active": (
            scanner_task is not None
            and not scanner_task.done()
        )
    }


@app.get("/api/status")
async def api_status():

    summary = trader.get_summary()

    return {
        "application": APP_NAME,
        "version": APP_VERSION,
        "mode": "PAPER",
        "balance": summary["balance"],
        "equity": summary["equity"],
        "realized_pnl": summary["realized_pnl"],
        "unrealized_pnl": summary["unrealized_pnl"],
        "reserved": summary["reserved"],
        "open_positions": len(
            summary["positions"]
        ),
        "win_rate": summary["win_rate"],
        "market_regime": engine.market_regime,
        "last_scan": engine.last_scan,
        "scan_stats": engine.scan_stats
    }


# --------------------------------------------------
# GRADIO DASHBOARD
# --------------------------------------------------

demo = create_dashboard(
    controller
)

app = gr.mount_gradio_app(
    app,
    demo,
    path="/"
)


# --------------------------------------------------
# SERVER
# --------------------------------------------------

if __name__ == "__main__":

    port = int(
        os.getenv(
            "PORT",
            DEFAULT_PORT
        )
    )

    uvicorn.run(
        app,
        host=HOST,
        port=port,
        log_level="info",
        access_log=True
    )
