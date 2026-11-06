import asyncio
import logging
from datetime import datetime, timezone

from config import (
    SYMBOLS,
    SCAN_INTERVAL_SECONDS,
    MIN_SCORE_TO_ENTER
)

from technical_analysis import calculate_indicators

from decision_engine import (
    calculate_technical_score,
    evaluate_setup
)


logger = logging.getLogger(__name__)


def utc_timestamp():

    return datetime.now(
        timezone.utc
    ).isoformat()


class TradingEngine:

    def __init__(
        self,
        market,
        ai,
        news,
        trader,
        db
    ):

        self.market = market
        self.ai = ai
        self.news = news
        self.trader = trader
        self.db = db

        self.running = False

        self.last_scan = None
        self.last_error = None

        self.market_regime = "UNKNOWN"

        self.scan_lock = asyncio.Lock()

        self.last_decisions = []
        self.scan_stats = {
            "scanned": 0,
            "rejected": 0,
            "approved": 0,
            "errors": 0
        }

    async def start(self):

        logger.info("Starting AI QUANT engine")

        await self.market.start()
        await self.ai.start()
        await self.news.start()

        self.running = True

        logger.info(
            "AI QUANT engine started in PAPER mode"
        )

    async def close(self):

        self.running = False

        await self.news.close()
        await self.ai.close()
        await self.market.close()

        logger.info("AI QUANT engine stopped")

    async def get_market_regime(self):

        try:

            snapshot = await self.market.get_market_snapshot(
                "BTCUSDT"
            )

            if not isinstance(snapshot, dict):

                return "UNKNOWN"

            candles = snapshot.get("klines")

            indicators = calculate_indicators(
                candles
            )

            if not indicators:

                return "UNKNOWN"

            bullish = (
                indicators["ema9"] > indicators["ema21"]
                and indicators["ema21"] > indicators["ema50"]
                and indicators["price"] > indicators["ema50"]
            )

            return (
                "BULLISH"
                if bullish
                else "NOT_BULLISH"
            )

        except Exception:

            logger.exception(
                "BTC market regime calculation failed"
            )

            return "UNKNOWN"

    def save_decision(self, result):

        try:

            record = dict(result)

            record["timestamp"] = utc_timestamp()

            self.db.log_decision(record)

        except Exception:

            logger.exception(
                "Failed to save decision"
            )

    def record_decision(
        self,
        symbol,
        action,
        score,
        ai_vote,
        reasons
    ):

        result = {
            "symbol": symbol,
            "action": action,
            "score": score,
            "ai_vote": ai_vote,
            "reasons": reasons
        }

        self.last_decisions.append(result)

        self.last_decisions = (
            self.last_decisions[-50:]
        )

        self.save_decision(result)

        return result

    async def scan_once(self):

        if self.scan_lock.locked():

            return {
                "status": "BUSY",
                "message": "A scan is already running"
            }

        async with self.scan_lock:

            logger.info("Starting market scan")

            self.last_error = None
            self.last_scan = utc_timestamp()

            stats = {
                "scanned": 0,
                "rejected": 0,
                "approved": 0,
                "errors": 0
            }

            try:

                # Update existing simulated positions
                await self.trader.update_positions(
                    self.market
                )

                # Analyze Bitcoin market regime
                self.market_regime = (
                    await self.get_market_regime()
                )

                if self.market_regime != "BULLISH":

                    reason = (
                        "BTC market regime: "
                        + self.market_regime
                    )

                    logger.info(reason)

                    for symbol in SYMBOLS:

                        self.record_decision(
                            symbol,
                            "WAIT",
                            0,
                            "UNAVAILABLE",
                            [reason]
                        )

                        stats["rejected"] += 1

                    self.scan_stats = stats

                    return {
                        "status": "COMPLETED",
                        "regime": self.market_regime,
                        "stats": stats
                    }

                # Collect recent news
                news_items = []

                try:

                    news_items = await self.news.get_news(
                        limit=10
                    )

                except Exception:

                    logger.warning(
                        "News unavailable during scan",
                        exc_info=True
                    )

                news_context = [
                    {
                        "title": item.get("title", ""),
                        "description": item.get(
                            "description",
                            ""
                        )
                    }
                    for item in news_items
                ]

                for symbol in SYMBOLS:

                    stats["scanned"] += 1

                    try:

                        snapshot = (
                            await self.market.get_market_snapshot(
                                symbol
                            )
                        )

                        if not isinstance(snapshot, dict):

                            self.record_decision(
                                symbol,
                                "WAIT",
                                0,
                                "UNAVAILABLE",
                                ["Market snapshot unavailable"]
                            )

                            stats["rejected"] += 1
                            continue

                        candles = snapshot.get(
                            "klines"
                        )

                        indicators = calculate_indicators(
                            candles
                        )

                        if not indicators:

                            self.record_decision(
                                symbol,
                                "WAIT",
                                0,
                                "UNAVAILABLE",
                                ["Invalid technical data"]
                            )

                            stats["rejected"] += 1
                            continue

                        technical = (
                            calculate_technical_score(
                                indicators,
                                self.market_regime
                            )
                        )

                        if not technical.get("valid"):

                            self.record_decision(
                                symbol,
                                "WAIT",
                                0,
                                "UNAVAILABLE",
                                technical.get(
                                    "reasons",
                                    ["Technical evaluation failed"]
                                )
                            )

                            stats["rejected"] += 1
                            continue

                        technical_score = technical["score"]

                        # Do not call AI for weak technical setups
                        if (
                            technical_score + 15
                            < MIN_SCORE_TO_ENTER
                        ):

                            self.record_decision(
                                symbol,
                                "WAIT",
                                technical_score,
                                "NOT_CHECKED",
                                technical["reasons"]
                                + [
                                    "Technical score below entry threshold"
                                ]
                            )

                            stats["rejected"] += 1
                            continue

                        ai_context = {
                            "symbol": symbol,
                            "market_regime": self.market_regime,
                            "indicators": indicators,
                            "technical_score": technical_score,
                            "recent_news": news_context
                        }

                        ai_result = await self.ai.analyze(
                            ai_context
                        )

                        decision = evaluate_setup(
                            indicators,
                            self.market_regime,
                            ai_result,
                            technical_result=technical
                        )

                        action = decision["action"]

                        if action == "PAPER_BUY":

                            opened = (
                                self.trader.open_position(
                                    symbol,
                                    indicators["price"],
                                    indicators["atr"]
                                )
                            )

                            if opened:

                                stats["approved"] += 1

                            else:

                                action = "WAIT"

                                decision["reasons"].append(
                                    "Paper position could not be opened"
                                )

                                stats["rejected"] += 1

                        else:

                            stats["rejected"] += 1

                        self.record_decision(
                            symbol,
                            action,
                            decision["score"],
                            decision["ai_vote"],
                            decision["reasons"]
                        )

                    except Exception as error:

                        stats["errors"] += 1
                        stats["rejected"] += 1

                        logger.exception(
                            "Scan failed for %s",
                            symbol
                        )

                        self.record_decision(
                            symbol,
                            "ERROR",
                            0,
                            "UNAVAILABLE",
                            [str(error)[:200]]
                        )

                self.scan_stats = stats

                self.last_scan = utc_timestamp()

                logger.info(
                    "Scan completed: %s",
                    stats
                )

                return {
                    "status": "COMPLETED",
                    "regime": self.market_regime,
                    "stats": stats
                }

            except Exception as error:

                self.last_error = str(error)[:500]

                logger.exception(
                    "Market scan failed"
                )

                self.scan_stats = stats

                return {
                    "status": "ERROR",
                    "message": self.last_error,
                    "stats": stats
                }

    async def run_forever(self):

        logger.info(
            "Background scanner started"
        )

        while self.running:

            try:

                await self.scan_once()

            except asyncio.CancelledError:

                raise

            except Exception:

                logger.exception(
                    "Background scanner error"
                )

            await asyncio.sleep(
                SCAN_INTERVAL_SECONDS
            )
