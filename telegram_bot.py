
"""Optional Telegram notifications and admin-only commands.
Paper simulation only. No real exchange orders.
"""

import logging

from config import TELEGRAM_TOKEN, TELEGRAM_ADMIN_ID

try:
    from telegram import Update
    from telegram.ext import (
        Application,
        CommandHandler,
        ContextTypes,
    )
except ImportError:
    Update = None
    ContextTypes = None
    Application = None
    CommandHandler = None


logger = logging.getLogger("AI_QUANT.telegram")


class TelegramBot:
    def __init__(self, db, engine=None):
        self.db = db
        self.engine = engine
        self.app = None

        self.initialized = False
        self.running = False

        self.admin_id = (
            str(TELEGRAM_ADMIN_ID).strip()
            if TELEGRAM_ADMIN_ID is not None
            else ""
        )

    # --------------------------------------------------
    # Authorization
    # --------------------------------------------------

    def _allowed(self, update):
        """Allow commands only from the configured admin."""

        if not self.admin_id or update is None:
            return False

        user = getattr(update, "effective_user", None)

        if user is None or user.id is None:
            return False

        return str(user.id) == self.admin_id

    async def _deny(self, update):
        """Respond to unauthorized users without exposing data."""

        message = getattr(update, "effective_message", None)

        if message is not None:
            await message.reply_text("Access denied.")

    # --------------------------------------------------
    # Status command
    # --------------------------------------------------

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._allowed(update):
            await self._deny(update)
            return

        try:
            account = self.db.account()
            positions = self.db.positions()

            cash = float(account["cash"])

            equity = cash

            if self.engine is not None:
                prices = self.engine.last_prices or {}
                equity = self.engine.paper.equity(prices)

            message = (
                "AI QUANT 4.0\n"
                "PAPER SIMULATION ONLY\n\n"
                f"Cash: {cash:.2f}\n"
                f"Portfolio equity: {equity:.2f}\n"
                f"Open positions: {len(positions)}"
            )

            await update.effective_message.reply_text(message)

        except Exception:
            logger.exception("Telegram status command failed.")

            await update.effective_message.reply_text(
                "Unable to retrieve portfolio status."
            )

    # --------------------------------------------------
    # Positions command
    # --------------------------------------------------

    async def positions(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        if not self._allowed(update):
            await self._deny(update)
            return

        try:
            rows = self.db.positions()

            if not rows:
                message = "No open simulated positions."

            else:
                lines = [
                    "AI QUANT 4.0",
                    "OPEN SIMULATED POSITIONS",
                    "",
                ]

                for position in rows[:20]:
                    symbol = position["symbol"]
                    qty = float(position["qty"])
                    entry = float(position["entry"])

                    lines.append(
                        f"{symbol}: {qty:.6f} @ {entry:.6f}"
                    )

                message = "\n".join(lines)

            await update.effective_message.reply_text(message)

        except Exception:
            logger.exception("Telegram positions command failed.")

            await update.effective_message.reply_text(
                "Unable to retrieve positions."
            )

    # --------------------------------------------------
    # Start bot
    # --------------------------------------------------

    async def start(self):
        """Start Telegram polling if configured."""

        if self.running:
            return True

        if not TELEGRAM_TOKEN or not self.admin_id:
            logger.info(
                "Telegram is disabled: token or admin ID is missing."
            )
            return False

        if Application is None or CommandHandler is None:
            logger.warning(
                "Telegram library is unavailable. "
                "Telegram notifications are disabled."
            )
            return False

        try:
            self.app = (
                Application.builder()
                .token(TELEGRAM_TOKEN)
                .build()
            )

            self.app.add_handler(
                CommandHandler("status", self.status)
            )

            self.app.add_handler(
                CommandHandler("positions", self.positions)
            )

            await self.app.initialize()
            self.initialized = True

            await self.app.start()

            if self.app.updater is not None:
                await self.app.updater.start_polling()

            self.running = True

            logger.info("Telegram bot started successfully.")

            return True

        except Exception:
            logger.exception("Telegram startup failed.")

            await self.close()

            return False

    # --------------------------------------------------
    # Stop bot
    # --------------------------------------------------

    async def close(self):
        """Stop Telegram polling and release resources."""

        app = self.app

        if app is None:
            self.running = False
            self.initialized = False
            return

        try:
            if app.updater is not None and app.updater.running:
                await app.updater.stop()

            if app.running:
                await app.stop()

            if self.initialized:
                await app.shutdown()

        except Exception:
            logger.exception("Telegram shutdown failed.")

        finally:
            self.app = None
            self.running = False
            self.initialized = False

            logger.info("Telegram bot stopped.")
