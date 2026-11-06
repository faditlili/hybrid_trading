import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes
)

from config import TELEGRAM_TOKEN, ALLOWED_ADMIN_ID

logger = logging.getLogger(__name__)


class TelegramController:

    def __init__(self, engine, trader):

        self.engine = engine
        self.trader = trader

        self.application = None

        self.admin_id = (
            int(ALLOWED_ADMIN_ID)
            if ALLOWED_ADMIN_ID.isdigit()
            else None
        )

    async def start(self):

        if not TELEGRAM_TOKEN:
            logger.warning(
                "Telegram token not configured"
            )
            return

        if not self.admin_id:
            logger.warning(
                "Telegram admin ID not configured"
            )
            return

        self.application = (
            Application.builder()
            .token(TELEGRAM_TOKEN)
            .build()
        )

        self.application.add_handler(
            CommandHandler("start", self.start_command)
        )

        self.application.add_handler(
            CommandHandler("status", self.status_command)
        )

        self.application.add_handler(
            CommandHandler("scan", self.scan_command)
        )

        self.application.add_handler(
            CommandHandler("positions", self.positions_command)
        )

        await self.application.initialize()
        await self.application.start()

        await self.application.updater.start_polling(
            drop_pending_updates=True
        )

        logger.info("Telegram bot started")

    async def close(self):

        if not self.application:
            return

        try:

            if self.application.updater:
                await self.application.updater.stop()

            await self.application.stop()
            await self.application.shutdown()

        except Exception:
            logger.exception(
                "Telegram shutdown failed"
            )

        self.application = None

    def authorized(self, update: Update):

        user = update.effective_user

        return (
            user is not None
            and self.admin_id is not None
            and user.id == self.admin_id
        )

    async def reject(self, update: Update):

        if update.message:
            await update.message.reply_text(
                "غير مصرح لك باستخدام هذا البوت."
            )

    async def start_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):

        if not self.authorized(update):
            await self.reject(update)
            return

        await update.message.reply_text(
            "AI QUANT ONLINE\n\n"
            "PAPER TRADING ONLY\n\n"
            "/status - حالة النظام\n"
            "/scan - فحص السوق\n"
            "/positions - الصفقات الافتراضية"
        )

    async def status_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):

        if not self.authorized(update):
            await self.reject(update)
            return

        summary = self.trader.get_summary()

        text = (
            "AI QUANT STATUS\n\n"
            f"Balance: {summary['balance']:.4f} USDT\n"
            f"Equity: {summary['equity']:.4f} USDT\n"
            f"Realized P/L: {summary['realized_pnl']:.4f} USDT\n"
            f"Unrealized P/L: {summary['unrealized_pnl']:.4f} USDT\n"
            f"Open positions: {len(summary['positions'])}\n"
            f"Win rate: {summary['win_rate']:.2f}%\n\n"
            f"Market: {self.engine.market_regime}\n"
            f"Last scan: {self.engine.last_scan or 'Not yet'}\n"
            "Mode: PAPER ONLY"
        )

        await update.message.reply_text(text)

    async def scan_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):

        if not self.authorized(update):
            await self.reject(update)
            return

        if self.engine.scan_lock.locked():

            await update.message.reply_text(
                "الفحص جارٍ بالفعل. انتظر حتى ينتهي."
            )

            return

        await update.message.reply_text(
            "بدأ فحص السوق..."
        )

        results = await self.engine.scan_once()

        await update.message.reply_text(
            f"اكتمل الفحص.\n"
            f"عدد النتائج: {len(results)}\n"
            f"حالة السوق: {self.engine.market_regime}"
        )

    async def positions_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):

        if not self.authorized(update):
            await self.reject(update)
            return

        positions = self.trader.get_summary()["positions"]

        if not positions:

            await update.message.reply_text(
                "لا توجد صفقات افتراضية مفتوحة."
            )

            return

        lines = ["OPEN PAPER POSITIONS\n"]

        for position in positions:

            lines.append(
                f"{position['symbol']}\n"
                f"Entry: {position['entry_price']:.6f}\n"
                f"Current: {position['current_price']:.6f}\n"
                f"P/L: {position['unrealized_pnl']:.4f} USDT\n"
            )

        await update.message.reply_text(
            "\n".join(lines)
        )
