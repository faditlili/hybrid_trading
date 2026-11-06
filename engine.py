import asyncio
from config import SYMBOLS, SCAN_INTERVAL_SECONDS
from technical_analysis import calculate_indicators
from decision_engine import evaluate_setup


class TradingEngine:
    def __init__(
        self,
        market_data,
        ai_council,
        news_engine,
        trader,
        database
    ):
        self.market = market_data
        self.ai = ai_council
        self.news = news_engine
        self.trader = trader
        self.db = database

        self.running = False
        self.scan_lock = asyncio.Lock()
        self.last_scan = None
        self.last_results = []

    async def start(self):
        await self.market.start()
        await self.ai.start()
        await self.news.start()

    async def close(self):
        await self.market.close()
        await self.ai.close()
        await self.news.close()

    async def get_market_regime(self):
        try:
            candles = await self.market.get_klines(
                "BTCUSDT",
                limit=100
            )

            indicators = calculate_indicators(candles)

            if (
                indicators["ema9"] > indicators["ema21"]
                and indicators["ema21"] > indicators["ema50"]
            ):
                return "BULLISH"

            return "NOT_BULLISH"

        except Exception as exc:
            self.db.log_event(
                "ERROR",
                f"BTC regime error: {str(exc)[:250]}"
            )
            return "UNKNOWN"

    async def scan_once(self):
        async with self.scan_lock:
            results = []

            try:
                regime = await self.get_market_regime()

                position_updates = await self.trader.update_positions(
                    self.market
                )

                for symbol, ok, result in position_updates:
                    if not ok:
                        self.db.log_event(
                            "WARNING",
                            f"{symbol}: {result}"
                        )

                if regime != "BULLISH":
                    self.db.log_event(
                        "INFO",
                        f"Scan skipped: BTC regime is {regime}"
                    )

                    self.last_scan = utc_timestamp()
                    self.last_results = results
                    return results

                for symbol in SYMBOLS:
                    if symbol in self.trader.positions:
                        continue

                    try:
                        snapshot = await self.market.get_market_snapshot(
                            symbol
                        )

                        if snapshot is None:
                            continue

                        indicators = calculate_indicators(
                            snapshot["candles"]
                        )

                        ai_result = await self.ai.analyze(
                            symbol,
                            indicators,
                            regime
                        )

                        decision = evaluate_setup(
                            indicators,
                            regime,
                            ai_result
                        )

                        self.db.log_decision(
                            symbol,
                            decision["score"],
                            decision["action"],
                            decision["reasons"]
                        )

                        result = {
                            "symbol": symbol,
                            "price": indicators["price"],
                            "score": decision["score"],
                            "action": decision["action"],
                            "reasons": decision["reasons"],
                            "ai_vote": ai_result["vote"]
                        }

                        if decision["action"] == "PAPER_BUY":
                            opened, details = self.trader.open_position(
                                symbol,
                                indicators["price"],
                                indicators["atr"]
                            )

                            result["opened"] = opened

                            if not opened:
                                result["message"] = details

                        results.append(result)

                    except Exception as exc:
                        self.db.log_event(
                            "ERROR",
                            f"{symbol} scan error: {str(exc)[:250]}"
                        )

                self.last_scan = utc_timestamp()
                self.last_results = results

                return results

            except Exception as exc:
                self.db.log_event(
                    "ERROR",
                    f"Scan failure: {str(exc)[:300]}"
                )

                return results

    async def run_forever(self):
        if self.running:
            return

        self.running = True

        try:
            while self.running:
                await self.scan_once()
                await asyncio.sleep(SCAN_INTERVAL_SECONDS)

        finally:
            self.running = False

    def stop(self):
        self.running = False


def utc_timestamp():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
