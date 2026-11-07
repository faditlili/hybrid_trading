
"""AI QUANT 4.0 - Application entry point.
Paper trading only. No real exchange orders.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from config import (
    APP_NAME,
    APP_VERSION,
    HOST,
    PORT,
)

from engine import Engine

# --------------------------------------------------
# Logging
# --------------------------------------------------

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("AI_QUANT")

# --------------------------------------------------
# Application state
# --------------------------------------------------

engine = Engine()
engine_task = None
shutdown_event = asyncio.Event()


# --------------------------------------------------
# Background engine
# --------------------------------------------------

async def run_engine():
    """Run the trading analysis engine safely."""

    logger.info("AI QUANT engine started.")

    while not shutdown_event.is_set():
        try:
            await engine.start()

            # Engine.start() should initialize the engine
            # and return without blocking indefinitely.
            break

        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception("Engine startup failed.")

        try:
            await asyncio.wait_for(
                shutdown_event.wait(),
                timeout=15,
            )
        except asyncio.TimeoutError:
            continue

    logger.info("Engine background task stopped.")


# --------------------------------------------------
# Keep alive
# --------------------------------------------------

async def keep_alive():
    """Internal health pulse for Render."""

    import aiohttp

    await asyncio.sleep(20)

    timeout = aiohttp.ClientTimeout(total=10)

    while not shutdown_event.is_set():
        try:
            async with aiohttp.ClientSession(
                timeout=timeout
            ) as session:

                async with session.get(
                    f"http://127.0.0.1:{PORT}/health"
                ) as response:

                    if response.status == 200:
                        logger.debug("Health pulse OK.")
                    else:
                        logger.warning(
                            "Health pulse status: %s",
                            response.status,
                        )

        except Exception:
            logger.warning(
                "Health pulse unavailable.",
                exc_info=True,
            )

        try:
            await asyncio.wait_for(
                shutdown_event.wait(),
                timeout=600,
            )
        except asyncio.TimeoutError:
            pass


# --------------------------------------------------
# Lifespan
# --------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):

    global engine_task

    shutdown_event.clear()

    logger.info(
        "Starting %s version %s",
        APP_NAME,
        APP_VERSION,
    )

    engine_task = asyncio.create_task(
        run_engine(),
        name="ai-quant-engine",
    )

    keep_alive_task = asyncio.create_task(
        keep_alive(),
        name="ai-quant-keep-alive",
    )

    try:
        yield

    finally:
        logger.info("Shutting down AI QUANT.")

        shutdown_event.set()

        tasks = [
            task
            for task in (
                engine_task,
                keep_alive_task,
            )
            if task is not None
        ]

        for task in tasks:
            task.cancel()

        await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )

        try:
            await engine.stop()
        except Exception:
            logger.exception("Engine shutdown error.")

        logger.info("AI QUANT stopped.")


# --------------------------------------------------
# FastAPI
# --------------------------------------------------

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=(
        "Advanced AI cryptocurrency analysis "
        "and paper trading system using BingX market data."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


# --------------------------------------------------
# Health check - Render
# --------------------------------------------------

@app.get("/health")
async def health():

    return {
        "status": "healthy",
        "application": APP_NAME,
        "version": APP_VERSION,
        "mode": "PAPER_TRADING",
        "exchange": "BingX",
    }


# --------------------------------------------------
# Root
# --------------------------------------------------

@app.get("/")
async def root():

    return {
        "application": APP_NAME,
        "version": APP_VERSION,
        "status": "running",
        "mode": "PAPER_TRADING",
        "exchange": "BingX",
        "health": "/health",
    }


# --------------------------------------------------
# System status
# --------------------------------------------------

@app.get("/status")
async def system_status():

    try:
        status = await engine.get_status()

        return {
            "application": APP_NAME,
            "version": APP_VERSION,
            "mode": "PAPER_TRADING",
            "engine": status,
        }

    except Exception:
        logger.exception("Could not retrieve engine status.")

        return JSONResponse(
            status_code=503,
            content={
                "status": "temporarily_unavailable",
            },
        )


# --------------------------------------------------
# Dashboard compatibility
# --------------------------------------------------

@app.get("/api/health")
async def api_health():
    return await health()


# --------------------------------------------------
# Local execution
# --------------------------------------------------

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=False,
        workers=1,
        log_level=os.getenv(
            "LOG_LEVEL",
            "info",
        ).lower(),
    )
