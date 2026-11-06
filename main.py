import asyncio
import inspect
import logging
import os

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

SERVER_HOST = HOST.strip()


def get_server_port():

    if (
        isinstance(PORT, bool)
        or not isinstance(PORT, int)
        or not 1 <= PORT <= 65535
    ):
        raise ValueError(
            "PORT must be between 1 and 65535"
        )

    return PORT


SERVER_PORT = get_server_port()


# ============================================================
# DASHBOARD AUTHENTICATION
# ============================================================

def get_dashboard_auth():

    username = os.getenv(
        "DASHBOARD_USERNAME",
        ""
    ).strip()

    password = os.getenv(
        "DASHBOARD_PASSWORD",
        ""
    )

    if not username or not password:

        raise RuntimeError(
            "Dashboard authentication is required. "
            "Set DASHBOARD_USERNAME and DASHBOARD_PASSWORD."
        )

    if len(username) > 100:

        raise ValueError(
            "DASHBOARD_USERNAME is too long"
        )

    if len(password) < 16:

        raise ValueError(
            "DASHBOARD_PASSWORD must contain "
            "at least 16 characters"
        )

    if len(password) > 256:

        raise ValueError(
            "DASHBOARD_PASSWORD is too long"
        )

    return username, password


DASHBOARD_AUTH = get_dashboard_auth()


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

startup_completed = False

application_state = "CREATED"


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


def safe_status_text(
    value,
    default="UNKNOWN",
    limit=200,
):

    if value is None:
        return default

    try:

        result = str(value).strip()

        return result[:limit] if result else default

    except Exception:

        return default


def scanner_is_active():

    task = scanner_task

    return (
        task is not None
        and not task.done()
        and not task.cancelled()
    )


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
            "Scanner task stopped"
        )

    except Exception:

        logger.exception(
            "Scanner task failed during shutdown"
        )


# ============================================================
# SAFE COMPONENT SHUTDOWN
# ============================================================

async def shutdown_component(
    name,
    close_function,
):

    try:

        result = close_function()

        if inspect.isawaitable(result):
            await result

        logger.info(
            "%s shutdown completed",
            name,
        )

    except asyncio.CancelledError:

        logger.warning(
            "%s shutdown was cancelled",
            name,
        )

    except Exception:

        logger.exception(
            "%s shutdown failed",
            name,
        )


# ============================================================
# APPLICATION SHUTDOWN
# ============================================================

async def shutdown_components():

    global shutdown_started
    global application_state

    if shutdown_started:
        return

    shutdown_started = True

    application_state = "STOPPING"

    logger.info(
        "Application shutdown started"
    )

    # --------------------------------------------------------
    # STOP NEW SCANS
    # --------------------------------------------------------

    try:

        engine.running = False

    except Exception:

        logger.exception(
            "Could not stop engine"
        )

    # --------------------------------------------------------
    # STOP SCANNER
    # --------------------------------------------------------

    await shutdown_component(
        "Scanner",
        stop_scanner,
    )

    # --------------------------------------------------------
    # STOP TELEGRAM
    # --------------------------------------------------------

    await shutdown_component(
        "Telegram",
        telegram.close,
    )

    # --------------------------------------------------------
    # CLOSE ENGINE AND DEPENDENCIES
    # --------------------------------------------------------

    await shutdown_component(
        "Trading engine",
        engine.close,
    )

    # --------------------------------------------------------
    # CLOSE DATABASE LAST
    # --------------------------------------------------------

    await shutdown_component(
        "Database",
        db.close,
    )

    application_state = "STOPPED"

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
    global startup_completed
    global application_state

    shutdown_started = False
    startup_completed = False
    scanner_task = None

    application_state = "STARTING"

    logger.info(
        "Starting %s version %s",
        APP_NAME,
        APP_VERSION,
    )

    try:

        # ----------------------------------------------------
        # START ENGINE AND DEPENDENCIES
        # ----------------------------------------------------

        await engine.start()

        if not getattr(engine, "running", False):

            raise RuntimeError(
                "Trading engine did not start"
            )

        # ----------------------------------------------------
        # START BACKGROUND SCANNER
        # ----------------------------------------------------

        scanner_task = asyncio.create_task(
            engine.run_forever(),
            name="AI_QUANT_SCANNER",
        )

        # ----------------------------------------------------
        # START TELEGRAM (OPTIONAL)
        # ----------------------------------------------------

        try:

            await telegram.start()

            logger.info(
                "Telegram startup completed"
            )

        except asyncio.CancelledError:

            raise

        except Exception:

            logger.exception(
                "Telegram startup failed; "
                "continuing without Telegram"
            )

        # ----------------------------------------------------
        # STARTUP COMPLETE
        # ----------------------------------------------------

        startup_completed = True

        application_state = "RUNNING"

        logger.info(
            "Application startup completed"
        )

        yield

    except asyncio.CancelledError:

        application_state = "FAILED"

        logger.warning(
            "Application startup or lifespan cancelled"
        )

        raise

    except Exception:

        application_state = "FAILED"

        logger.exception(
            "Application lifecycle failed"
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

    engine_running = bool(
        getattr(
            engine,
            "running",
            False,
        )
    )

    scanner_active = scanner_is_active()

    healthy = (
        application_state == "RUNNING"
        and startup_completed
        and engine_running
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

        "application_state": application_state,

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

    Account balances, equity and open positions
    are intentionally not exposed.
    """

    try:

        stats = getattr(
            engine,
            "scan_stats",
            {},
        )

        if not isinstance(stats, dict):
            stats = {}

        engine_running = bool(
            getattr(
                engine,
                "running",
                False,
            )
        )

        scanner_active = scanner_is_active()

        last_scan = safe_status_text(
            getattr(
                engine,
                "last_scan",
                None,
            ),
            default="",
        )

        last_error = getattr(
            engine,
            "last_error",
            None,
        )

        return {

            "application": APP_NAME,

            "version": APP_VERSION,

            "mode": "PAPER",

            "application_state": application_state,

            "engine_running": engine_running,

            "scanner_active": scanner_active,

            "market_regime": safe_status_text(
                getattr(
                    engine,
                    "market_regime",
                    "UNKNOWN",
                )
            ),

            "last_scan": last_scan,

            "has_error": bool(last_error),

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
    auth=DASHBOARD_AUTH,
)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    try:

        logger.info(
            "Starting %s on %s:%s",
            APP_NAME,
            SERVER_HOST,
            SERVER_PORT,
        )

        uvicorn.run(
            app,
            host=SERVER_HOST,
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
