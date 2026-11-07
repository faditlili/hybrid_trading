
"""Advanced asynchronous orchestration for AI QUANT.

Educational paper simulation only.
No real order execution or private exchange endpoints.
"""

import asyncio
import inspect
import logging
import math

from datetime import datetime, timezone

import config

from market_data import BingXMarketData
from technical_analysis import calculate_indicators
from ai_council import AICouncil
from news_engine import NewsEngine
from decision_engine import evaluate_setup
from paper_trading import PaperTrader
from telegram_bot import TelegramBot


logger = logging.getLogger("AI_QUANT.engine")


# --------------------------------------------------
# Configuration
# --------------------------------------------------

SYMBOLS = tuple(config.SYMBOLS)

REQUIRED_TIMEFRAMES = ("15m", "1h", "4h")

_configured_timeframes = getattr(
    config,
    "TIMEFRAMES",
    getattr(config, "TIMEFRAME", "15m")
)

if isinstance(_configured_timeframes, str):
    _configured_timeframes = (_configured_timeframes,)

TIMEFRAMES = tuple(
    dict.fromkeys(
        tuple(_configured_timeframes)
        + REQUIRED_TIMEFRAMES
    )
)

SCAN_INTERVAL_SECONDS = max(
    60,
    int(config.SCAN_INTERVAL_SECONDS)
)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------
# Trading engine
# --------------------------------------------------

class TradingEngine:

    def __init__(self, db):

        if db is None:
            raise ValueError(
                "A valid Database instance is required"
            )

        self.db = db

        # Core components.
        self.market = BingXMarketData()
        self.ai = AICouncil()
        self.news = NewsEngine()

        # Paper-only portfolio.
        self.paper = PaperTrader(db)

        # Optional Telegram notifications.
        self.telegram = TelegramBot(
            db,
            engine=self
        )

        # Runtime state.
        self.running = False
        self.task = None

        self.last_scan = None
        self.last_error = None
        self.last_prices = {}

        # Prevent overlapping scans and lifecycle operations.
        self.scan_lock = asyncio.Lock()
        self.lifecycle_lock = asyncio.Lock()

    # --------------------------------------------------
    # Logging
    # --------------------------------------------------

    def _log_event(self, level, message):

        try:
            self.db.log_event(
                level,
                str(message)[:1000],
                utc_now()
            )

        except Exception:
            logger.exception(
                "Could not write database event"
            )

    def _set_error(self, message):

        self.last_error = str(message)[:1000]

        logger.error(
            "%s",
            self.last_error
        )

        self._log_event(
            "ERROR",
            self.last_error
        )

    # --------------------------------------------------
    # Telegram notifications
    # --------------------------------------------------

    async def _send_telegram_notification(
        self,
        method_name,
        payload
    ):
        """Send an optional notification without interrupting the engine."""

        if self.telegram is None:
            return False

        method = getattr(
            self.telegram,
            method_name,
            None
        )

        if not callable(method):
            logger.warning(
                "Telegram method %s is unavailable",
                method_name
            )
            return False

        try:

            result = method(payload)

            if inspect.isawaitable(result):
                await result

            return True

        except Exception:

            logger.exception(
                "Telegram notification failed: %s",
                method_name
            )

            self._log_event(
                "WARNING",
                f"Telegram notification failed: {method_name}"
            )

            return False

    async def _notify_trade_opened(self, symbol):
        """Notify Telegram after a paper position has been saved."""

        getter = getattr(
            self.paper,
            "get_position",
            None
        )

        if not callable(getter):
            logger.error(
                "PaperTrader.get_position() is unavailable"
            )
            return False

        try:
            position = getter(symbol)

        except Exception:

            logger.exception(
                "Could not retrieve opened position: %s",
                symbol
            )

            return False

        if not isinstance(position, dict):
            logger.error(
                "Opened position could not be retrieved: %s",
                symbol
            )
            return False

        return await self._send_telegram_notification(
            "notify_trade_opened",
            position
        )

    async def _notify_trade_closed(self, trade):
        """Notify Telegram after a closed paper trade has been committed."""

        if not isinstance(trade, dict):
            logger.warning(
                "Invalid closed trade notification payload"
            )
            return False

        return await self._send_telegram_notification(
            "notify_trade_closed",
            trade
        )

    # --------------------------------------------------
    # Component lifecycle
    # --------------------------------------------------

    async def start(self):

        async with self.lifecycle_lock:

            if self.running:
                return

            started_components = []

            try:

                # Start essential components.
                for component in (
                    self.market,
                    self.ai,
                    self.news,
                ):

                    await component.start()

                    started_components.append(
                        component
                    )

                self.running = True

                # Telegram is optional.
                try:

                    await self.telegram.start()

                except Exception:

                    logger.exception(
                        "Telegram startup failed; "
                        "engine will continue without Telegram"
                    )

                    self._log_event(
                        "WARNING",
                        "Telegram startup failed"
                    )

                self.task = asyncio.create_task(
                    self.run_loop(),
                    name="ai-quant-engine"
                )

                logger.info(
                    "AI QUANT engine started successfully."
                )

                self._log_event(
                    "INFO",
                    "AI QUANT engine started"
                )

            except Exception:

                self.running = False

                # Clean up components that already started.
                for component in reversed(
                    started_components
                ):

                    try:
                        await component.close()

                    except Exception:
                        logger.exception(
                            "Startup cleanup failed for %s",
                            component.__class__.__name__
                        )

                self.task = None

                raise

    async def stop(self):

        async with self.lifecycle_lock:

            self.running = False

            # Stop background scanning.
            if self.task is not None:

                self.task.cancel()

                await asyncio.gather(
                    self.task,
                    return_exceptions=True
                )

                self.task = None

            # Stop Telegram first.
            try:

                await self.telegram.close()

            except Exception:

                logger.exception(
                    "Telegram shutdown failed"
                )

            # Stop core components.
            for component in (
                self.news,
                self.ai,
                self.market,
            ):

                try:

                    await component.close()

                except Exception:

                    logger.exception(
                        "Error closing %s",
                        component.__class__.__name__
                    )

            logger.info(
                "AI QUANT engine stopped."
            )

            self._log_event(
                "INFO",
                "AI QUANT engine stopped"
            )

    # --------------------------------------------------
    # Market data
    # --------------------------------------------------

    async def _fetch_prices(self):
        """Fetch and validate public ticker prices."""

        prices = {}
        errors = []

        for symbol in SYMBOLS:

            try:

                ticker = await self.market.ticker(
                    symbol
                )

                if not isinstance(ticker, dict):
                    raise ValueError(
                        "Invalid ticker response"
                    )

                price = float(
                    ticker["last"]
                )

                if (
                    not math.isfinite(price)
                    or price <= 0
                ):
                    raise ValueError(
                        "Invalid market price"
                    )

                prices[symbol] = price

            except Exception as exc:

                message = (
                    f"{symbol} ticker error: {exc}"
                )

                errors.append(message)

                logger.exception(
                    "Ticker error for %s",
                    symbol
                )

                self._log_event(
                    "ERROR",
                    message
                )

        return prices, errors

    # --------------------------------------------------
    # News compatibility
    # --------------------------------------------------

    async def _check_news(self, symbol):
        """Support synchronous or asynchronous news checks."""

        result = self.news.blocks(symbol)

        if inspect.isawaitable(result):
            result = await result

        return bool(result)

    # --------------------------------------------------
    # Symbol analysis
    # --------------------------------------------------

    async def _analyze_symbol(
        self,
        symbol,
        price,
        prices
    ):
        """Analyze multiple timeframes and evaluate a paper entry."""

        frames = {}

        # Fetch and calculate all required timeframes.
        for timeframe in TIMEFRAMES:

            candles = await self.market.klines(
                symbol,
                timeframe
            )

            indicators = calculate_indicators(
                candles
            )

            if not isinstance(indicators, dict):
                raise ValueError(
                    f"Invalid indicators for {timeframe}"
                )

            frames[timeframe] = indicators

        missing = [
            timeframe
            for timeframe in REQUIRED_TIMEFRAMES
            if timeframe not in frames
        ]

        if missing:

            raise ValueError(
                "Required timeframes missing: "
                + ", ".join(missing)
            )

        # Check news risk.
        blocked = await self._check_news(
            symbol
        )

        # Obtain AI council vote.
        ai = await self.ai.vote({
            "symbol": symbol,
            "frames": frames,
        })

        if not isinstance(ai, dict):

            ai = {
                "vote": "UNAVAILABLE",
                "agreement": 0.0,
                "reason": "Invalid AI response",
            }

        vote = ai.get(
            "vote",
            "UNAVAILABLE"
        )

        agreement = ai.get(
            "agreement",
            0.0
        )

        try:
            agreement = float(agreement)

        except (TypeError, ValueError):
            agreement = 0.0

        if (
            not math.isfinite(agreement)
            or not 0 <= agreement <= 1
        ):
            agreement = 0.0

        # Evaluate technical, AI and news conditions.
        decision = evaluate_setup(
            frames,
            vote,
            agreement,
            blocked
        )

        if not isinstance(decision, dict):

            raise ValueError(
                "Decision engine returned an invalid result"
            )

        decision = dict(decision)

        decision.setdefault(
            "action",
            "HOLD"
        )

        decision.setdefault(
            "score",
            0
        )

        decision.setdefault(
            "reason",
            "No valid setup"
        )

        decision["opened"] = False

        # --------------------------------------------------
        # Paper entry validation
        # --------------------------------------------------

        if decision["action"] == "PAPER_BUY_CANDIDATE":

            atr = frames["15m"].get("atr")

            valid_atr = (
                isinstance(atr, (int, float))
                and not isinstance(atr, bool)
                and math.isfinite(atr)
                and atr > 0
            )

            if not valid_atr:

                decision["action"] = "HOLD"

                decision["reason"] = (
                    "Invalid ATR: paper entry rejected"
                )

                decision["entry_status"] = (
                    "Rejected: invalid ATR"
                )

            else:

                opened = self.paper.open_position(
                    symbol,
                    price,
                    atr,
                    prices=prices
                )

                decision["opened"] = bool(
                    opened
                )

                if opened:

                    decision["entry_status"] = (
                        "Paper position opened"
                    )

                    # The paper trader saves the position first.
                    # Telegram notification happens only afterward.
                    await self._notify_trade_opened(
                        symbol
                    )

                else:

                    decision["entry_status"] = (
                        "Rejected by portfolio risk, "
                        "exposure, cash, duplicate-symbol "
                        "or position limits"
                    )

        # Persist the final decision.
        self.db.record_decision(
            symbol,
            decision["action"],
            decision["score"],
            decision["reason"],
            utc_now()
        )

        return {
            "symbol": symbol,
            **decision,
            "ai": ai,
        }

    # --------------------------------------------------
    # Complete scan
    # --------------------------------------------------

    async def scan_once(self):
        """Run one complete analysis and portfolio update cycle."""

        async with self.scan_lock:

            results = []
            errors = []

            prices, market_errors = (
                await self._fetch_prices()
            )

            errors.extend(
                market_errors
            )

            # Analyze every symbol with a valid ticker.
            for symbol in SYMBOLS:

                if symbol not in prices:
                    continue

                try:

                    result = await self._analyze_symbol(
                        symbol,
                        prices[symbol],
                        prices
                    )

                    results.append(
                        result
                    )

                except Exception as exc:

                    message = (
                        f"{symbol} analysis failed: {exc}"
                    )

                    errors.append(
                        message
                    )

                    logger.exception(
                        "Analysis failed for %s",
                        symbol
                    )

                    self._log_event(
                        "ERROR",
                        message
                    )

            # Preserve the latest valid ticker snapshot.
            if prices:

                self.last_prices = prices.copy()

            # Update open paper positions independently
            # of whether analysis succeeded.
            if prices:

                try:

                    closed = self.paper.update(
                        prices
                    )

                    if closed:

                        logger.info(
                            "Paper positions closed: %s",
                            closed
                        )

                        self._log_event(
                            "INFO",
                            f"Paper positions closed: {closed}"
                        )

                        # update() returns closed trades only
                        # after their database transaction commits.
                        for trade in closed:

                            await self._notify_trade_closed(
                                trade
                            )

                except Exception as exc:

                    message = (
                        f"Portfolio update failed: {exc}"
                    )

                    errors.append(
                        message
                    )

                    logger.exception(
                        "Portfolio update failed"
                    )

                    self._log_event(
                        "ERROR",
                        message
                    )

            self.last_scan = utc_now()

            if errors:

                self.last_error = (
                    " | ".join(errors)[:1000]
                )

            elif not results:

                self.last_error = (
                    "No successful analysis results"
                )

            else:

                self.last_error = None

            return results

    # --------------------------------------------------
    # Background loop
    # --------------------------------------------------

    async def run_loop(self):
        """Continuous background scanning."""

        while self.running:

            try:

                await self.scan_once()

            except asyncio.CancelledError:

                raise

            except Exception as exc:

                self._set_error(
                    f"Engine loop error: {exc}"
                )

            try:

                await asyncio.sleep(
                    SCAN_INTERVAL_SECONDS
                )

            except asyncio.CancelledError:

                raise


# Backward compatibility.
Engine = TradingEngine
