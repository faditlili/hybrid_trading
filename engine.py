import asyncio
import logging
from datetime import datetime, timezone

from config import SYMBOLS, SCAN_INTERVAL_SECONDS, MIN_SCORE_TO_ENTER
from technical_analysis import calculate_indicators
from decision_engine import (
    calculate_technical_score,
    evaluate_setup
)

logger = logging.getLogger(__name__)


def utc_timestamp():
    return datetime.now(timezone.utc).isoformat()


class TradingEngine:

    def __init__(self, market, ai, news, trader, db):

        self.market = market
        self.ai = ai
        self.news = news
        self.trader = trader
        self.db = db

        self.running = False
        self.scan_lock = asyncio.Lock()

        self.last_scan = None
        self.last_results = []
        self.market_regime = "UNKNOWN"
        self.last_error = None

    async def start(self):

        started = []

        try:
            await self.market.start()
            started.append(self.market)

            await self.ai.start()
            started.append(self.ai)

            await self.news.start()
            started.append(self.news)

            logger.info("AI QUANT services started")

        except Exception:

            for service in reversed(started):
                try:
                    await service.close()
                except Exception:
                    logger.exception("Service cleanup failed")

            raise

    async def close(self):

        self.running = False

        for service in (
            self.news,
            self.ai,
            self.market
        ):
            try:
                await service.close()
            except Exception:
                logger.exception("Service shutdown failed")

    async def get_market_regime(self):

        try:

            candles = await self.market.get_klines(
                "BTCUSDT"
            )

            indicators = calculate_indicators(candles)

            if not indicators:
                return "UNKNOWN"

            bullish = (
                indicators["ema9"] > indicators["ema21"]
                and indicators["ema21"] > indicators["ema50"]
            )

            return "BULLISH" if bullish else "NOT_BULLISH"

        except Exception as exc:

            logger.warning(
                "Market regime calculation failed: %s",
                str(exc)[:200]
            )

            return "UNKNOWN"

    async def scan_once(self):

        async with self.scan_lock:

            started_at = utc_timestamp()

            results = []

            try:

                # مراقبة الصفقات الافتراضية المفتوحة أولاً
                await self.trader.update_positions(
                    self.market
                )

                regime = await self.get_market_regime()

                self.market_regime = regime

                if regime != "BULLISH":

                    self.last_results = []
                    self.last_scan = started_at
                    self.last_error = None

                    logger.info(
                        "Scan skipped: market regime is %s",
                        regime
                    )

                    return []

                for symbol in SYMBOLS:

                    if symbol in self.trader.positions:
                        continue

                    try:

                        snapshot = (
                            await self.market.get_market_snapshot(
                                symbol
                            )
                        )

                        if not snapshot:
                            continue

                        candles = snapshot["candles"]

                        indicators = calculate_indicators(
                            candles
                        )

                        if not indicators:
                            continue

                        # تقييم فني أولي قبل استدعاء النماذج
                        technical = calculate_technical_score(
                            indicators,
                            regime
                        )

                        # لا نستهلك طلبات AI إذا كان الحد الأقصى
                        # الممكن بعد إضافة تصويت AI أقل من العتبة
                        if (
                            technical["score"] + 15
                            < MIN_SCORE_TO_ENTER
                        ):

                            results.append({
                                "symbol": symbol,
                                "price": snapshot["ticker"]["price"],
                                "score": technical["score"],
                                "action": "WAIT",
                                "reasons": technical["reasons"],
                                "ai_vote": "SKIPPED",
                                "opened": False
                            })

                            continue

                        ai_result = await self.ai.analyze({
                            "symbol": symbol,
                            "timeframe": "15m",
                            "price": snapshot["ticker"]["price"],
                            "change_24h": snapshot["ticker"]["change_pct"],
                            "quote_volume": snapshot["ticker"]["quote_volume"],
                            "indicators": indicators
                        })

                        decision = evaluate_setup(
                            indicators,
                            regime,
                            ai_result
                        )

                        opened = False

                        if decision["action"] == "PAPER_BUY":

                            opened = self.trader.open_position(
                                symbol,
                                snapshot["ticker"]["price"],
                                indicators["atr"]
                            )

                        result = {
                            "symbol": symbol,
                            "price": snapshot["ticker"]["price"],
                            "score": decision["score"],
                            "action": decision["action"],
                            "reasons": decision["reasons"],
                            "ai_vote": ai_result.get(
                                "vote",
                                "UNAVAILABLE"
                            ),
                            "opened": opened
                        }

                        results.append(result)

                        try:
                            self.db.log_decision({
                                **result,
                                "timestamp": utc_timestamp()
                            })
                        except Exception:
                            logger.exception(
                                "Could not save decision for %s",
                                symbol
                            )

                    except Exception as exc:

                        logger.warning(
                            "Symbol scan failed for %s: %s",
                            symbol,
                            str(exc)[:200]
                        )

                self.last_scan = started_at
                self.last_results = results
                self.last_error = None

                logger.info(
                    "Scan completed: %s symbols evaluated",
                    len(results)
                )

                return results

            except Exception as exc:

                self.last_error = str(exc)[:300]

                logger.exception(
                    "Market scan failed"
                )

                self.last_scan = started_at
                self.last_results = results

                return results

    async def run_forever(self):

        self.running = True

        logger.info("AI QUANT scanner started")

        while self.running:

            cycle_start = asyncio.get_running_loop().time()

            try:
                await self.scan_once()

            except asyncio.CancelledError:
                raise

            except Exception:
                logger.exception("Scanner cycle failed")

            elapsed = (
                asyncio.get_running_loop().time()
                - cycle_start
            )

            remaining = max(
                1,
                SCAN_INTERVAL_SECONDS - elapsed
            )

            try:
                await asyncio.sleep(remaining)

            except asyncio.CancelledError:
                raise

        logger.info("AI QUANT scanner stopped")

    def stop(self):
        self.running = False
