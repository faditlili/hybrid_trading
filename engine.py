"""Async orchestration for market data, analysis, and paper simulation."""
import asyncio, logging
from datetime import datetime, timezone
from config import SYMBOLS, TIMEFRAMES, SCAN_INTERVAL_SECONDS
from market_data import BingXMarketData
from technical_analysis import calculate_indicators
from ai_council import AICouncil
from news_engine import NewsEngine
from decision_engine import evaluate_setup
from paper_trading import PaperTrader
logger=logging.getLogger(__name__)

class TradingEngine:
    def __init__(self,db):
        self.db=db; self.market=BingXMarketData(); self.ai=AICouncil(); self.news=NewsEngine(); self.paper=PaperTrader(db)
        self.running=False; self.task=None; self.last_scan=None; self.last_error=None; self.last_prices={}; self.scan_lock=asyncio.Lock()
    async def start(self):
        await self.market.start(); await self.ai.start(); await self.news.start(); self.running=True
        if self.task is None or self.task.done(): self.task=asyncio.create_task(self.run_loop())
    async def stop(self):
        self.running=False
        if self.task: self.task.cancel(); await asyncio.gather(self.task,return_exceptions=True); self.task=None
        await self.market.close(); await self.ai.close(); await self.news.close()
    async def scan_once(self):
        async with self.scan_lock:
            prices={}; results=[]; market_errors={}
            # Fetch all current marks first so the 10% aggregate cap uses the
            # same current portfolio valuation for every candidate in this scan.
            for symbol in SYMBOLS:
                try:
                    prices[symbol]=(await self.market.ticker(symbol))["last"]
                except Exception as exc:
                    market_errors[symbol]=str(exc)
            for symbol in SYMBOLS:
                if symbol not in prices:
                    self.last_error=f"{symbol}: {market_errors.get(symbol, 'ticker unavailable')}"
                    self.db.log_event("ERROR",self.last_error,datetime.now(timezone.utc).isoformat())
                    continue
                try:
                    frames={}
                    for tf in TIMEFRAMES:
                        candles=await self.market.klines(symbol,tf)
                        frames[tf]=calculate_indicators(candles)
                    blocked=await self.news.blocks(symbol)
                    ai=await self.ai.vote({"symbol":symbol,"frames":frames})
                    decision=evaluate_setup(frames,ai["vote"],ai["agreement"],blocked)
                    self.db.record_decision(symbol,decision["action"],decision["score"],decision["reason"],datetime.now(timezone.utc).isoformat())
                    if decision["action"]=="PAPER_BUY_CANDIDATE":
                        opened=self.paper.open_position(symbol,prices[symbol],frames["15m"]["atr"],prices=prices)
                        decision["opened"]=opened
                    results.append({"symbol":symbol,**decision,"ai":ai})
                except Exception as exc:
                    self.last_error=f"{symbol}: {exc}"; logger.exception("Scan failed for %s",symbol)
                    self.db.log_event("ERROR",self.last_error,datetime.now(timezone.utc).isoformat())
            self.last_prices=prices.copy(); self.paper.update(prices); self.last_scan=datetime.now(timezone.utc).isoformat()
            if results and not market_errors: self.last_error=None
            return results
    async def run_loop(self):
        while self.running:
            try: await self.scan_once()
            except asyncio.CancelledError: raise
            except Exception as exc: self.last_error=str(exc); logger.exception("Engine loop error")
            await asyncio.sleep(SCAN_INTERVAL_SECONDS)
