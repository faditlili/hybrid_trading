"""Passive webhook layer handling authenticated admin query monitoring updates."""
import logging
import secrets
import config
class TelegramBot:
    def __init__(self, db, engine):
        self.db = db
        self.engine = engine
        self.app = None
    async def start(self):
        if (
            not config.TELEGRAM_TOKEN 
            or not config.TELEGRAM_ADMIN_ID
        ): 
            return False
            
        try:
            from telegram.ext import (
                Application, CommandHandler
            )
            self.app = (
                Application.builder()
                .token(config.TELEGRAM_TOKEN)
                .build()
            )
            async def auth(u):
                return secrets.compare_digest(
                    str(u.effective_user.id),
                    str(config.TELEGRAM_ADMIN_ID)
                )
                
            async def status_cmd(u, c):
                if await auth(u):
                    st = str(self.engine.status())
                    await u.message.reply_text(st)
                    
            async def pos_cmd(u, c):
                if await auth(u):
                    ps = str(self.db.positions())
                    await u.message.reply_text(ps)
            self.app.add_handler(
                CommandHandler("status", status_cmd)
            )
            self.app.add_handler(
                CommandHandler("positions", pos_cmd)
            )
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()
            return True
        except Exception:
            return False
            
    async def close(self):
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            self.app = None
