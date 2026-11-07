
"""Advanced asynchronous orchestration for AI QUANT.
Paper trading only. No real order execution.
"""
import asyncio
import logging
from datetime import datetime, timezone

import config

from market_data import BingXMarketData
from technical_analysis import calculate_indicators
from ai_council import AICouncil
from news_engine import NewsEngine
from decision_engine import evaluate_setup
from paper_trading import PaperTrader

logger = logging.getLogger(__name__)

SYMBOLS = config.SYMBOLS

TIMEFRAMES = getattr(
    config,
    "TIMEFRAMES",
    (getattr(config, "TIMEFRAME", "15m"),)
)

if isinstance(TIMEFRAMES, str):
    TIMEFRAMES = (TIMEFRAMES,)

SCAN_INTERVAL_SECONDS = config.SCAN_INTERVAL_SECONDS


class TradingEngine:

    def __init__(self, db):
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

    async def start(self):

        if self.running:
            return

        await self.market.start()
        await self.ai.start()
        await self.news.start()

        self.running = True

        if self.task is None or self.task.done():
            self.task = asyncio.create_task(
                self.run_loop()
            )

        logger.info("AI QUANT engine started.")

    async def stop(self):

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

    async def scan_once(self):

        async with self.scan_lock:

            prices = {}
            results = []
            market_errors = {}

            timestamp = datetime.now(
                timezone.utc
            ).isoformat()

            # Fetch all market prices first.
            for symbol in SYMBOLS:

                try:
                    ticker = await self.market.ticker(
                        symbol
                    )

                    price = float(ticker["last"])

                    if price <= 0:
                        raise ValueError(
                            "Invalid market price"
                        )

                    prices[symbol] = price

                except Exception as exc:

                    market_errors[symbol] = str(exc)

                    self.last_error = (
                        f"{symbol}: {exc}"
                    )

                    logger.exception(
                        "Ticker error: %s",
                        symbol
                    )

                    self.db.log_event(
                        "ERROR",
                        self.last_error,
                        timestamp
                    )

            # Analyze each available symbol.
            for symbol in SYMBOLS:

                if symbol not in prices:
                    continue

                try:

                    frames = {}

                    for timeframe in TIMEFRAMES:

                        candles = await self.market.klines(
                            symbol,
                            timeframe
                        )

                        frames[timeframe] = (
                            calculate_indicators(
                                candles
                            )
                        )

                    if not frames:
                        continue

                    # News protection.
                    blocked = await self.news.blocks(
                        symbol
                    )

                    # AI consensus.
                    ai = await self.ai.vote({
                        "symbol": symbol,
                        "frames": frames
                    })

                    # Advanced decision analysis.
                    decision = evaluate_setup(
                        frames,
                        ai["vote"],
                        ai["agreement"],
                        blocked
                    )

                    self.db.record_decision(
                        symbol,
                        decision["action"],
                        decision["score"],
                        decision["reason"],
                        datetime.now(
                            timezone.utc
                        ).isoformat()
                    )

                    # Paper trading only.
                    if decision["action"] == "PAPER_BUY_CANDIDATE":

                        preferred_frame = (
                            "15m"
                            if "15m" in frames
                            else next(iter(frames))
                        )

                        atr = frames[
                            preferred_frame
                        ]["atr"]

                        opened = self.paper.open_position(
                            symbol,
                            prices[symbol],
                            atr,
                            prices=prices
                        )

                        decision["opened"] = opened

                    results.append({
                        "symbol": symbol,
                        **decision,
                        "ai": ai
                    })

                except Exception as exc:

                    self.last_error = (
                        f"{symbol}: {exc}"
                    )

                    logger.exception(
                        "Analysis failed for %s",
                        symbol
                    )

                    self.db.log_event(
                        "ERROR",
                        self.last_error,
                        datetime.now(
                            timezone.utc
                        ).isoformat()
                    )

            # Update portfolio with current market prices.
            self.last_prices = prices.copy()

            if prices:
                self.paper.update(prices)

            self.last_scan = datetime.now(
                timezone.utc
            ).isoformat()

            if not market_errors and results:
                self.last_error = None

            return results

    async def run_loop(self):

        while self.running:

            try:

                await self.scan_once()

            except asyncio.CancelledError:
                raise

            except Exception as exc:

                self.last_error = str(exc)

                logger.exception(
                    "AI QUANT engine loop error"
                )

            try:
                await asyncio.sleep(
                    SCAN_INTERVAL_SECONDS
                )

            except asyncio.CancelledError:
                raise


# Backward compatibility:
# Other project files can import Engine or TradingEngine.

Engine = TradingEngine
