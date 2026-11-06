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


# --------------------------------------------------
# LOGGING
# --------------------------------------------------

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
shutdown_started = False


# --------------------------------------------------
# SHUTDOWN HELPERS
# --------------------------------------------------

async def stop_scanner():

    global scanner_task

    task = scanner_task

    if task is None:
        return

    scanner_task = None

    if not task.done():

        task.cancel()

    try:

        await task

    except asyncio.CancelledError:

        logger.info(
            "Scanner task cancelled successfully"
        )

    except Exception:

        logger.exception(
            "Scanner task terminated with an error"
        )


async def shutdown_components():

    global shutdown_started

    if shutdown_started:
        return

    shutdown_started = True

    logger.info(
        "Application shutdown started"
    )

    # Stop new scans before cancelling the background task.
    engine.running = False

    await stop_scanner()

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
# APPLICATION LIFECYCLE
# --------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):

    global scanner_task
    global shutdown_started

    shutdown_started = False

    logger.info(
        "Starting %s version %s",
        APP_NAME,
        APP_VERSION
    )

    try:

        # Start market data, AI and news components.
        await engine.start()

        # Start the continuous market scanner.
        scanner_task = asyncio.create_task(
            engine.run_forever(),
            name="AI_QUANT_SCANNER"
        )

        # Telegram is optional.
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

        await shutdown_components()


# --------------------------------------------------
# FASTAPI
# --------------------------------------------------

api_app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    lifespan=lifespan
)


@api_app.get("/health")
async def health():

    scanner_active = (
        scanner_task is not None
        and not scanner_task.done()
    )

    engine_running = bool(
        getattr(engine, "running", False)
    )

    healthy = (
        engine_running
        and scanner_active
    )

    return {
        "status": (
            "ok"
            if healthy
            else "degraded"
        ),
        "application": APP_NAME,
        "version": APP_VERSION,
        "running": engine_running,
        "scanner_active": scanner_active,
        "paper_trading_only": True
    }


@api_app.get("/api/status")
async def api_status():

    summary = trader.get_summary() or {}

    positions = summary.get(
        "positions",
        []
    ) or []

    return {
        "application": APP_NAME,
        "version": APP_VERSION,
        "mode": "PAPER",

        "balance": summary.get(
            "balance",
            0
        ),

        "equity": summary.get(
            "equity",
            0
        ),

        "realized_pnl": summary.get(
            "realized_pnl",
            0
        ),

        "unrealized_pnl": summary.get(
            "unrealized_pnl",
            0
        ),

        "reserved": summary.get(
            "reserved",
            0
        ),

        "open_positions": len(positions),

        "win_rate": summary.get(
            "win_rate",
            0
        ),

        "market_regime": getattr(
            engine,
            "market_regime",
            "UNKNOWN"
        ),

        "last_scan": getattr(
            engine,
            "last_scan",
            None
        ),

        "scan_stats": getattr(
            engine,
            "scan_stats",
            {}
        )
    }


# --------------------------------------------------
# GRADIO DASHBOARD
# --------------------------------------------------

demo = create_dashboard(
    controller
)

app = gr.mount_gradio_app(
    api_app,
    demo,
    path="/"
)


# --------------------------------------------------
# SERVER
# --------------------------------------------------

def get_server_port():

    raw_port = os.getenv(
        "PORT",
        str(DEFAULT_PORT)
    )

    try:

        port = int(raw_port)

    except (TypeError, ValueError):

        raise ValueError(
            "PORT must be a valid integer"
        )

    if not 1 <= port <= 65535:

        raise ValueError(
            "PORT must be between 1 and 65535"
        )

    return port


if __name__ == "__main__":

    try:

        port = get_server_port()

        uvicorn.run(
            app,
            host=HOST,
            port=port,
            log_level="info",
            access_log=True
        )

    except KeyboardInterrupt:

        logger.info(
            "Application interrupted by user"
        )

    except Exception:

        logger.exception(
            "Application startup failed"
        )

        raise
