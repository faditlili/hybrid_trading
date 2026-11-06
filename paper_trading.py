from datetime import datetime, timezone

from config import (
    INITIAL_BALANCE,
    MAX_OPEN_POSITIONS,
    MAX_ALLOCATION_PCT,
    RISK_PER_TRADE_PCT,
    FEE_RATE,
    SIMULATED_SLIPPAGE_BPS,
    STOP_ATR_MULTIPLIER,
    TARGET_R_MULTIPLIER
)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class PaperTrader:

    def __init__(self, database):
        self.db = database

        account = self.db.account()

        self.balance = float(account["balance"])
        self.realized_pnl = float(account["realized_pnl"])
        self.wins = int(account["wins"])
        self.losses = int(account["losses"])

        self.positions = {
            p["symbol"]: p
            for p in self.db.positions()
        }

        self.last_prices = {}

    def _save_account(self):
        self.db.update_account(
            self.balance,
            self.realized_pnl,
            self.wins,
            self.losses
        )

    def open_position(self, symbol, price, atr):

        if symbol in self.positions:
            return False, "Position already exists"

        if len(self.positions) >= MAX_OPEN_POSITIONS:
            return False, "Maximum positions reached"

        if price <= 0 or atr <= 0 or self.balance <= 0:
            return False, "Invalid market data"

        stop_distance = atr * STOP_ATR_MULTIPLIER

        risk_budget = self.balance * RISK_PER_TRADE_PCT
        max_allocation = self.balance * MAX_ALLOCATION_PCT

        quantity_by_risk = risk_budget / stop_distance
        quantity_by_allocation = max_allocation / price

        quantity = min(
            quantity_by_risk,
            quantity_by_allocation
        )

        if quantity <= 0:
            return False, "Invalid position quantity"

        entry = price * (
            1 + SIMULATED_SLIPPAGE_BPS / 10000
        )

        allocation = quantity * entry
        entry_fee = allocation * FEE_RATE

        total_cost = allocation + entry_fee

        if total_cost > self.balance:
            return False, "Insufficient virtual balance"

        stop = entry - stop_distance

        target = entry + (
            stop_distance * TARGET_R_MULTIPLIER
        )

        position = {
            "symbol": symbol,
            "side": "LONG",
            "quantity": quantity,
            "entry": entry,
            "stop": stop,
            "target": target,
            "allocation": allocation,
            "entry_fee": entry_fee,
            "opened_at": utc_now()
        }

        self.balance -= total_cost

        self.positions[symbol] = position
        self.last_prices[symbol] = price

        self.db.add_position(position)
        self._save_account()

        return True, position

    def close_position(self, symbol, market_price, reason):

        position = self.positions.get(symbol)

        if not position:
            return False, "Position not found"

        if market_price <= 0:
            return False, "Invalid exit price"

        exit_price = market_price * (
            1 - SIMULATED_SLIPPAGE_BPS / 10000
        )

        quantity = position["quantity"]
        entry = position["entry"]

        gross_pnl = (exit_price - entry) * quantity

        exit_fee = exit_price * quantity * FEE_RATE

        net_pnl = (
            gross_pnl
            - exit_fee
            - position["entry_fee"]
        )

        self.balance += (
            position["allocation"]
            + gross_pnl
            - exit_fee
        )

        self.realized_pnl += net_pnl

        if net_pnl >= 0:
            self.wins += 1
        else:
            self.losses += 1

        trade = {
            "symbol": symbol,
            "side": "LONG",
            "entry": entry,
            "exit": exit_price,
            "quantity": quantity,
            "pnl": net_pnl,
            "reason": reason,
            "opened_at": position["opened_at"],
            "closed_at": utc_now()
        }

        self.db.add_trade(trade)
        self.db.remove_position(symbol)

        del self.positions[symbol]
        self.last_prices.pop(symbol, None)

        self._save_account()

        return True, trade

    async def update_positions(self, market_data):

        results = []

        for symbol in list(self.positions.keys()):

            try:
                ticker = await market_data.get_ticker(symbol)
                price = ticker["price"]

                self.last_prices[symbol] = price

                position = self.positions[symbol]

                if price <= position["stop"]:

                    ok, result = self.close_position(
                        symbol,
                        price,
                        "STOP_LOSS"
                    )

                    results.append((symbol, ok, result))

                elif price >= position["target"]:

                    ok, result = self.close_position(
                        symbol,
                        price,
                        "TAKE_PROFIT"
                    )

                    results.append((symbol, ok, result))

            except Exception as exc:

                results.append((
                    symbol,
                    False,
                    f"Monitoring error: {str(exc)[:200]}"
                ))

        return results

    def summary(self):

        reserved = sum(
            p["allocation"]
            for p in self.positions.values()
        )

        unrealized = sum(
            (
                self.last_prices.get(symbol, p["entry"])
                - p["entry"]
            ) * p["quantity"]
            for symbol, p in self.positions.items()
        )

        equity = (
            self.balance
            + reserved
            + unrealized
        )

        return {
            "available_balance": self.balance,
            "reserved_allocation": reserved,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": unrealized,
            "equity": equity,
            "wins": self.wins,
            "losses": self.losses,
            "open_positions": len(self.positions),
            "initial_balance": INITIAL_BALANCE
        }
