import asyncio
import logging
import math

from datetime import datetime, timezone

import pandas as pd

from config import (
    SYMBOLS,
    SCAN_INTERVAL_SECONDS,
    MAX_SCAN_DURATION_SECONDS,
    MIN_SCORE_TO_ENTER,
    PAPER_MODE,
)

from technical_analysis import calculate_indicators

from decision_engine import (
    calculate_technical_score,
    evaluate_setup,
)


logger = logging.getLogger(__name__)


def utc_timestamp():
    return datetime.now(timezone.utc).isoformat()


def valid_number(value):

    if isinstance(value, bool):
        return False

    try:
        return math.isfinite(float(value))

    except (TypeError, ValueError, OverflowError):
        return False


def safe_float(value, default=0.0):

    if valid_number(value):
        return float(value)

    return float(default)


def safe_reasons(value):

    if not isinstance(value, (list, tuple)):
        return ["No explanation provided"]

    reasons = []

    for reason in value:

        if reason is None:
            continue

        reasons.append(str(reason)[:300])

        if len(reasons) >= 20:
            break

    return reasons or ["No explanation provided"]


class TradingEngine:

    def __init__(
        self,
        market,
        ai,
        news,
        trader,
        db,
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
        self.lifecycle_lock = asyncio.Lock()

        self.last_decisions = []

        self._started_components = []

        self.scan_stats = {
            "scanned": 0,
            "rejected": 0,
            "approved": 0,
            "errors": 0,
        }

        self._validate_config()

    # ========================================================
    # CONFIGURATION
    # ========================================================

    def _validate_config(self):

        if PAPER_MODE is not True:
            raise RuntimeError(
                "AI QUANT only supports PAPER_MODE=True"
            )

        numeric_settings = {
            "SCAN_INTERVAL_SECONDS": SCAN_INTERVAL_SECONDS,
            "MAX_SCAN_DURATION_SECONDS": MAX_SCAN_DURATION_SECONDS,
            "MIN_SCORE_TO_ENTER": MIN_SCORE_TO_ENTER,
        }

        for name, value in numeric_settings.items():

            if not valid_number(value):
                raise ValueError(
                    f"{name} must be a valid finite number"
                )

        if SCAN_INTERVAL_SECONDS <= 0:
            raise ValueError(
                "SCAN_INTERVAL_SECONDS must be positive"
            )

        if MAX_SCAN_DURATION_SECONDS <= 0:
            raise ValueError(
                "MAX_SCAN_DURATION_SECONDS must be positive"
            )

        if not 0 <= MIN_SCORE_TO_ENTER <= 100:
            raise ValueError(
                "MIN_SCORE_TO_ENTER must be between 0 and 100"
            )

        if not isinstance(SYMBOLS, (list, tuple)):
            raise ValueError(
                "SYMBOLS must be a list or tuple"
            )

        if not SYMBOLS:
            raise ValueError(
                "SYMBOLS cannot be empty"
            )

        normalized = []

        for symbol in SYMBOLS:

            if not isinstance(symbol, str):
                raise ValueError(
                    "Every symbol must be a string"
                )

            symbol = symbol.strip().upper()

            if not symbol:
                raise ValueError(
                    "SYMBOLS contains an empty symbol"
                )

            if symbol in normalized:
                raise ValueError(
                    f"Duplicate symbol: {symbol}"
                )

            normalized.append(symbol)

        self.symbols = normalized

        self.scan_interval = float(
            SCAN_INTERVAL_SECONDS
        )

        self.max_scan_duration = float(
            MAX_SCAN_DURATION_SECONDS
        )

        self.minimum_score = float(
            MIN_SCORE_TO_ENTER
        )

    # ========================================================
    # LIFECYCLE
    # ========================================================

    async def start(self):

        async with self.lifecycle_lock:

            if self.running:
                logger.warning(
                    "Trading engine is already running"
                )
                return

            logger.info(
                "Starting AI QUANT in PAPER mode"
            )

            components = (
                self.market,
                self.ai,
                self.news,
            )

            try:

                for component in components:

                    await component.start()

                    self._started_components.append(
                        component
                    )

                self.running = True

                logger.info(
                    "AI QUANT engine started successfully"
                )

            except BaseException:

                logger.exception(
                    "Engine startup failed. Rolling back components"
                )

                self.running = False

                await self._close_started_components()

                raise

    async def _close_started_components(self):

        components = list(
            reversed(self._started_components)
        )

        self._started_components.clear()

        for component in components:

            try:

                await component.close()

            except Exception:

                logger.exception(
                    "Component shutdown failed: %s",
                    type(component).__name__,
                )

    async def close(self):

        async with self.lifecycle_lock:

            self.running = False

            # Wait for an active scan to finish or time out
            # before closing its dependencies.

            async with self.scan_lock:

                await self._close_started_components()

            logger.info(
                "AI QUANT engine stopped"
            )

    # ========================================================
    # MARKET REGIME
    # ========================================================

    async def get_market_regime(self):

        try:

            snapshot = await self.market.get_market_snapshot(
                "BTCUSDT"
            )

            if not isinstance(snapshot, dict):
                return "UNKNOWN"

            candles = snapshot.get("klines")

            if not isinstance(candles, pd.DataFrame):
                return "UNKNOWN"

            indicators = calculate_indicators(
                candles
            )

            if not isinstance(indicators, dict):
                return "UNKNOWN"

            required = (
                "ema9",
                "ema21",
                "ema50",
                "price",
            )

            for key in required:

                if not valid_number(indicators.get(key)):
                    return "UNKNOWN"

            ema9 = float(indicators["ema9"])
            ema21 = float(indicators["ema21"])
            ema50 = float(indicators["ema50"])
            price = float(indicators["price"])

            if min(ema9, ema21, ema50, price) <= 0:
                return "UNKNOWN"

            bullish = (
                ema9 > ema21
                and ema21 > ema50
                and price > ema50
            )

            return (
                "BULLISH"
                if bullish
                else "NOT_BULLISH"
            )

        except asyncio.CancelledError:
            raise

        except Exception:

            logger.exception(
                "BTC market regime calculation failed"
            )

            return "UNKNOWN"

    # ========================================================
    # DECISION STORAGE
    # ========================================================

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
        reasons,
    ):

        result = {
            "symbol": str(symbol),
            "action": str(action),
            "score": safe_float(score),
            "ai_vote": str(ai_vote),
            "reasons": safe_reasons(reasons),
        }

        self.last_decisions.append(result)

        self.last_decisions = (
            self.last_decisions[-50:]
        )

        self.save_decision(result)

        return result

    # ========================================================
    # NEWS CONTEXT
    # ========================================================

    async def _get_news_context(self):

        try:

            result = await self.news.get_news(
                limit=10
            )

            if not isinstance(result, list):
                return []

            news_context = []

            for item in result:

                if not isinstance(item, dict):
                    continue

                title = str(
                    item.get("title", "")
                ).strip()

                description = str(
                    item.get("description", "")
                ).strip()

                if not title:
                    continue

                news_context.append({
                    "title": title[:300],
                    "description": description[:600],
                })

            return news_context

        except asyncio.CancelledError:
            raise

        except Exception:

            logger.warning(
                "News unavailable during scan",
                exc_info=True,
            )

            return []

    # ========================================================
    # SYMBOL SCANNING
    # ========================================================

    async def _scan_symbol(
        self,
        symbol,
        news_context,
        stats,
    ):

        stats["scanned"] += 1

        try:

            snapshot = await self.market.get_market_snapshot(
                symbol
            )

            if not isinstance(snapshot, dict):

                self.record_decision(
                    symbol,
                    "WAIT",
                    0,
                    "UNAVAILABLE",
                    ["Market snapshot unavailable"],
                )

                stats["rejected"] += 1
                return

            candles = snapshot.get("klines")

            if not isinstance(candles, pd.DataFrame):

                self.record_decision(
                    symbol,
                    "WAIT",
                    0,
                    "UNAVAILABLE",
                    ["Invalid candle data: DataFrame required"],
                )

                stats["rejected"] += 1
                return

            indicators = calculate_indicators(
                candles
            )

            if not isinstance(indicators, dict):

                self.record_decision(
                    symbol,
                    "WAIT",
                    0,
                    "UNAVAILABLE",
                    ["Invalid technical data"],
                )

                stats["rejected"] += 1
                return

            # Technical evaluation

            technical = calculate_technical_score(
                indicators,
                self.market_regime,
            )

            if (
                not isinstance(technical, dict)
                or technical.get("valid") is not True
            ):

                reasons = (
                    technical.get("reasons", [])
                    if isinstance(technical, dict)
                    else ["Technical evaluation failed"]
                )

                self.record_decision(
                    symbol,
                    "WAIT",
                    0,
                    "UNAVAILABLE",
                    reasons,
                )

                stats["rejected"] += 1
                return

            technical_score = technical.get("score")

            if (
                not valid_number(technical_score)
                or not 0 <= float(technical_score) <= 85
            ):

                self.record_decision(
                    symbol,
                    "WAIT",
                    0,
                    "UNAVAILABLE",
                    ["Invalid technical score"],
                )

                stats["rejected"] += 1
                return

            technical_score = float(
                technical_score
            )

            # Avoid unnecessary AI requests.

            if (
                technical_score + 15
                < self.minimum_score
            ):

                self.record_decision(
                    symbol,
                    "WAIT",
                    technical_score,
                    "NOT_CHECKED",
                    safe_reasons(
                        technical.get("reasons", [])
                    ) + [
                        "Technical score below entry threshold"
                    ],
                )

                stats["rejected"] += 1
                return

            # Prepare AI context.

            ai_context = {
                "symbol": symbol,
                "market_regime": self.market_regime,
                "indicators": indicators,
                "technical_score": technical_score,
                "recent_news": news_context,
            }

            ai_result = await self.ai.analyze(
                ai_context
            )

            if not isinstance(ai_result, dict):

                ai_result = {
                    "vote": "UNAVAILABLE",
                    "reason": "Invalid AI response",
                }

            # Final decision.

            decision = evaluate_setup(
                indicators,
                self.market_regime,
                ai_result,
                technical_result=technical,
            )

            if not isinstance(decision, dict):
                raise ValueError(
                    "Decision engine returned an invalid result"
                )

            action = decision.get(
                "action",
                "WAIT",
            )

            score = safe_float(
                decision.get("score")
            )

            ai_vote = str(
                decision.get("ai_vote", "UNAVAILABLE")
            )

            reasons = safe_reasons(
                decision.get("reasons", [])
            )

            # Only PAPER_BUY is an accepted entry action.

            if action == "PAPER_BUY":

                price = indicators.get("price")
                atr = indicators.get("atr")

                if (
                    not valid_number(price)
                    or not valid_number(atr)
                    or float(price) <= 0
                    or float(atr) <= 0
                ):

                    action = "WAIT"

                    reasons.append(
                        "Invalid price or ATR for paper trading"
                    )

                    stats["rejected"] += 1

                else:

                    opened = self.trader.open_position(
                        symbol,
                        float(price),
                        float(atr),
                    )

                    if opened:

                        stats["approved"] += 1

                    else:

                        action = "WAIT"

                        reasons.append(
                            "Paper position could not be opened"
                        )

                        stats["rejected"] += 1

            else:

                if action != "WAIT":

                    action = "WAIT"

                    reasons.append(
                        "Unsupported decision action"
                    )

                stats["rejected"] += 1

            self.record_decision(
                symbol,
                action,
                score,
                ai_vote,
                reasons,
            )

        except asyncio.CancelledError:
            raise

        except Exception as error:

            stats["errors"] += 1
            stats["rejected"] += 1

            logger.exception(
                "Scan failed for %s",
                symbol,
            )

            self.record_decision(
                symbol,
                "ERROR",
                0,
                "UNAVAILABLE",
                [str(error)[:200]],
            )

    # ========================================================
    # ONE SCAN CYCLE
    # ========================================================

    async def _run_scan_cycle(self, stats):

        # Update existing simulated positions.

        await self.trader.update_positions(
            self.market
        )

        if not self.running:
            return "STOPPED"

        # Determine BTC market regime.

        self.market_regime = (
            await self.get_market_regime()
        )

        logger.info(
            "BTC market regime: %s",
            self.market_regime,
        )

        # Collect recent news.

        news_context = await self._get_news_context()

        # Scan configured symbols.

        for symbol in self.symbols:

            if not self.running:
                return "STOPPED"

            await self._scan_symbol(
                symbol,
                news_context,
                stats,
            )

        return "COMPLETED"

    # ========================================================
    # SCAN CONTROL
    # ========================================================

    async def scan_once(self):

        if not self.running:

            return {
                "status": "NOT_RUNNING",
                "message": "Trading engine is not running",
            }

        if self.scan_lock.locked():

            return {
                "status": "BUSY",
                "message": "A scan is already running",
            }

        async with self.scan_lock:

            if not self.running:

                return {
                    "status": "NOT_RUNNING",
                    "message": "Trading engine is not running",
                }

            logger.info(
                "Starting market scan"
            )

            self.last_error = None
            self.last_scan = utc_timestamp()

            stats = {
                "scanned": 0,
                "rejected": 0,
                "approved": 0,
                "errors": 0,
            }

            try:

                async with asyncio.timeout(
                    self.max_scan_duration
                ):

                    status = await self._run_scan_cycle(
                        stats
                    )

                self.scan_stats = dict(stats)
                self.last_scan = utc_timestamp()

                if status == "STOPPED":

                    return {
                        "status": "STOPPED",
                        "regime": self.market_regime,
                        "stats": dict(stats),
                    }

                logger.info(
                    "Scan completed: %s",
                    stats,
                )

                return {
                    "status": "COMPLETED",
                    "regime": self.market_regime,
                    "stats": dict(stats),
                }

            except TimeoutError:

                self.last_error = (
                    "Scan exceeded MAX_SCAN_DURATION_SECONDS"
                )

                self.scan_stats = dict(stats)
                self.last_scan = utc_timestamp()

                logger.warning(
                    "Market scan timed out after %.1f seconds",
                    self.max_scan_duration,
                )

                return {
                    "status": "TIMEOUT",
                    "message": self.last_error,
                    "regime": self.market_regime,
                    "stats": dict(stats),
                }

            except asyncio.CancelledError:
                raise

            except Exception as error:

                self.last_error = str(error)[:500]

                logger.exception(
                    "Market scan failed"
                )

                self.scan_stats = dict(stats)
                self.last_scan = utc_timestamp()

                return {
                    "status": "ERROR",
                    "message": self.last_error,
                    "stats": dict(stats),
                }

    # ========================================================
    # BACKGROUND SCANNER
    # ========================================================

    async def run_forever(self):

        if not self.running:

            logger.warning(
                "Cannot start scanner: engine is not running"
            )

            return

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

            if not self.running:
                break

            await asyncio.sleep(
                self.scan_interval
            )
