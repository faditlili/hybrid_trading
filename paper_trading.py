"""Paper-only portfolio accounting. No exchange order functionality exists here."""
from datetime import datetime, timezone
import math
from config import PORTFOLIO_EXPOSURE_LIMIT, MAX_OPEN_POSITIONS, FEE_RATE, SLIPPAGE_BPS, STOP_ATR_MULTIPLIER, TARGET_R_MULTIPLIER

class PaperTrader:
    def __init__(self, db): self.db=db
    @staticmethod
    def now(): return datetime.now(timezone.utc).isoformat()
    def equity(self, prices=None):
        a=self.db.account(); positions=self.db.positions(); prices=prices or {}
        return a["cash"]+sum(p["qty"]*float(prices.get(p["symbol"],p["entry"])) for p in positions)
    def exposure(self, prices=None):
        prices=prices or {}; return sum(p["qty"]*float(prices.get(p["symbol"],p["entry"])) for p in self.db.positions())
    def open_position(self,symbol,price,atr,prices=None):
        if not all(math.isfinite(float(x)) and float(x)>0 for x in (price,atr)): return False
        price=float(price); atr=float(atr); positions=self.db.positions()
        if len(positions)>=MAX_OPEN_POSITIONS or any(p["symbol"]==symbol for p in positions): return False
        prices=prices or {}; equity=self.equity(prices); cap=equity*PORTFOLIO_EXPOSURE_LIMIT; remaining=cap-self.exposure(prices)
        fill=price*(1+SLIPPAGE_BPS/10000); stop=fill-STOP_ATR_MULTIPLIER*atr
        if stop<=0 or remaining<=0: return False
        # Solve the cap against post-fee equity, not pre-entry equity.
        notional=remaining/(1+PORTFOLIO_EXPOSURE_LIMIT*FEE_RATE)
        qty=notional/fill; fee=notional*FEE_RATE
        account=self.db.account()
        if notional+fee>account["cash"]:
            notional=account["cash"]/(1+FEE_RATE); qty=notional/fill; fee=notional*FEE_RATE
        if qty<=0 or notional<1: return False
        target=fill+(fill-stop)*TARGET_R_MULTIPLIER
        with self.db.lock:
            try:
                self.db.conn.execute("BEGIN IMMEDIATE")
                self.db.conn.execute("UPDATE account SET cash=cash-? WHERE id=1",(notional+fee,))
                self.db.conn.execute("INSERT INTO positions(symbol,qty,entry,stop,target,notional,entry_fee,opened_at) VALUES(?,?,?,?,?,?,?,?)",(symbol,qty,fill,stop,target,notional,fee,self.now()))
                self.db.conn.execute("INSERT INTO trades(symbol,side,qty,price,pnl,fee,created_at,reason) VALUES(?,?,?,?,?,?,?,?)",(symbol,"PAPER_BUY",qty,fill,0,fee,self.now(),"paper simulation entry"))
                self.db.conn.commit(); return True
            except Exception:
                self.db.conn.rollback(); raise
    def update(self, prices):
        closed=[]
        for p in self.db.positions():
            price=prices.get(p["symbol"])
            if price is None or not math.isfinite(float(price)): continue
            price=float(price)
            if price<=p["stop"] or price>=p["target"]:
                fill=price*(1-SLIPPAGE_BPS/10000); gross=(fill-p["entry"])*p["qty"]; fee=fill*p["qty"]*FEE_RATE; pnl=gross-p["entry_fee"]-fee
                with self.db.lock:
                    try:
                        self.db.conn.execute("BEGIN IMMEDIATE")
                        self.db.conn.execute("UPDATE account SET cash=cash+?,realized_pnl=realized_pnl+? WHERE id=1",(fill*p["qty"]-fee,pnl))
                        self.db.conn.execute("DELETE FROM positions WHERE id=?",(p["id"],))
                        self.db.conn.execute("INSERT INTO trades(symbol,side,qty,price,pnl,fee,created_at,reason) VALUES(?,?,?,?,?,?,?,?)",(p["symbol"],"PAPER_SELL",p["qty"],fill,pnl,fee,self.now(),"stop/target simulation"))
                        self.db.conn.commit(); closed.append({"symbol":p["symbol"],"pnl":pnl})
                    except Exception: self.db.conn.rollback(); raise
        return closed
