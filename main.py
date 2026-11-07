import logging, os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import gradio as gr
import uvicorn
from config import HOST,PORT,DB_PATH
from database import Database
from engine import TradingEngine
from api import build_router
from telegram_bot import TelegramBot
from dashboard import build_dashboard

logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"),format="%(asctime)s %(levelname)s %(name)s: %(message)s")
db=Database(DB_PATH); engine=TradingEngine(db); telegram=TelegramBot(db)

@asynccontextmanager
async def lifespan(app):
    try:
        await engine.start()
        try: await telegram.start()
        except Exception: logging.exception("Telegram startup failed; continuing without Telegram")
        yield
    finally:
        await telegram.close(); await engine.stop(); db.close()

app=FastAPI(title="AI QUANT 4.0",version="4.0.0",lifespan=lifespan)
allowed=[x.strip() for x in os.getenv("CORS_ORIGINS","").split(",") if x.strip()]
if allowed: app.add_middleware(CORSMiddleware,allow_origins=allowed,allow_credentials=False,allow_methods=["GET","POST"],allow_headers=["*"])
app.include_router(build_router(db,engine))
app = gr.mount_gradio_app(app, build_dashboard(), path="/dashboard")

if __name__=="__main__": uvicorn.run(app,host=HOST,port=PORT,log_level="info")
