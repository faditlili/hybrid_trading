import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes
)

from config import (
    TELEGRAM_TOKEN,
    ALLOWED_ADMIN_ID
)


logger = logging.getLogger(__name__)


class TelegramController:

    def __init__(self, engine, trader):

        self.engine = engine
        self.trader = trader

        self.application = None
        self.started = False

        try:

            self.admin_id = (
                int(ALLOWED_ADMIN_ID)
                if ALLOWED_ADMIN_ID
                else None
            )

        except (TypeError, ValueError):

            self.admin_id = None

            logger.error(
                "Invalid ALLOWED_ADMIN_ID configuration"
            )

    async def authorized(self, update: Update):

        if not self.admin_id:
            return False

        user = update.effective_user

        if not user:
            return False

        return user.id == self.admin_id

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

        if not await self.authorized(update):

            await self.reject(update)
            return

        await update.message.reply_text(
            "مرحباً بك في AI QUANT.\n\n"
            "النظام يعمل بالمحاكاة الافتراضية فقط.\n\n"
            "الأوامر المتاحة:\n"
            "/status - حالة النظام والرصيد\n"
            "/scan - فحص السوق\n"
            "/positions - المراكز الافتراضية\n"
        )

    async def status_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):

        if not await self.authorized(update):

            await self.reject(update)
            return

        summary = self.trader.get_summary()

        message = (
            "AI QUANT STATUS\n\n"
            f"Balance: {summary['balance']:.2f} USDT\n"
            f"Equity: {summary['equity']:.2f} USDT\n"
            f"Realized PnL: {summary['realized_pnl']:.2f} USDT\n"
            f"Unrealized PnL: {summary['unrealized_pnl']:.2f} USDT\n"
            f"Reserved: {summary['reserved']:.2f} USDT\n"
            f"Open Positions: {len(summary['positions'])}\n"
            f"Win Rate: {summary['win_rate']:.2f}%\n\n"
            f"Market Regime: {self.engine.market_regime}\n"
            f"Last Scan: {self.engine.last_scan}\n"
            "\nMODE: PAPER TRADING ONLY"
        )

        await update.message.reply_text(message)

    async def scan_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):

        if not await self.authorized(update):

            await self.reject(update)
            return

        if self.engine.scan_lock.locked():

            await update.message.reply_text(
                "هناك فحص جارٍ حالياً. انتظر حتى ينتهي."
            )

            return

        await update.message.reply_text(
            "بدأ فحص السوق..."
        )

        result = await self.engine.scan_once()

        if result.get("status") == "COMPLETED":

            stats = result.get("stats", {})

            message = (
                "اكتمل الفحص.\n\n"
                f"Market Regime: {result.get('regime')}\n"
                f"Scanned: {stats.get('scanned', 0)}\n"
                f"Approved: {stats.get('approved', 0)}\n"
                f"Rejected: {stats.get('rejected', 0)}\n"
                f"Errors: {stats.get('errors', 0)}"
            )

        else:

            message = (
                "تعذر إكمال الفحص.\n"
                f"{result.get('message', result.get('status'))}"
            )

        await update.message.reply_text(message)

    async def positions_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):

        if not await self.authorized(update):

            await self.reject(update)
            return

        summary = self.trader.get_summary()

        positions = summary.get(
            "positions",
            []
        )

        if not positions:

            await update.message.reply_text(
                "لا توجد مراكز افتراضية مفتوحة حالياً."
            )

            return

        lines = [
            "OPEN PAPER POSITIONS\n"
        ]

        for position in positions:

            symbol = position.get(
                "symbol",
                "UNKNOWN"
            )

            entry = float(
                position.get("entry_price", 0)
            )

            current = float(
                position.get("current_price", entry)
            )

            pnl = float(
                position.get("unrealized_pnl", 0)
            )

            lines.append(
                f"{symbol}\n"
                f"Entry: {entry:.6f}\n"
                f"Current: {current:.6f}\n"
                f"Unrealized PnL: {pnl:.4f} USDT\n"
            )

        await update.message.reply_text(
            "\n".join(lines)
        )

    async def start(self):

        if self.started:
            return

        if not TELEGRAM_TOKEN:

            logger.warning(
                "Telegram token not configured"
            )

            return

        if not self.admin_id:

            logger.warning(
                "Telegram admin ID not configured; bot disabled"
            )

            return

        try:

            self.application = (
                Application.builder()
                .token(TELEGRAM_TOKEN)
                .build()
            )

            self.application.add_handler(
                CommandHandler(
                    "start",
                    self.start_command
                )
            )

            self.application.add_handler(
                CommandHandler(
                    "status",
                    self.status_command
                )
            )

            self.application.add_handler(
                CommandHandler(
                    "scan",
                    self.scan_command
                )
            )

            self.application.add_handler(
                CommandHandler(
                    "positions",
                    self.positions_command
                )
            )

            await self.application.initialize()

            await self.application.start()

            if self.application.updater:

                await self.application.updater.start_polling()

            self.started = True

            logger.info(
                "Telegram bot started"
            )

        except Exception:

            logger.exception(
                "Telegram startup failed"
            )

            await self.close()

    async def close(self):

        if not self.application:
            return

        try:

            if self.application.updater:

                if self.application.updater.running:

                    await self.application.updater.stop()

            if self.application.running:

                await self.application.stop()

            await self.application.shutdown()

        except Exception:

            logger.exception(
                "Telegram shutdown failed"
            )

        finally:

            self.application = None
            self.started = False
