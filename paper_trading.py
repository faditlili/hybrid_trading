"""Simulated portfolio tracking capital compounding and partial targets."""
import math
import time
import config
class PaperTrader:
    def __init__(self, db):
        self.db = db
    def open_position(self, symbol, price, atr):
        a = self.db.account()
        positions = self.db.positions()
        
        if len(positions) >= config.MAX_OPEN_POSITIONS: 
            return False
        if any(p["symbol"] == symbol for p in positions): 
            return False
            
        price, atr = float(price), float(atr)
        if not math.isfinite(price) or price <= 0 or atr <= 0: 
            return False
        
        stop = price - 2 * atr
        target = price + 4 * atr
        # Linear compounding calculation loop based on current active equity
        risk_cash = a["equity"] * config.RISK_PER_TRADE
        qty = risk_cash / (price - stop)
        notional = qty * price
        
        cap = min(
            a["balance"] * config.MAX_ALLOCATION, 
            a["equity"] * config.MAX_ALLOCATION
        )
        fee = notional * config.FEE_RATE
        if (
            notional + fee > cap 
            or notional + fee > a["balance"]
        ):
            max_cap = min(cap, a["balance"])
            qty = max(
                0, 
                (max_cap / (1 + config.FEE_RATE)) 
                / price
            )
            notional = qty * price
            fee = notional * config.FEE_RATE
            
        if qty <= 0 or notional + fee > a["balance"]: 
            return False
        with self.db.lock:
            c = self.db.conn
            c.execute(
                "INSERT INTO positions(symbol, "
                "entry, qty, stop, target, "
                "entry_fee, opened, status) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, 'OPEN')", 
                (symbol, price, qty, stop, 
                 target, fee, time.time())
            )
            c.execute(
                "UPDATE account SET "
                "balance=balance-? WHERE id=1", 
                (notional + fee,)
            )
            c.commit()
        return True
    def update(self, prices):
        closed = []
        with self.db.lock:
            for p in self.db.positions():
                price = float(
                    prices.get(p["symbol"], 0) 
                    or 0
                )
                if price <= 0: 
                    continue
                
                atr_unit = (
                    (p["target"] - p["entry"]) 
                    / 4
                )
                tp1 = p["entry"] + 2 * atr_unit
                # Partial profit take trigger matrix
                if price >= tp1 and p["entry_fee"] > 0:
                    fill = tp1 * (
                        1 - config.SLIPPAGE_BPS 
                        / 10000
                    )
                    gross = (
                        (fill - p["entry"]) 
                        * (p["qty"] * 0.5)
                    )
                    fee = (
                        fill * (p["qty"] * 0.5) 
                        * config.FEE_RATE
                    )
                    pnl = gross - fee
                    
                    c = self.db.conn
                    c.execute(
                        "UPDATE positions SET "
                        "qty=qty*0.5, stop=?, "
                        "entry_fee=0 WHERE id=?", 
                        (p["entry"], p["id"])
                    )
                    c.execute(
                        "UPDATE account SET "
                        "balance=balance+?, "
                        "realized_pnl=realized_pnl+? "
                        "WHERE id=1", 
                        (fill * (p["qty"] * 0.5) 
                         - fee, pnl)
                    )
                    c.execute(
                        "INSERT INTO trades(symbol, "
                        "side, price, qty, pnl, "
                        "created) "
                        "VALUES(?, 'SELL_PARTIAL', "
                        "?, ?, ?, ?)", 
                        (p["symbol"], fill, 
                         p["qty"] * 0.5, pnl, 
                         time.time())
                    )
                    c.commit()
                    continue
                # Final stop loss and take profit validation gates
                if (
                    price <= p["stop"] 
                    or price >= p["target"]
                ):
                    if price <= p["stop"]:
                        trigger = p["stop"]
                    else:
                        trigger = p["target"]
                        
                    fill = trigger * (
                        1 - config.SLIPPAGE_BPS 
                        / 10000
                    )
                    gross = (
                        (fill - p["entry"]) 
                        * p["qty"]
                    )
                    fee = (
                        fill * p["qty"] 
                        * config.FEE_RATE
                    )
                    pnl = (
                        gross 
                        - float(p["entry_fee"]) 
                        - fee
                    )
                    c = self.db.conn
                    c.execute(
                        "UPDATE positions SET "
                        "status='CLOSED' WHERE id=?", 
                        (p["id"],)
                    )
                    c.execute(
                        "UPDATE account SET "
                        "balance=balance+?, "
                        "equity=equity+?, "
                        "realized_pnl=realized_pnl+? "
                        "WHERE id=1", 
                        (fill * p["qty"] - fee, 
                         pnl, pnl)
                    )
                    c.execute(
                        "INSERT INTO trades(symbol, "
                        "side, price, qty, pnl, "
                        "created) "
                        "VALUES(?, 'SELL_FINAL', "
                        "?, ?, ?, ?)", 
                        (p["symbol"], fill, 
                         p["qty"], pnl, 
                         time.time())
                    )
                    c.commit()
                    closed.append({
                        "symbol": p["symbol"], 
                        "pnl": pnl
                    })
        return closed
