import asyncio
import logging
import os

from contextlib import asynccontextmanager
from datetime import datetime, timezone

import gradio as gr
import uvicorn

from fastapi import FastAPI

from config import (
    APP_NAME,
    APP_VERSION,
    HOST,
    PORT,
    PAPER_MODE,
    LOG_LEVEL,
)

from database import Database
from market_data import MarketData
from ai_council import AICouncil
from news_engine import NewsEngine
from paper_trading import PaperTrader
from engine import TradingEngine
from dashboard import create_dashboard
from telegram_bot import TelegramController

from types import SimpleNamespace


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=getattr(
        logging,
        str(LOG_LEVEL).upper(),
        logging.INFO,
    ),
    format=(
        "%(asctime)s | %(levelname)s | "
        "%(name)s | %(message)s"
    ),
)

logger = logging.getLogger(__name__)


# ============================================================
# APPLICATION VALIDATION
# ============================================================

if PAPER_MODE is not True:
    raise RuntimeError(
        "AI QUANT supports PAPER_MODE=True only."
    )

if not isinstance(HOST, str) or not HOST.strip():
    raise ValueError("Invalid HOST configuration.")

if isinstance(PORT, bool) or not isinstance(PORT, int):
    raise ValueError("PORT must be an integer.")

if not 1 <= PORT <= 65535:
    raise ValueError("Invalid PORT range.")


# ============================================================
# SERVICE INSTANCES
# ============================================================

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
    db=db,
)

telegram = TelegramController(
    engine=engine,
    trader=trader,
)

controller = SimpleNamespace(
    db=db,
    market=market,
    ai=ai,
    news=news,
    trader=trader,
    engine=engine,
    telegram=telegram,
)


# ============================================================
# DASHBOARD
# ============================================================

demo = create_dashboard(controller)

if demo is None:
    raise RuntimeError("Dashboard creation failed.")


# ============================================================
# APPLICATION STATE
# ============================================================

scanner_task = None

application_started = False

shutdown_lock = asyncio.Lock()

application_state = {
    "status": "starting",
    "scanner_running": False,
    "telegram_running": False,
    "paper_mode": True,
    "started_at": None,
    "last_error": None,
}


# ============================================================
# TELEGRAM
# ============================================================

async def start_telegram():

    try:

        result = await telegram.start()

        if result is False:

            application_state["telegram_running"] = False

            logger.warning("Telegram bot did not start.")

            return False

        application_state["telegram_running"] = True

        logger.info("Telegram bot started.")

        return True

    except asyncio.CancelledError:
        raise

    except Exception:

        application_state["telegram_running"] = False

        logger.exception("Telegram startup failed.")

        return False


async def stop_telegram():

    try:

        await telegram.close()

    except asyncio.CancelledError:
        raise

    except Exception:

        logger.exception("Telegram shutdown failed.")

    finally:

        application_state["telegram_running"] = False


# ============================================================
# SHUTDOWN
# ============================================================

async def shutdown_application():

    global scanner_task
    global application_started

    async with shutdown_lock:

        if not application_started:
            return

        logger.info("AI QUANT shutdown started.")

        application_state["status"] = "stopping"

        await stop_telegram()

        try:

            await engine.close()

        except asyncio.CancelledError:
            raise

        except Exception:

            logger.exception("Trading engine shutdown failed.")

        task = scanner_task

        if task is not None:

            try:

                await asyncio.wait_for(
                    asyncio.shield(task),
                    timeout=15,
                )

            except asyncio.TimeoutError:

                logger.warning(
                    "Scanner did not stop within 15 seconds."
                )

                task.cancel()

                try:
                    await task
                except asyncio.CancelledError:
                    pass

            except asyncio.CancelledError:
                raise

            except Exception:

                logger.exception(
                    "Scanner task shutdown failed."
                )

        scanner_task = None

        application_state["scanner_running"] = False

        try:

            await db.close()

        except asyncio.CancelledError:
            raise

        except Exception:

            logger.exception("Database shutdown failed.")

        application_state["status"] = "stopped"

        application_started = False

        logger.info("AI QUANT shutdown completed.")


# ============================================================
# APPLICATION LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app):

    global scanner_task
    global application_started

    application_state["status"] = "starting"
    application_state["last_error"] = None

    try:

        if application_started:
            raise RuntimeError("Application is already running.")

        if PAPER_MODE is not True:
            raise RuntimeError("Paper mode is mandatory.")

        started = await engine.start()

        if started is not True:
            raise RuntimeError("Trading engine could not start.")

        scanner_task = asyncio.create_task(
            engine.run_forever(),
            name="ai-quant-scanner",
        )

        application_state["scanner_running"] = True

        await start_telegram()

        application_started = True

        application_state["status"] = "running"

        application_state["started_at"] = (
            datetime.now(timezone.utc).isoformat()
        )

        logger.info(
            "%s %s started in paper mode.",
            APP_NAME,
            APP_VERSION,
        )

        yield

    except asyncio.CancelledError:
        raise

    except Exception as exc:

        application_state["status"] = "error"

        application_state["last_error"] = type(exc).__name__

        logger.exception(
            "Application startup or runtime failed."
        )

        raise

    finally:

        if application_started:

            await shutdown_application()

        else:

            try:
                await engine.close()
            except Exception:
                logger.exception("Startup rollback failed.")

            try:
                await db.close()
            except Exception:
                logger.exception("Database rollback failed.")


# ============================================================
# FASTAPI
# ============================================================

api_app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=(
        "AI-assisted cryptocurrency market analysis "
        "and paper trading system."
    ),
    lifespan=lifespan,
)


# ============================================================
# HEALTH
# ============================================================

@api_app.get("/health")
async def health():

    task_running = (
        scanner_task is not None
        and not scanner_task.done()
    )

    return {
        "application": APP_NAME,
        "version": APP_VERSION,
        "status": application_state["status"],
        "paper_mode": True,
        "scanner_running": task_running,
        "engine_running": engine.running,
        "telegram_running": (
            application_state["telegram_running"]
        ),
    }


# ============================================================
# API STATUS
# ============================================================

@api_app.get("/api/status")
async def api_status():

    def read_status(component):

        method = getattr(
            component,
            "get_status",
            None,
        )

        if not callable(method):
            return {}

        try:

            result = method()

            return result if isinstance(result, dict) else {}

        except Exception:

            logger.exception(
                "Could not read component status."
            )

            return {}

    return {
        "application": APP_NAME,
        "version": APP_VERSION,
        "status": application_state["status"],
        "paper_mode": True,
        "engine": read_status(engine),
        "market": read_status(market),
        "ai": read_status(ai),
        "news": read_status(news),
        "telegram_running": (
            application_state["telegram_running"]
        ),
    }


# ============================================================
# GRADIO DASHBOARD
# ============================================================

# No username or password required.
api_app = gr.mount_gradio_app(
    api_app,
    demo,
    path="/",
)


# ============================================================
# SERVER
# ============================================================

def run():

    if PAPER_MODE is not True:
        raise RuntimeError("Real trading is disabled.")

    logger.info(
        "Starting %s version %s.",
        APP_NAME,
        APP_VERSION,
    )

    uvicorn.run(
        api_app,
        host=HOST,
        port=PORT,
        log_level=str(LOG_LEVEL).lower(),
        access_log=False,
        timeout_keep_alive=10,
    )


if __name__ == "__main__":
    run()
