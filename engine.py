
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

SYMBOLS = config.SYMBOLS

TIMEFRAMES = getattr(
    config,
    "TIMEFRAMES",
    (getattr(config, "TIMEFRAME", "15m"),)
)

if isinstance(TIMEFRAMES, str):
    TIMEFRAMES = (TIMEFRAMES,)

SCAN_INTERVAL_SECONDS = config.SCAN_INTERVAL_SECONDS


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
            logger.exception("Could not write database event")

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

                if self.task is None or self.task.done():
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

    async def scan_once(self):

        async with self.scan_lock:

            prices = {}
            results = []
            market_errors = {}

            for symbol in SYMBOLS:

                try:
                    ticker = await self.market.ticker(symbol)

                    price = float(ticker["last"])

                    if not math.isfinite(price) or price <= 0:
                        raise ValueError("Invalid market price")

                    prices[symbol] = price

                except Exception as exc:
                    market_errors[symbol] = str(exc)

                    self.last_error = f"{symbol}: {exc}"

                    logger.exception(
                        "Ticker error: %s",
                        symbol
                    )

                    self._log_event(
                        "ERROR",
                        self.last_error
                    )

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

                        frames[timeframe] = calculate_indicators(
                            candles
                        )

                    if any(
                        timeframe not in frames
                        for timeframe in ("15m", "1h", "4h")
                    ):
                        raise ValueError(
                            "Required analysis timeframe missing"
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

                    if decision["action"] == "PAPER_BUY_CANDIDATE":

                        atr = frames["15m"].get("atr")

                        if (
                            isinstance(atr, bool)
                            or not isinstance(atr, (int, float))
                            or not math.isfinite(atr)
                            or atr <= 0
                        ):
                            decision["opened"] = False
                            decision["reason"] = (
                                "Invalid ATR: paper entry rejected"
                            )
                        else:
                            decision["opened"] = (
                                self.paper.open_position(
                                    symbol,
                                    prices[symbol],
                                    atr,
                                    prices=prices
                                )
                            )

                    results.append({
                        "symbol": symbol,
                        **decision,
                        "ai": ai
                    })

                except Exception as exc:
                    self.last_error = f"{symbol}: {exc}"

                    logger.exception(
                        "Analysis failed for %s",
                        symbol
                    )

                    self._log_event(
                        "ERROR",
                        self.last_error
                    )

            self.last_prices = prices.copy()

            if prices:
                try:
                    self.paper.update(prices)
                except Exception as exc:
                    self.last_error = (
                        f"Portfolio update failed: {exc}"
                    )

                    logger.exception(
                        "Portfolio update failed"
                    )

                    self._log_event(
                        "ERROR",
                        self.last_error
                    )

            self.last_scan = utc_now()

            if market_errors:
                self.last_error = (
                    "One or more market data requests failed"
                )
            elif not results:
                self.last_error = (
                    self.last_error or "No successful analysis results"
                )
            else:
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

                self._log_event(
                    "ERROR",
                    self.last_error
                )

            try:
                await asyncio.sleep(
                    SCAN_INTERVAL_SECONDS
                )

            except asyncio.CancelledError:
                raise


# Backward compatibility.
Engine = TradingEngine
