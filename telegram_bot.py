
"""Optional Telegram notifications and admin-only commands.

Paper simulation only.
No real exchange orders.
Trade notifications are sent only after successful database commits.
"""

import logging
import math
import asyncio

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

        self._lifecycle_lock = asyncio.Lock()

    # --------------------------------------------------
    # Utilities
    # --------------------------------------------------

    @staticmethod
    def _number(value, default=0.0):
        try:
            result = float(value)

            if math.isfinite(result):
                return result

            return default

        except (TypeError, ValueError, OverflowError):
            return default

    @staticmethod
    def _format_money(value):
        return f"{value:+.4f}"

    @staticmethod
    def _safe_text(value, default="N/A"):
        if value is None:
            return default

        result = str(value).strip()

        return result[:150] if result else default

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
        """Reject unauthorized commands."""

        message = getattr(update, "effective_message", None)

        if message is not None:
            await message.reply_text("Access denied.")

    # --------------------------------------------------
    # Internal message sender
    # --------------------------------------------------

    async def _send_admin_message(self, message):
        """Send a message to the configured administrator.

        Failures are isolated and never stop the trading engine.
        """

        if not self.running or self.app is None:
            logger.warning(
                "Telegram message skipped: bot is not running."
            )
            return False

        if not self.admin_id:
            return False

        try:
            chat_id = int(self.admin_id)

            await self.app.bot.send_message(
                chat_id=chat_id,
                text=str(message)[:4000],
            )

            return True

        except Exception as exc:
            logger.error(
                "Telegram message delivery failed: %s",
                type(exc).__name__,
            )
            return False

    # --------------------------------------------------
    # Trade opened notification
    # --------------------------------------------------

    async def notify_trade_opened(self, position):
        """Notify admin after a simulated position is committed."""

        if not isinstance(position, dict):
            return False

        try:
            symbol = self._safe_text(position.get("symbol"))
            qty = self._number(position.get("qty"))
            entry = self._number(position.get("entry"))
            stop = self._number(position.get("stop"))
            target = self._number(position.get("target"))
            notional = self._number(position.get("notional"))
            entry_fee = self._number(position.get("entry_fee"))
            opened_at = self._safe_text(
                position.get("opened_at")
            )

            if (
                symbol == "N/A"
                or qty <= 0
                or entry <= 0
                or stop <= 0
                or target <= entry
            ):
                logger.warning(
                    "Invalid position data for Telegram notification."
                )
                return False

            message = (
                "AI QUANT 4.0\n"
                "PAPER TRADE OPENED\n\n"
                f"Symbol: {symbol}\n"
                f"Quantity: {qty:.8f}\n"
                f"Entry price: {entry:.8f}\n"
                f"Stop loss: {stop:.8f}\n"
                f"Take profit: {target:.8f}\n"
                f"Position value: {notional:.4f}\n"
                f"Entry fee: {entry_fee:.4f}\n"
                f"Opened at: {opened_at}\n\n"
                "Simulation only. No real order was placed."
            )

            return await self._send_admin_message(message)

        except Exception as exc:
            logger.error(
                "Trade-open notification failed: %s",
                type(exc).__name__,
            )
            return False

    # --------------------------------------------------
    # Trade closed notification
    # --------------------------------------------------

    async def notify_trade_closed(self, trade):
        """Notify admin after a simulated position is closed."""

        if not isinstance(trade, dict):
            return False

        try:
            symbol = self._safe_text(trade.get("symbol"))
            qty = self._number(trade.get("qty"))
            entry = self._number(trade.get("entry_price"))
            exit_price = self._number(trade.get("exit_price"))

            gross_pnl = self._number(
                trade.get("gross_pnl")
            )

            entry_fee = self._number(
                trade.get("entry_fee")
            )

            exit_fee = self._number(
                trade.get("exit_fee")
            )

            total_fees = self._number(
                trade.get(
                    "total_fees",
                    entry_fee + exit_fee,
                )
            )

            pnl = self._number(trade.get("pnl"))

            reason = self._safe_text(
                trade.get("reason")
            )

            closed_at = self._safe_text(
                trade.get("closed_at")
            )

            if (
                symbol == "N/A"
                or qty <= 0
                or entry <= 0
                or exit_price <= 0
            ):
                logger.warning(
                    "Invalid closed-trade data for Telegram notification."
                )
                return False

            result_label = (
                "PROFIT"
                if pnl > 0
                else "LOSS"
                if pnl < 0
                else "BREAKEVEN"
            )

            message = (
                "AI QUANT 4.0\n"
                "PAPER TRADE CLOSED\n\n"
                f"Symbol: {symbol}\n"
                f"Quantity: {qty:.8f}\n"
                f"Entry price: {entry:.8f}\n"
                f"Exit price: {exit_price:.8f}\n\n"
                f"Gross P/L: {self._format_money(gross_pnl)}\n"
                f"Entry fee: {entry_fee:.4f}\n"
                f"Exit fee: {exit_fee:.4f}\n"
                f"Total fees: {total_fees:.4f}\n\n"
                f"Net P/L: {self._format_money(pnl)}\n"
                f"Result: {result_label}\n"
                f"Close reason: {reason}\n"
                f"Closed at: {closed_at}\n\n"
                "Simulation only. No real order was placed."
            )

            return await self._send_admin_message(message)

        except Exception as exc:
            logger.error(
                "Trade-close notification failed: %s",
                type(exc).__name__,
            )
            return False

    # --------------------------------------------------
    # Status command
    # --------------------------------------------------

    async def status(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
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
                f"Cash: {cash:.4f}\n"
                f"Portfolio equity: {equity:.4f}\n"
                f"Open positions: {len(positions)}"
            )

            await update.effective_message.reply_text(message)

        except Exception:
            logger.exception(
                "Telegram status command failed."
            )

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
                    stop = float(position["stop"])
                    target = float(position["target"])

                    lines.append(
                        f"{symbol}\n"
                        f"Quantity: {qty:.8f}\n"
                        f"Entry: {entry:.8f}\n"
                        f"Stop: {stop:.8f}\n"
                        f"Target: {target:.8f}\n"
                    )

                message = "\n".join(lines)

            await update.effective_message.reply_text(message)

        except Exception:
            logger.exception(
                "Telegram positions command failed."
            )

            await update.effective_message.reply_text(
                "Unable to retrieve positions."
            )

    # --------------------------------------------------
    # Start bot
    # --------------------------------------------------

    async def start(self):
        """Start Telegram polling if configured."""

        async with self._lifecycle_lock:

            if self.running:
                return True

            if not TELEGRAM_TOKEN or not self.admin_id:
                logger.info(
                    "Telegram is disabled: token or admin ID is missing."
                )
                return False

            if Application is None or CommandHandler is None:
                logger.warning(
                    "Telegram library unavailable. "
                    "Telegram features are disabled."
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

                logger.info(
                    "Telegram bot started successfully."
                )

                return True

            except Exception:
                logger.exception(
                    "Telegram startup failed."
                )

                await self._close_unlocked()
                return False

    # --------------------------------------------------
    # Stop bot
    # --------------------------------------------------

    async def _close_unlocked(self):
        app = self.app

        if app is None:
            self.running = False
            self.initialized = False
            return

        try:
            if (
                app.updater is not None
                and app.updater.running
            ):
                await app.updater.stop()

            if app.running:
                await app.stop()

            if self.initialized:
                await app.shutdown()

        except Exception:
            logger.exception(
                "Telegram shutdown failed."
            )

        finally:
            self.app = None
            self.running = False
            self.initialized = False

            logger.info("Telegram bot stopped.")

    async def close(self):
        """Stop polling and release Telegram resources."""

        async with self._lifecycle_lock:
            await self._close_unlocked()
