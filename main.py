import os
import asyncio
import logging
import gradio as gr

from fastapi import FastAPI

from database import Database
from market_data import MarketData
from ai_council import AICouncil
from news_engine import NewsEngine
from paper_trading import PaperTrader
from engine import TradingEngine
from dashboard import create_dashboard
from telegram_bot import TelegramController


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("AI_QUANT")


db = Database()

market = MarketData()
ai = AICouncil()
news = NewsEngine()

trader = PaperTrader(db)

controller = TradingEngine(
    market_data=market,
    ai_council=ai,
    news_engine=news,
    trader=trader,
    database=db
)

telegram = TelegramController(controller)

app = FastAPI(title="AI QUANT")

dashboard = create_dashboard(controller)

app = gr.mount_gradio_app(
    app,
    dashboard,
    path="/"
)


@app.on_event("startup")
async def startup_event():
    logger.info("Starting AI QUANT")

    try:
        await controller.start()

        try:
            await telegram.start()
        except Exception as exc:
            logger.error(
                "Telegram startup failed: %s",
                exc
            )

        app.state.scanner_task = asyncio.create_task(
            controller.run_forever()
        )

        logger.info("AI QUANT started")

    except Exception as exc:
        logger.exception(
            "Startup failed: %s",
            exc
        )


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Stopping AI QUANT")

    controller.stop()

    task = getattr(
        app.state,
        "scanner_task",
        None
    )

    if task:
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

    await telegram.stop()
    await controller.close()

    db.close()

    logger.info("AI QUANT stopped")


@app.get("/health")
async def health():
    return {
        "status": "online",
        "system": "AI QUANT",
        "mode": "PAPER_TRADING_ONLY"
    }


if __name__ == "__main__":
    import uvicorn

    port = int(
        os.getenv("PORT", "7860")
    )

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port
    )
