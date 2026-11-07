"""Server entrypoint implementing dynamic reverse keepalive routes."""
import asyncio
import logging
import aiohttp
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import config
from database import Database
from engine import Engine
from dashboard import build_router
from telegram_bot import TelegramBot
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

db = Database()
engine = Engine(db)
telegram = TelegramBot(db, engine)
async def keep_alive():
    await asyncio.sleep(20)
    async with aiohttp.ClientSession() as s:
        while True:
            try:
                url = (
                    f"http://127.0.0.1:"
                    f"{config.PORT}/health"
                )
                async with s.get(
                    url, timeout=5
                ) as r:
                    if r.status == 200: 
                        log.info("Pulse ok.")
            except Exception: 
                pass
            await asyncio.sleep(600)
@asynccontextmanager
async def lifespan(app: FastAPI):
    await engine.start()
    await telegram.start()
    pulse = asyncio.create_task(
        keep_alive()
    )
    try: 
        yield
    finally:
        pulse.cancel()
        await telegram.close()
        await engine.stop()
        db.close()
app = FastAPI(
    title=config.APP_NAME, 
    version=config.APP_VERSION, 
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"]
)

app.include_router(
    build_router(db, engine)
)

@app.get("/health")
async def health(): 
    return {
        "status": "ok", 
        "mode": "PAPER_ONLY"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host=config.HOST, 
        port=config.PORT
    )
