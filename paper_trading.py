import math
import logging

from config import (
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
    except (TypeError, ValueError):
        return False


class PaperTrader:

    def __init__(self, db):

        self.db = db

        account = self.db.get_account()

        self.balance = float(account["balance"])
        self.realized_pnl = float(account["realized_pnl"])
        self.wins = int(account["wins"])
        self.losses = int(account["losses"])

        self.positions = {
            position["symbol"]: position
            for position in self.db.get_positions()
        }

        self.last_prices = {}

    def _save_open(self, position):

        return self.db.open_position_atomic(
            position=position,
            balance=self.balance,
            realized_pnl=self.realized_pnl,
            wins=self.wins,
            losses=self.losses
        )

    def _save_close(self, symbol, trade):

        return self.db.close_position_atomic(
            symbol=symbol,
            trade=trade,
            balance=self.balance,
            realized_pnl=self.realized_pnl,
            wins=self.wins,
            losses=self.losses
        )

    def open_position(self, symbol, price, atr):

        if symbol in self.positions:
            return False

        if len(self.positions) >= MAX_OPEN_POSITIONS:
            return False

        if not valid_number(price) or not valid_number(atr):
            return False

        price = float(price)
        atr = float(atr)

        if price <= 0 or atr <= 0 or self.balance <= 0:
            return False

        stop_distance = atr * STOP_ATR_MULTIPLIER

        if stop_distance <= 0:
            return False

        risk_budget = self.balance * RISK_PER_TRADE_PCT

        max_allocation = self.balance * MAX_ALLOCATION_PCT

        quantity = min(
            risk_budget / stop_distance,
            max_allocation / price
        )

        if not valid_number(quantity) or quantity <= 0:
            return False

        slippage = SIMULATED_SLIPPAGE_BPS / 10000

        entry_price = price * (1 + slippage)

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

        position = {
            "symbol": symbol,
            "quantity": quantity,
            "entry_price": entry_price,
            "allocation": allocation,
            "entry_fee": entry_fee,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "entry_value": allocation
        }

        new_balance = self.balance - total_cost

        if not self.db.open_position_atomic(
            position=position,
            balance=new_balance,
            realized_pnl=self.realized_pnl,
            wins=self.wins,
            losses=self.losses
        ):
            logger.error(
                "Database rejected opening position: %s",
                symbol
            )
            return False

        self.balance = new_balance
        self.positions[symbol] = position
        self.last_prices[symbol] = price

        logger.info(
            "Paper position opened: %s",
            symbol
        )

        return True

    def close_position(self, symbol, price, reason="MANUAL"):

        position = self.positions.get(symbol)

        if not position:
            return False

        if not valid_number(price):
            return False

        price = float(price)

        if price <= 0:
            return False

        slippage = SIMULATED_SLIPPAGE_BPS / 10000

        exit_price = price * (1 - slippage)

        quantity = float(position["quantity"])

        allocation = float(position["allocation"])

        entry_fee = float(position["entry_fee"])

        gross_pnl = (
            exit_price - float(position["entry_price"])
        ) * quantity

        exit_fee = exit_price * quantity * FEE_RATE

        net_pnl = gross_pnl - entry_fee - exit_fee

        new_balance = (
            self.balance
            + allocation
            + gross_pnl
            - exit_fee
        )

        new_realized = self.realized_pnl + net_pnl

        new_wins = self.wins + (1 if net_pnl > 0 else 0)

        new_losses = self.losses + (1 if net_pnl <= 0 else 0)

        trade = {
            "symbol": symbol,
            "entry_price": float(position["entry_price"]),
            "exit_price": exit_price,
            "quantity": quantity,
            "gross_pnl": gross_pnl,
            "net_pnl": net_pnl,
            "entry_fee": entry_fee,
            "exit_fee": exit_fee,
            "reason": str(reason)
        }

        if not self.db.close_position_atomic(
            symbol=symbol,
            trade=trade,
            balance=new_balance,
            realized_pnl=new_realized,
            wins=new_wins,
            losses=new_losses
        ):
            logger.error(
                "Database rejected closing position: %s",
                symbol
            )
            return False

        self.balance = new_balance
        self.realized_pnl = new_realized
        self.wins = new_wins
        self.losses = new_losses

        del self.positions[symbol]
        self.last_prices.pop(symbol, None)

        logger.info(
            "Paper position closed: %s | PnL: %.4f",
            symbol,
            net_pnl
        )

        return True

    async def update_positions(self, market):

        for symbol in list(self.positions.keys()):

            try:

                ticker = await market.get_ticker(symbol)

                price = float(ticker["price"])

                if not valid_number(price) or price <= 0:
                    continue

                self.last_prices[symbol] = price

                position = self.positions[symbol]

                if price <= float(position["stop_loss"]):

                    self.close_position(
                        symbol,
                        price,
                        "STOP_LOSS"
                    )

                elif price >= float(position["take_profit"]):

                    self.close_position(
                        symbol,
                        price,
                        "TAKE_PROFIT"
                    )

            except Exception as exc:

                logger.warning(
                    "Position monitoring failed for %s: %s",
                    symbol,
                    str(exc)[:200]
                )

    def get_summary(self):

        reserved = sum(
            float(position["allocation"])
            for position in self.positions.values()
        )

        unrealized = 0.0
        positions_data = []

        for symbol, position in self.positions.items():

            price = self.last_prices.get(
                symbol,
                float(position["entry_price"])
            )

            quantity = float(position["quantity"])

            entry_price = float(position["entry_price"])

            entry_fee = float(position["entry_fee"])

            exit_fee_estimate = (
                price * quantity * FEE_RATE
            )

            gross = (price - entry_price) * quantity

            net = gross - entry_fee - exit_fee_estimate

            unrealized += net

            positions_data.append({
                **position,
                "symbol": symbol,
                "current_price": price,
                "unrealized_pnl": net
            })

        estimated_equity = (
            self.balance
            + reserved
            + sum(
                (
                    float(self.last_prices.get(
                        symbol,
                        float(position["entry_price"])
                    ))
                    - float(position["entry_price"])
                ) * float(position["quantity"])
                - float(self.last_prices.get(
                    symbol,
                    float(position["entry_price"])
                )) * float(position["quantity"]) * FEE_RATE
                for symbol, position in self.positions.items()
            )
        )

        total_trades = self.wins + self.losses

        win_rate = (
            self.wins / total_trades * 100
            if total_trades
            else 0.0
        )

        return {
            "balance": self.balance,
            "reserved": reserved,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": unrealized,
            "equity": estimated_equity,
            "wins": self.wins,
            "losses": self.losses,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "positions": positions_data
        }
