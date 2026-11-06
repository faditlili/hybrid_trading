import logging
import math

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes
)

from config import (
    TELEGRAM_TOKEN,
    TELEGRAM_ADMIN_ID
)


logger = logging.getLogger(__name__)


def safe_float(value, default=0.0):

    try:
        result = float(value)

        if not math.isfinite(result):
            return default

        return result

    except (TypeError, ValueError, OverflowError):
        return default


def safe_text(value, default="UNKNOWN", max_length=200):

    if value is None:
        return default

    try:
        result = str(value).strip()

        if not result:
            return default

        return result[:max_length]

    except Exception:
        return default


def safe_count(value):

    try:
        result = int(value)

        return max(0, result)

    except (TypeError, ValueError, OverflowError):
        return 0


class TelegramController:

    def __init__(self, engine, trader):

        self.engine = engine
        self.trader = trader

        self.application = None

        self.started = False
        self.initialized = False
        self.application_started = False
        self.polling_started = False

        self.admin_id = None

        try:

            if TELEGRAM_ADMIN_ID is not None:

                admin_id = int(TELEGRAM_ADMIN_ID)

                if admin_id > 0:
                    self.admin_id = admin_id

        except (TypeError, ValueError, OverflowError):

            logger.error(
                "Invalid TELEGRAM_ADMIN_ID configuration"
            )

    async def authorized(self, update: Update):

        if self.admin_id is None:
            return False

        user = update.effective_user

        if user is None:
            return False

        return user.id == self.admin_id

    async def reject(self, update: Update):

        message = update.effective_message

        if message:

            await message.reply_text(
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

        message = update.effective_message

        if not message:
            return

        await message.reply_text(
            "مرحباً بك في AI QUANT.\n\n"
            "النظام يعمل بالمحاكاة الورقية فقط.\n\n"
            "الأوامر المتاحة:\n"
            "/status - حالة النظام والرصيد\n"
            "/scan - فحص السوق\n"
            "/positions - المراكز الافتراضية\n\n"
            "لا يتم إرسال أوامر تداول حقيقية."
        )

    async def status_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):

        if not await self.authorized(update):

            await self.reject(update)
            return

        message = update.effective_message

        if not message:
            return

        try:

            summary = self.trader.get_summary()

            if not isinstance(summary, dict):
                summary = {}

            positions = summary.get("positions") or []

            if not isinstance(positions, list):
                positions = []

            balance = safe_float(
                summary.get("balance")
            )

            equity = safe_float(
                summary.get("equity")
            )

            realized = safe_float(
                summary.get("realized_pnl")
            )

            unrealized = safe_float(
                summary.get("unrealized_pnl")
            )

            reserved = safe_float(
                summary.get("reserved")
            )

            win_rate = safe_float(
                summary.get("win_rate")
            )

            regime = safe_text(
                getattr(
                    self.engine,
                    "market_regime",
                    "UNKNOWN"
                )
            )

            last_scan = safe_text(
                getattr(
                    self.engine,
                    "last_scan",
                    None
                ),
                default="لم يتم الفحص بعد",
                max_length=150
            )

            running = bool(
                getattr(
                    self.engine,
                    "running",
                    False
                )
            )

            status = (
                "RUNNING"
                if running
                else "STOPPED"
            )

            text = (
                "AI QUANT STATUS\n\n"
                f"Engine: {status}\n"
                f"Balance: {balance:.2f} USDT\n"
                f"Equity: {equity:.2f} USDT\n"
                f"Realized PnL: {realized:.2f} USDT\n"
                f"Unrealized PnL: {unrealized:.2f} USDT\n"
                f"Reserved: {reserved:.2f} USDT\n"
                f"Open Positions: {len(positions)}\n"
                f"Win Rate: {win_rate:.2f}%\n\n"
                f"Market Regime: {regime}\n"
                f"Last Scan: {last_scan}\n\n"
                "MODE: PAPER TRADING ONLY"
            )

            await message.reply_text(text[:3900])

        except Exception:

            logger.exception(
                "Telegram status command failed"
            )

            await message.reply_text(
                "تعذر الحصول على حالة النظام حالياً."
            )

    async def scan_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):

        if not await self.authorized(update):

            await self.reject(update)
            return

        message = update.effective_message

        if not message:
            return

        scan_lock = getattr(
            self.engine,
            "scan_lock",
            None
        )

        if scan_lock is not None and scan_lock.locked():

            await message.reply_text(
                "هناك فحص جارٍ حالياً. انتظر حتى ينتهي."
            )

            return

        if not getattr(self.engine, "running", False):

            await message.reply_text(
                "محرك النظام متوقف حالياً. "
                "لا يمكن بدء الفحص."
            )

            return

        await message.reply_text(
            "بدأ فحص السوق...\n"
            "يرجى الانتظار."
        )

        try:

            result = await self.engine.scan_once()

            if not isinstance(result, dict):
                result = {}

            result_status = safe_text(
                result.get("status"),
                default="UNKNOWN"
            )

            stats = result.get("stats") or {}

            if not isinstance(stats, dict):
                stats = {}

            if result_status == "COMPLETED":

                regime = safe_text(
                    result.get("regime")
                )

                scanned = safe_count(
                    stats.get("scanned")
                )

                approved = safe_count(
                    stats.get("approved")
                )

                rejected = safe_count(
                    stats.get("rejected")
                )

                errors = safe_count(
                    stats.get("errors")
                )

                text = (
                    "اكتمل الفحص.\n\n"
                    f"Market Regime: {regime}\n"
                    f"Scanned: {scanned}\n"
                    f"Approved: {approved}\n"
                    f"Rejected: {rejected}\n"
                    f"Errors: {errors}\n\n"
                    "MODE: PAPER TRADING ONLY"
                )

            else:

                error_message = safe_text(
                    result.get("message"),
                    default=result_status,
                    max_length=500
                )

                text = (
                    "تعذر إكمال الفحص.\n\n"
                    f"الحالة: {result_status}\n"
                    f"التفاصيل: {error_message}"
                )

            await message.reply_text(text[:3900])

        except Exception as exc:

            logger.exception(
                "Telegram scan command failed"
            )

            await message.reply_text(
                "حدث خطأ أثناء فحص السوق.\n"
                f"النوع: {type(exc).__name__}\n"
                "راجع سجل النظام للتفاصيل."
            )

    async def positions_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):

        if not await self.authorized(update):

            await self.reject(update)
            return

        message = update.effective_message

        if not message:
            return

        try:

            summary = self.trader.get_summary()

            if not isinstance(summary, dict):
                summary = {}

            positions = summary.get("positions") or []

            if not isinstance(positions, list):
                positions = []

            if not positions:

                await message.reply_text(
                    "لا توجد مراكز افتراضية مفتوحة حالياً."
                )

                return

            lines = [
                "OPEN PAPER POSITIONS",
                ""
            ]

            for position in positions:

                if not isinstance(position, dict):
                    continue

                symbol = safe_text(
                    position.get("symbol")
                )

                entry = safe_float(
                    position.get("entry_price")
                )

                current = safe_float(
                    position.get("current_price"),
                    entry
                )

                pnl = safe_float(
                    position.get("unrealized_pnl")
                )

                stop_loss = safe_float(
                    position.get("stop_loss")
                )

                take_profit = safe_float(
                    position.get("take_profit")
                )

                lines.append(
                    f"{symbol}\n"
                    f"Entry: {entry:.8f}\n"
                    f"Current: {current:.8f}\n"
                    f"Unrealized PnL: {pnl:.4f} USDT\n"
                    f"Stop Loss: {stop_loss:.8f}\n"
                    f"Take Profit: {take_profit:.8f}\n"
                )

            text = "\n".join(lines)

            if len(text) > 3900:

                text = (
                    text[:3700]
                    + "\n\nتم اختصار الرسالة بسبب طولها."
                )

            await message.reply_text(text)

        except Exception:

            logger.exception(
                "Telegram positions command failed"
            )

            await message.reply_text(
                "تعذر تحميل المراكز الافتراضية."
            )

    async def start(self):

        if self.started:
            return

        if not TELEGRAM_TOKEN:

            logger.warning(
                "Telegram token not configured"
            )

            return

        if self.admin_id is None:

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

            self.initialized = True

            await self.application.start()

            self.application_started = True

            if self.application.updater is None:

                raise RuntimeError(
                    "Telegram updater is unavailable"
                )

            await self.application.updater.start_polling()

            self.polling_started = True
            self.started = True

            logger.info(
                "Telegram bot started successfully"
            )

        except Exception:

            logger.exception(
                "Telegram startup failed"
            )

            await self.close()

    async def close(self):

        application = self.application

        if application is None:
            return

        try:

            if (
                application.updater is not None
                and self.polling_started
                and application.updater.running
            ):

                await application.updater.stop()

        except Exception:

            logger.exception(
                "Telegram polling shutdown failed"
            )

        try:

            if (
                self.application_started
                and application.running
            ):

                await application.stop()

        except Exception:

            logger.exception(
                "Telegram application stop failed"
            )

        try:

            if self.initialized:

                await application.shutdown()

        except Exception:

            logger.exception(
                "Telegram application shutdown failed"
            )

        finally:

            self.application = None

            self.started = False
            self.initialized = False
            self.application_started = False
            self.polling_started = False
