from fastapi import APIRouter
from datetime import datetime, timezone
from config import APP_NAME, APP_VERSION, PAPER_MODE, PORTFOLIO_EXPOSURE_LIMIT

def build_router(db,engine):
    r=APIRouter()
    @r.get("/health")
    async def health():
        return {"status":"ok","app":APP_NAME,"version":APP_VERSION,"paper_mode":PAPER_MODE,"time":datetime.now(timezone.utc).isoformat()}
    @r.get("/dashboard/status")
    async def status():
        account=db.account(); positions=db.positions(); prices={}
        prices=engine.last_prices
        equity=engine.paper.equity(prices); exposure=engine.paper.exposure(prices)
        return {"app":APP_NAME,"version":APP_VERSION,"paper_mode":True,"cash":account["cash"],"equity":equity,"realized_pnl":account["realized_pnl"],"open_positions":len(positions),"exposure":exposure,"exposure_limit":equity*PORTFOLIO_EXPOSURE_LIMIT,"last_scan":engine.last_scan,"last_error":engine.last_error}
    @r.get("/dashboard/positions")
    async def positions(): return db.positions()
    @r.get("/dashboard/trades")
    async def trades(): return db.recent("trades",100)
    @r.get("/dashboard/decisions")
    async def decisions(): return db.recent("decisions",100)
    @r.get("/dashboard/events")
    async def events(): return db.recent("events",100)
    return r
