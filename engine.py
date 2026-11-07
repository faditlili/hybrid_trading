
"""Advanced asynchronous orchestration for AI QUANT.
Educational paper simulation only. No real order execution.
"""

import asyncio
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

logger = logging.getLogger(__name__)

SYMBOLS = tuple(config.SYMBOLS)

TIMEFRAMES = getattr(
    config,
    "TIMEFRAMES",
    (getattr(config, "TIMEFRAME", "15m"),)
)

if isinstance(TIMEFRAMES, str):
    TIMEFRAMES = (TIMEFRAMES,)

TIMEFRAMES = tuple(TIMEFRAMES)

REQUIRED_TIMEFRAMES = ("15m", "1h", "4h")

SCAN_INTERVAL_SECONDS = max(
    1,
    int(config.SCAN_INTERVAL_SECONDS)
)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class TradingEngine:

    def __init__(self, db):
        if db is None:
            raise ValueError("Database instance is required")

        self.db = db

        self.market = BingXMarketData()
        self.ai = AICouncil()
        self.news = NewsEngine()
        self.paper = PaperTrader(db)

        self.running = False
        self.task = None

        self.last_scan = None
        self.last_error = None
        self.last_prices = {}

        self.scan_lock = asyncio.Lock()
        self.lifecycle_lock = asyncio.Lock()

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
        logger.error("%s", self.last_error)
        self._log_event("ERROR", self.last_error)

    async def start(self):
        async with self.lifecycle_lock:

            if self.running:
                return

            started = []

            try:
                for component in (
                    self.market,
                    self.ai,
                    self.news
                ):
                    await component.start()
                    started.append(component)

                self.running = True

                self.task = asyncio.create_task(
                    self.run_loop(),
                    name="ai-quant-engine"
                )

                logger.info("AI QUANT engine started.")

            except Exception:
                self.running = False

                for component in reversed(started):
                    try:
                        await component.close()
                    except Exception:
                        logger.exception(
                            "Startup cleanup failed"
                        )

                self.task = None
                raise

    async def stop(self):
        async with self.lifecycle_lock:

            self.running = False

            if self.task is not None:
                self.task.cancel()

                await asyncio.gather(
                    self.task,
                    return_exceptions=True
                )

                self.task = None

            for component in (
                self.market,
                self.ai,
                self.news
            ):
                try:
                    await component.close()
                except Exception:
                    logger.exception(
                        "Error closing %s",
                        component.__class__.__name__
                    )

            logger.info("AI QUANT engine stopped.")

    async def _fetch_prices(self):
        """Fetch valid ticker prices independently for each symbol."""

        prices = {}
        errors = []

        for symbol in SYMBOLS:
            try:
                ticker = await self.market.ticker(symbol)

                if not isinstance(ticker, dict):
                    raise ValueError("Invalid ticker response")

                price = float(ticker["last"])

                if not math.isfinite(price) or price <= 0:
                    raise ValueError("Invalid market price")

                prices[symbol] = price

            except Exception as exc:
                message = f"{symbol} ticker error: {exc}"
                errors.append(message)

                logger.exception(
                    "Ticker error for %s",
                    symbol
                )

                self._log_event("ERROR", message)

        return prices, errors

    async def _analyze_symbol(self, symbol, price, prices):
        """Analyze one symbol and optionally open a paper position."""

        frames = {}

        for timeframe in TIMEFRAMES:
            candles = await self.market.klines(
                symbol,
                timeframe
            )

            frames[timeframe] = calculate_indicators(
                candles
            )

        missing = [
            timeframe
            for timeframe in REQUIRED_TIMEFRAMES
            if timeframe not in frames
        ]

        if missing:
            raise ValueError(
                "Required analysis timeframes missing: "
                + ", ".join(missing)
            )

        blocked = await self.news.blocks(symbol)

        ai = await self.ai.vote({
            "symbol": symbol,
            "frames": frames
        })

        decision = evaluate_setup(
            frames,
            ai.get("vote", "UNAVAILABLE"),
            ai.get("agreement", 0.0),
            blocked
        )

        self.db.record_decision(
            symbol,
            decision["action"],
            decision["score"],
            decision["reason"],
            utc_now()
        )

        decision["opened"] = False

        if decision["action"] == "PAPER_BUY_CANDIDATE":

            atr = frames["15m"].get("atr")

            if (
                isinstance(atr, bool)
                or not isinstance(atr, (int, float))
                or not math.isfinite(atr)
                or atr <= 0
            ):
                decision["reason"] = (
                    "Invalid ATR: paper entry rejected"
                )

            else:
                decision["opened"] = self.paper.open_position(
                    symbol,
                    price,
                    atr,
                    prices=prices
                )

                if not decision["opened"]:
                    decision["entry_status"] = (
                        "Rejected by portfolio risk, "
                        "exposure, cash, or position limits"
                    )
                else:
                    decision["entry_status"] = (
                        "Paper position opened"
                    )

        return {
            "symbol": symbol,
            **decision,
            "ai": ai
        }

    async def scan_once(self):
        """Run one complete market-analysis and portfolio cycle."""

        async with self.scan_lock:

            results = []
            errors = []

            prices, market_errors = await self._fetch_prices()
            errors.extend(market_errors)

            for symbol in SYMBOLS:

                if symbol not in prices:
                    continue

                try:
                    result = await self._analyze_symbol(
                        symbol,
                        prices[symbol],
                        prices
                    )

                    results.append(result)

                except Exception as exc:
                    message = (
                        f"{symbol} analysis failed: {exc}"
                    )

                    errors.append(message)

                    logger.exception(
                        "Analysis failed for %s",
                        symbol
                    )

                    self._log_event("ERROR", message)

            self.last_prices = prices.copy()

            # Always update existing paper positions when prices exist,
            # even if another symbol's analysis failed.
            if prices:
                try:
                    closed = self.paper.update(prices)

                    if closed:
                        logger.info(
                            "Paper positions closed: %s",
                            closed
                        )

                except Exception as exc:
                    message = (
                        f"Portfolio update failed: {exc}"
                    )

                    errors.append(message)

                    logger.exception(
                        "Portfolio update failed"
                    )

                    self._log_event("ERROR", message)

            self.last_scan = utc_now()

            if errors:
                self.last_error = " | ".join(errors)[:1000]
            elif not results:
                self.last_error = "No successful analysis results"
            else:
                self.last_error = None

            return results

    async def run_loop(self):
        """Background scanning loop."""

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
