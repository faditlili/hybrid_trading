"""Optional Telegram status notifications; admin-only commands."""
import logging
try:
    from telegram import Update
    from telegram.ext import Application,CommandHandler,ContextTypes
except ImportError:  # Telegram is optional when no bot token is configured.
    class _ContextTypes:
        DEFAULT_TYPE = object
    Update = object
    ContextTypes = _ContextTypes
    Application = CommandHandler = None
from config import TELEGRAM_TOKEN,TELEGRAM_ADMIN_ID
logger=logging.getLogger(__name__)
class TelegramBot:
    def __init__(self,db): self.db=db; self.app=None
    def _allowed(self,update): return bool(TELEGRAM_ADMIN_ID) and str(update.effective_user.id)==TELEGRAM_ADMIN_ID
    async def status(self,update:Update,context:ContextTypes.DEFAULT_TYPE):
        if not self._allowed(update): return
        a=self.db.account(); p=self.db.positions()
        await update.message.reply_text(f"AI QUANT 4.0 | PAPER ONLY\nCash: {a['cash']:.2f}\nOpen positions: {len(p)}")
    async def positions(self,update:Update,context:ContextTypes.DEFAULT_TYPE):
        if not self._allowed(update): return
        rows=self.db.positions(); await update.message.reply_text("\n".join(f"{x['symbol']}: {x['qty']:.6f} @ {x['entry']:.6f}" for x in rows) or "No open simulated positions")
    async def start(self):
        if not TELEGRAM_TOKEN or not TELEGRAM_ADMIN_ID or Application is None: return False
        self.app=Application.builder().token(TELEGRAM_TOKEN).build()
        self.app.add_handler(CommandHandler("status",self.status)); self.app.add_handler(CommandHandler("positions",self.positions))
        await self.app.initialize(); await self.app.start()
        if self.app.updater: await self.app.updater.start_polling()
        return True
    async def close(self):
        if self.app:
            if self.app.updater and self.app.updater.running: await self.app.updater.stop()
            await self.app.stop(); await self.app.shutdown(); self.app=None
