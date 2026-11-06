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
    PORT,
    APP_NAME,
    APP_VERSION,
    PAPER_MODE,
)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "%(message)s"
    ),
)

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

if PAPER_MODE is not True:
    raise RuntimeError(
        "AI QUANT must run in PAPER_MODE=True"
    )

if isinstance(PORT, bool) or not isinstance(PORT, int):
    raise ValueError(
        "PORT must be an integer"
    )

if not 1 <= PORT <= 65535:
    raise ValueError(
        "PORT must be between 1 and 65535"
    )


# ============================================================
# CORE COMPONENTS
# ============================================================

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
    db,
)

telegram = TelegramController(
    engine,
    trader,
)

controller = SimpleNamespace(
    engine=engine,
    trader=trader,
    db=db,
)


# ============================================================
# APPLICATION STATE
# ============================================================

scanner_task = None

shutdown_started = False


# ============================================================
# SCANNER SHUTDOWN
# ============================================================

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


# ============================================================
# APPLICATION SHUTDOWN
# ============================================================

async def shutdown_components():

    global shutdown_started

    if shutdown_started:
        return

    shutdown_started = True

    logger.info(
        "Application shutdown started"
    )

    # Prevent new background scans.

    engine.running = False

    # Stop the scanner before closing its dependencies.

    await stop_scanner()

    # Stop Telegram.

    try:

        await telegram.close()

    except Exception:

        logger.exception(
            "Telegram shutdown failed"
        )

    # Close market, AI and news components.

    try:

        await engine.close()

    except Exception:

        logger.exception(
            "Engine shutdown failed"
        )

    # Close the database last.

    try:

        db.close()

    except Exception:

        logger.exception(
            "Database shutdown failed"
        )

    logger.info(
        "Application shutdown completed"
    )


# ============================================================
# APPLICATION LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    global scanner_task
    global shutdown_started

    shutdown_started = False

    logger.info(
        "Starting %s version %s",
        APP_NAME,
        APP_VERSION,
    )

    try:

        # Start market data, AI and news.

        await engine.start()

        # Start background scanner.

        scanner_task = asyncio.create_task(
            engine.run_forever(),
            name="AI_QUANT_SCANNER",
        )

        # Telegram is optional.

        try:

            await telegram.start()

            logger.info(
                "Telegram controller started"
            )

        except Exception:

            logger.exception(
                "Telegram startup failed; application will continue"
            )

        logger.info(
            "Application startup completed"
        )

        yield

    except BaseException:

        logger.exception(
            "Application lifecycle interrupted"
        )

        raise

    finally:

        await shutdown_components()


# ============================================================
# FASTAPI APPLICATION
# ============================================================

api_app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    lifespan=lifespan,
)


# ============================================================
# HEALTH ENDPOINT
# ============================================================

@api_app.get("/health")
async def health():

    task = scanner_task

    scanner_active = (
        task is not None
        and not task.done()
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
        "paper_trading_only": True,
    }


# ============================================================
# STATUS ENDPOINT
# ============================================================

@api_app.get("/api/status")
async def api_status():

    summary = trader.get_summary() or {}

    positions = summary.get(
        "positions",
        [],
    ) or []

    return {
        "application": APP_NAME,
        "version": APP_VERSION,
        "mode": "PAPER",

        "balance": summary.get(
            "balance",
            0,
        ),

        "equity": summary.get(
            "equity",
            0,
        ),

        "realized_pnl": summary.get(
            "realized_pnl",
            0,
        ),

        "unrealized_pnl": summary.get(
            "unrealized_pnl",
            0,
        ),

        "reserved": summary.get(
            "reserved",
            0,
        ),

        "open_positions": len(positions),

        "win_rate": summary.get(
            "win_rate",
            0,
        ),

        "market_regime": getattr(
            engine,
            "market_regime",
            "UNKNOWN",
        ),

        "last_scan": getattr(
            engine,
            "last_scan",
            None,
        ),

        "last_error": getattr(
            engine,
            "last_error",
            None,
        ),

        "scan_stats": getattr(
            engine,
            "scan_stats",
            {},
        ),
    }


# ============================================================
# GRADIO DASHBOARD
# ============================================================

demo = create_dashboard(
    controller
)

app = gr.mount_gradio_app(
    api_app,
    demo,
    path="/",
)


# ============================================================
# SERVER
# ============================================================

def get_server_port():

    if (
        isinstance(PORT, bool)
        or not isinstance(PORT, int)
        or not 1 <= PORT <= 65535
    ):

        raise ValueError(
            "Invalid PORT configuration"
        )

    return PORT


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    try:

        server_port = get_server_port()

        logger.info(
            "Starting %s on %s:%s",
            APP_NAME,
            HOST,
            server_port,
        )

        uvicorn.run(
            app,
            host=HOST,
            port=server_port,
            log_level="info",
            access_log=True,
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
