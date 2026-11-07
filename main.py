"""AI QUANT 4.0 - Application entry point.
Paper simulation only. No real exchange orders.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from config import APP_NAME, APP_VERSION, HOST, PORT
from database import Database
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
# Application lifecycle
# --------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):

    db = None
    engine = None

    logger.info(
        "Starting %s version %s",
        APP_NAME,
        APP_VERSION,
    )

    try:
        # Initialize persistent database.
        db = Database()

        # Engine requires the database instance.
        engine = Engine(db)

        app.state.db = db
        app.state.engine = engine

        # Start market, AI and news services.
        await engine.start()

        logger.info("AI QUANT started successfully.")

        yield

    except Exception:
        logger.exception("Application startup/runtime failure.")
        raise

    finally:
        logger.info("Shutting down AI QUANT.")

        if engine is not None:
            try:
                await engine.stop()
            except Exception:
                logger.exception("Engine shutdown failed.")

        if db is not None:
            try:
                db.close()
            except Exception:
                logger.exception("Database shutdown failed.")

        app.state.engine = None
        app.state.db = None

        logger.info("AI QUANT stopped.")


# --------------------------------------------------
# FastAPI application
# --------------------------------------------------

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=(
        "Advanced cryptocurrency market analysis "
        "and paper portfolio simulation."
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
# Application dependencies
# --------------------------------------------------

def get_engine(request: Request):

    engine = getattr(
        request.app.state,
        "engine",
        None
    )

    if engine is None:
        raise RuntimeError("Engine unavailable")

    return engine


def get_database(request: Request):

    db = getattr(
        request.app.state,
        "db",
        None
    )

    if db is None:
        raise RuntimeError("Database unavailable")

    return db


# --------------------------------------------------
# Health check - Render
# --------------------------------------------------

@app.get("/health")
async def health(request: Request):

    engine = getattr(
        request.app.state,
        "engine",
        None
    )

    db = getattr(
        request.app.state,
        "db",
        None
    )

    if engine is None or db is None:
        return JSONResponse(
            status_code=503,
            content={"status": "starting"},
        )

    return {
        "status": "healthy",
        "application": APP_NAME,
        "version": APP_VERSION,
        "mode": "PAPER_TRADING",
        "database": "connected",
        "engine_running": engine.running,
    }


@app.get("/api/health")
async def api_health(request: Request):
    return await health(request)


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
        "dashboard": "/ui/",
        "health": "/health",
    }


# --------------------------------------------------
# Portfolio status
# --------------------------------------------------

@app.get("/status")
@app.get("/dashboard/status")
async def dashboard_status(request: Request):

    try:
        engine = get_engine(request)

        db = get_database(request)

        account = db.account()

        prices = engine.last_prices

        equity = engine.paper.equity(prices)

        exposure = engine.paper.exposure(prices)

        return {
            "application": APP_NAME,
            "version": APP_VERSION,
            "mode": "PAPER_TRADING",

            "cash": account["cash"],
            "realized_pnl": account["realized_pnl"],

            "equity": equity,
            "exposure": exposure,

            "risk_fraction": 0.10,
            "risk_budget": engine.paper.risk_budget(prices),

            "open_positions": len(db.positions()),

            "last_scan": engine.last_scan,
            "last_error": engine.last_error,

            "prices": prices,
        }

    except Exception as exc:

        logger.exception("Portfolio status failed.")

        return JSONResponse(
            status_code=503,
            content={"error": str(exc)},
        )


# --------------------------------------------------
# Open positions
# --------------------------------------------------

@app.get("/dashboard/positions")
async def dashboard_positions(request: Request):

    try:
        db = get_database(request)

        return db.get_positions()

    except Exception as exc:

        logger.exception("Positions endpoint failed.")

        return JSONResponse(
            status_code=503,
            content={"error": str(exc)},
        )


# --------------------------------------------------
# Recent trades
# --------------------------------------------------

@app.get("/dashboard/trades")
async def dashboard_trades(request: Request):

    try:
        db = get_database(request)

        return db.get_trades(100)

    except Exception as exc:

        logger.exception("Trades endpoint failed.")

        return JSONResponse(
            status_code=503,
            content={"error": str(exc)},
        )


# --------------------------------------------------
# AI decisions
# --------------------------------------------------

@app.get("/dashboard/decisions")
async def dashboard_decisions(request: Request):

    try:
        db = get_database(request)

        return db.get_decisions(100)

    except Exception as exc:

        logger.exception("Decisions endpoint failed.")

        return JSONResponse(
            status_code=503,
            content={"error": str(exc)},
        )


# --------------------------------------------------
# System status
# --------------------------------------------------

@app.get("/system/status")
async def system_status(request: Request):

    try:
        engine = get_engine(request)

        return {
            "running": engine.running,
            "last_scan": engine.last_scan,
            "last_error": engine.last_error,
            "last_prices": engine.last_prices,
        }

    except Exception as exc:

        return JSONResponse(
            status_code=503,
            content={"error": str(exc)},
        )


# --------------------------------------------------
# Gradio dashboard
# --------------------------------------------------

try:

    import gradio as gr

    from dashboard import build_dashboard

    app = gr.mount_gradio_app(
        app,
        build_dashboard(),
        path="/ui",
    )

    logger.info("Gradio dashboard mounted at /ui")

except ImportError:

    logger.warning(
        "Gradio unavailable. API remains operational."
    )


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
            "info"
        ).lower(),
    )
