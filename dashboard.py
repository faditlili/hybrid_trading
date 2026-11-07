"""HTTP Basic-auth protected API engine endpoints for external GUI links."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
import config

security = HTTPBasic()
def require_auth(
    credentials: HTTPBasicCredentials = Depends(security)
):
    if not config.DASHBOARD_USERNAME or not config.DASHBOARD_PASSWORD:
        raise HTTPException(
            503, "Dynamic secure credentials are uninitialized."
        )
        
    u_ok = secrets.compare_digest(
        credentials.username, config.DASHBOARD_USERNAME
    )
    p_ok = secrets.compare_digest(
        credentials.password, config.DASHBOARD_PASSWORD
    )
    
    if not (u_ok and p_ok): 
        raise HTTPException(
            401, "Unauthorized core gateway access.", 
            headers={"WWW-Authenticate": "Basic"}
        )
    return True
def build_router(db, engine):
    r = APIRouter()
    
    @r.get("/dashboard/status", dependencies=[Depends(require_auth)])
    async def status(): 
        return {
            "engine": engine.status(), 
            "account": db.account(), 
            "positions": db.positions()
        }
    @r.get(
        "/dashboard/decisions", 
        dependencies=[Depends(require_auth)]
    )
    async def decisions(): 
        return db.recent("decisions")
    @r.get(
        "/dashboard/trades", 
        dependencies=[Depends(require_auth)]
    )
    async def trades(): 
        return db.recent("trades")
        
    return r
