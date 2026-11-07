"""Central non-blocking engine executing parallel trading routines."""
import asyncio
import logging
import config
from market_data import BingXMarketData
from technical_analysis import calculate_indicators
from decision_engine import calculate_technical_score, evaluate_setup
from ai_council import AICouncil
from news_engine import NewsEngine
from paper_trading import PaperTrader

log = logging.getLogger(__name__)
class Engine:
    def __init__(self, db):
        self.db = db
        self.market = BingXMarketData()
        self.ai = AICouncil()
        self.news = NewsEngine()
        self.paper = PaperTrader(db)
        self.running = False
        self.task = None
        self.lock = asyncio.Lock()
        self.last_scan = None
    async def start(self):
        await self.market.start()
        await self.ai.start()
        self.running = True
        self.task = asyncio.create_task(
            self._loop()
        )
        
    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            await asyncio.gather(
                self.task, 
                return_exceptions=True
            )
            self.task = None
        await self.ai.close()
        await self.market.close()
    async def scan_once(self):
        if self.lock.locked(): 
            return {"status": "scan running"}
            
        async with self.lock:
            if not self.news.items: 
                await self.news.refresh()
            prices = {}
            results = []
            async def process(symbol):
                try:
                    # 1. Check for consecutive losses
                    losses = (
                        self.db
                        .get_symbol_recent_loss_count(
                            symbol, hours=24
                        )
                    )
                    if losses >= 2:
                        return None
                        
                    # 2. Dynamic score scaling
                    win_rate = (
                        self.db
                        .get_overall_win_rate(
                            limit=20
                        )
                    )
                    min_score = (
                        config.MIN_SCORE_TO_ENTER
                    )
                    if win_rate < 0.45:
                        min_score += 6.0
                    elif win_rate > 0.60:
                        min_score = max(
                            68.0, min_score - 2.0
                        )

                    # 3. Macro sentiment safety breaker
                    if await (
                        self.news
                        .is_market_unsafe(symbol)
                    ):
                        self.db.log_event(
                            "WARNING",
                            f"Breaker tripped: "
                            f"{symbol}"
                        )
                        return None
                    snap = await (
                        self.market
                        .snapshot(symbol)
                    )
                    ind = calculate_indicators(
                        snap["candles"]
                    )
                    pr = snap["ticker"]["last"]
                    prices[symbol] = pr
                    
                    tech = calculate_technical_score(
                        ind
                    )
                    ai = await self.ai.analyze(
                        {
                            "symbol": symbol,
                            "indicators": ind,
                            "news": await (
                                self.news
                                .get_context()
                            )
                        }
                    )
                    dec = evaluate_setup(
                        tech, ai["vote"],
                        ai["agreement"],
                        min_score,
                        config.AI_MIN_AGREEMENT
                    )
                    
                    self.db.record_decision(
                        symbol, dec["action"],
                        dec["score"],
                        {
                            "technical": tech,
                            "ai": ai,
                            "reason": dec["reason"]
                        }
                    )
                    if dec["action"] == "PAPER_BUY":
                        self.paper.open_position(
                            symbol, pr, ind["atr"]
                        )
                    return {
                        "symbol": symbol,
                        "price": pr,
                        "decision": dec
                    }
                except Exception as e:
                    log.warning(
                        "Parallel failure "
                        f"for {symbol}: {e}"
                    )
                    return None
            tasks = [
                process(s) 
                for s in config.SYMBOLS
            ]
            res = await asyncio.gather(*tasks)
            results = [
                r for r in res 
                if r is not None
            ]
            self.paper.update(prices)
            
            dt = __import__("datetime")
            self.last_scan = (
                dt.datetime.now(
                    dt.timezone.utc
                ).isoformat()
            )
            return {
                "status": "ok",
                "results": results,
                "last_scan": self.last_scan
            }
    async def _loop(self):
        while self.running:
            try:
                await self.scan_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Loop failure")
            await asyncio.sleep(
                config.SCAN_INTERVAL_SECONDS
            )
            
    def status(self):
        return {
            "running": self.running,
            "last_scan": self.last_scan,
            "mode": "PAPER ONLY"
        }
