import math
import logging
import threading

from config import (
    INITIAL_BALANCE,
    RISK_PER_TRADE_PCT,
    MAX_ALLOCATION_PCT,
    FEE_RATE,
    SIMULATED_SLIPPAGE_BPS,
    STOP_ATR_MULTIPLIER,
    TARGET_R_MULTIPLIER,
    MAX_OPEN_POSITIONS
)

logger = logging.getLogger(__name__)


def valid_number(value):
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


class PaperTrader:

    def __init__(self, db):
        self.db = db
        self.lock = threading.RLock()

        account = self.db.get_account() or {}

        self.balance = float(
            account.get("balance", INITIAL_BALANCE)
        )

        self.realized_pnl = float(
            account.get("realized_pnl", 0)
        )

        self.live_marks = {}

    def _get_positions(self):
        positions = self.db.get_positions()
        return positions if isinstance(positions, list) else []

    def _slippage(self):
        return SIMULATED_SLIPPAGE_BPS / 10000

    def open_position(self, symbol, price, atr):

        with self.lock:

            if not isinstance(symbol, str) or not symbol:
                return False

            if not valid_number(price) or not valid_number(atr):
                return False

            price = float(price)
            atr = float(atr)

            if price <= 0 or atr <= 0:
                return False

            positions = self._get_positions()

            if any(p.get("symbol") == symbol for p in positions):
                return False

            if len(positions) >= MAX_OPEN_POSITIONS:
                return False

            stop_distance = atr * STOP_ATR_MULTIPLIER

            if stop_distance <= 0:
                return False

            risk_budget = self.balance * RISK_PER_TRADE_PCT
            max_allocation = self.balance * MAX_ALLOCATION_PCT

            quantity_by_risk = risk_budget / stop_distance
            quantity_by_allocation = max_allocation / price

            quantity = min(
                quantity_by_risk,
                quantity_by_allocation
            )

            if not valid_number(quantity) or quantity <= 0:
                return False

            entry_price = price * (1 + self._slippage())

            allocation = quantity * entry_price
            entry_fee = allocation * FEE_RATE
            total_cost = allocation + entry_fee

            if total_cost > self.balance:
                return False

            stop_loss = entry_price - stop_distance

            take_profit = (
                entry_price
                + stop_distance * TARGET_R_MULTIPLIER
            )

            if stop_loss <= 0 or take_profit <= entry_price:
                return False

            new_balance = self.balance - total_cost

            position = {
                "symbol": symbol,
                "quantity": quantity,
                "entry_price": entry_price,
                "allocation": allocation,
                "entry_fee": entry_fee,
                "stop_loss": stop_loss,
                "take_profit": take_profit
            }

            success = self.db.open_position_atomic(
                position,
                new_balance
            )

            if not success:
                return False

            self.balance = new_balance

            self.live_marks[symbol] = {
                "current_price": entry_price,
                "unrealized_pnl": 0.0
            }

            logger.info("Paper position opened: %s", symbol)
            return True

    def close_position(self, symbol, price, reason=""):

        with self.lock:

            if not valid_number(price):
                return False

            price = float(price)

            if price <= 0:
                return False

            positions = self._get_positions()

            position = next(
                (p for p in positions if p.get("symbol") == symbol),
                None
            )

            if not position:
                return False

            quantity = float(position.get("quantity", 0))
            entry_price = float(position.get("entry_price", 0))
            allocation = float(position.get("allocation", 0))
            entry_fee = float(position.get("entry_fee", 0))

            if quantity <= 0 or entry_price <= 0:
                return False

            exit_price = price * (1 - self._slippage())

            exit_value = quantity * exit_price
            exit_fee = exit_value * FEE_RATE

            gross_pnl = exit_value - allocation
            net_pnl = gross_pnl - entry_fee - exit_fee

            new_balance = self.balance + exit_value - exit_fee
            new_realized = self.realized_pnl + net_pnl

            trade = {
                "quantity": quantity,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "gross_pnl": gross_pnl,
                "net_pnl": net_pnl,
                "entry_fee": entry_fee,
                "exit_fee": exit_fee,
                "reason": str(reason)[:200]
            }

            success = self.db.close_position_atomic(
                symbol,
                trade,
                new_balance,
                new_realized
            )

            if not success:
                return False

            self.balance = new_balance
            self.realized_pnl = new_realized

            self.live_marks.pop(symbol, None)

            logger.info(
                "Paper position closed: %s | PnL: %.6f",
                symbol,
                net_pnl
            )

            return True

    async def update_positions(self, market):

        positions = self._get_positions()

        for position in positions:

            symbol = position.get("symbol")

            if not symbol:
                continue

            try:

                ticker = await market.get_ticker(symbol)

                if not isinstance(ticker, dict):
                    continue

                price = ticker.get("price")

                if not valid_number(price):
                    continue

                price = float(price)

                if price <= 0:
                    continue

                quantity = float(position.get("quantity", 0))
                allocation = float(position.get("allocation", 0))
                entry_fee = float(position.get("entry_fee", 0))

                if quantity <= 0:
                    continue

                current_value = quantity * price

                unrealized_pnl = (
                    current_value
                    - allocation
                    - entry_fee
                    - current_value * FEE_RATE
                )

                with self.lock:
                    self.live_marks[symbol] = {
                        "current_price": price,
                        "unrealized_pnl": unrealized_pnl
                    }

                stop_loss = float(position.get("stop_loss", 0))
                take_profit = float(position.get("take_profit", 0))

                if stop_loss > 0 and price <= stop_loss:

                    self.close_position(
                        symbol,
                        price,
                        "Stop loss"
                    )

                elif take_profit > 0 and price >= take_profit:

                    self.close_position(
                        symbol,
                        price,
                        "Take profit"
                    )

            except Exception:

                logger.exception(
                    "Position update failed for %s",
                    symbol
                )

    def get_summary(self):

        with self.lock:

            positions = self._get_positions()

            for position in positions:

                symbol = position.get("symbol")
                mark = self.live_marks.get(symbol)

                if mark:
                    position["current_price"] = mark["current_price"]
                    position["unrealized_pnl"] = mark["unrealized_pnl"]
                else:
                    position["current_price"] = position.get(
                        "entry_price", 0
                    )
                    position["unrealized_pnl"] = 0.0

            reserved = sum(
                float(p.get("allocation", 0))
                for p in positions
            )

            unrealized_pnl = sum(
                float(p.get("unrealized_pnl", 0))
                for p in positions
            )

            equity = self.balance + reserved + unrealized_pnl

            trades = self.db.get_recent_trades(500)

            wins = sum(
                1 for trade in trades
                if float(trade.get("net_pnl", 0)) > 0
            )

            total = len(trades)

            win_rate = (
                wins / total * 100
                if total else 0.0
            )

            return {
                "balance": self.balance,
                "equity": equity,
                "realized_pnl": self.realized_pnl,
                "unrealized_pnl": unrealized_pnl,
                "reserved": reserved,
                "positions": positions,
                "win_rate": win_rate
            }
