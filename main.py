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
# CONFIGURATION VALIDATION
# ============================================================

if PAPER_MODE is not True:

    raise RuntimeError(
        "AI QUANT must run in PAPER_MODE=True"
    )


if not isinstance(HOST, str) or not HOST.strip():

    raise ValueError(
        "HOST must be a non-empty string"
    )


def get_server_port():

    if (
        isinstance(PORT, bool)
        or not isinstance(PORT, int)
        or not 1 <= PORT <= 65535
    ):

        raise ValueError(
            "PORT must be an integer between 1 and 65535"
        )

    return PORT


SERVER_PORT = get_server_port()


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

application_started_once = False


# ============================================================
# SAFE HELPERS
# ============================================================

def safe_count(value):

    if isinstance(value, bool):
        return 0

    try:

        result = int(value)

        return max(0, result)

    except (TypeError, ValueError, OverflowError):

        return 0


def safe_status_text(value, default="UNKNOWN"):

    if value is None:
        return default

    try:

        result = str(value).strip()

        return result[:200] if result else default

    except Exception:

        return default


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

    # Prevent new scans.

    engine.running = False

    # Stop background scanner.

    try:

        await stop_scanner()

    except Exception:

        logger.exception(
            "Scanner shutdown failed"
        )

    # Stop Telegram.

    try:

        await telegram.close()

    except Exception:

        logger.exception(
            "Telegram shutdown failed"
        )

    # Close engine dependencies.

    try:

        await engine.close()

    except Exception:

        logger.exception(
            "Engine shutdown failed"
        )

    # Close database last.

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
    global application_started_once

    if application_started_once:

        raise RuntimeError(
            "This AI QUANT application instance "
            "cannot be restarted after shutdown."
        )

    application_started_once = True

    shutdown_started = False

    logger.info(
        "Starting %s version %s",
        APP_NAME,
        APP_VERSION,
    )

    try:

        # Start market, AI and news services.

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
                "Telegram startup sequence completed"
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
        getattr(
            engine,
            "running",
            False,
        )
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

    """
    Public-safe status endpoint.

    Financial account details and open position data
    are intentionally not exposed without authentication.
    """

    try:

        stats = getattr(
            engine,
            "scan_stats",
            {},
        )

        if not isinstance(stats, dict):
            stats = {}

        task = scanner_task

        scanner_active = (
            task is not None
            and not task.done()
        )

        return {
            "application": APP_NAME,
            "version": APP_VERSION,
            "mode": "PAPER",

            "engine_running": bool(
                getattr(
                    engine,
                    "running",
                    False,
                )
            ),

            "scanner_active": scanner_active,

            "market_regime": safe_status_text(
                getattr(
                    engine,
                    "market_regime",
                    "UNKNOWN",
                )
            ),

            "last_scan": getattr(
                engine,
                "last_scan",
                None,
            ),

            "last_error": safe_status_text(
                getattr(
                    engine,
                    "last_error",
                    None,
                ),
                default="",
            ),

            "scan_stats": {
                "scanned": safe_count(
                    stats.get("scanned")
                ),
                "approved": safe_count(
                    stats.get("approved")
                ),
                "rejected": safe_count(
                    stats.get("rejected")
                ),
                "errors": safe_count(
                    stats.get("errors")
                ),
            },

            "paper_trading_only": True,
        }

    except Exception:

        logger.exception(
            "API status endpoint failed"
        )

        return {
            "application": APP_NAME,
            "version": APP_VERSION,
            "mode": "PAPER",
            "status": "temporarily_unavailable",
            "paper_trading_only": True,
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
# MAIN
# ============================================================

if __name__ == "__main__":

    try:

        logger.info(
            "Starting %s on %s:%s",
            APP_NAME,
            HOST,
            SERVER_PORT,
        )

        uvicorn.run(
            app,
            host=HOST,
            port=SERVER_PORT,
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
