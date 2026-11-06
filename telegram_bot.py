from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes
)

from config import TELEGRAM_TOKEN, ALLOWED_ADMIN_ID


class TelegramController:
    def __init__(self, controller):
        self.controller = controller
        self.application = None

    def authorized(self, update):
        if not ALLOWED_ADMIN_ID:
            return False

        user = update.effective_user

        return (
            user is not None
            and str(user.id) == str(ALLOWED_ADMIN_ID)
        )

    async def start_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        if not self.authorized(update):
            return

        await update.message.reply_text(
            "AI QUANT is online.\n"
            "Paper trading only.\n\n"
            "/status - Account status\n"
            "/scan - Scan market\n"
            "/positions - Open positions"
        )

    async def status_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        if not self.authorized(update):
            return

        summary = self.controller.trader.summary()

        message = (
            "AI QUANT STATUS\n\n"
            f"Available balance: {summary['available_balance']:.4f} USDT\n"
            f"Realized P/L: {summary['realized_pnl']:.4f} USDT\n"
            f"Open positions: {summary['open_positions']}\n"
            f"Wins: {summary['wins']}\n"
            f"Losses: {summary['losses']}"
        )

        await update.message.reply_text(message)

    async def scan_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        if not self.authorized(update):
            return

        await update.message.reply_text(
            "Market scan started..."
        )

        results = await self.controller.scan_once()

        if not results:
            await update.message.reply_text(
                "No qualifying paper-trading setups found."
            )
            return

        lines = []

        for item in results[:15]:
            lines.append(
                f"{item['symbol']} | "
                f"Score: {item['score']} | "
                f"{item['action']}"
            )

        await update.message.reply_text(
            "\n".join(lines)
        )

    async def positions_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        if not self.authorized(update):
            return

        positions = self.controller.trader.positions

        if not positions:
            await update.message.reply_text(
                "No open paper positions."
            )
            return

        lines = []

        for symbol, p in positions.items():
            lines.append(
                f"{symbol}\n"
                f"Entry: {p['entry']:.8f}\n"
                f"Stop: {p['stop']:.8f}\n"
                f"Target: {p['target']:.8f}"
            )

        await update.message.reply_text(
            "\n\n".join(lines)
        )

    async def start(self):
        if not TELEGRAM_TOKEN:
            return False

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
        await self.application.updater.start_polling()

        return True

    async def stop(self):
        if not self.application:
            return

        if self.application.updater:
            await self.application.updater.stop()

        await self.application.stop()
        await self.application.shutdown()
