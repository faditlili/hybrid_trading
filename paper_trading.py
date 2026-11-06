import asyncio
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
    MAX_OPEN_POSITIONS,
)


logger = logging.getLogger(__name__)


def valid_number(value):
    if isinstance(value, bool):
        return False

    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def safe_float(value, default=0.0):
    if valid_number(value):
        return float(value)

    if default is None:
        return None

    if valid_number(default):
        return float(default)

    return 0.0


class PaperTrader:

    def __init__(self, db):

        self.db = db
        self.lock = threading.RLock()
        self.update_lock = asyncio.Lock()

        self._validate_config()

        account = self.db.get_account()

        if not isinstance(account, dict):
            raise RuntimeError("Unable to load paper account")

        if (
            not valid_number(account.get("balance"))
            or not valid_number(account.get("realized_pnl"))
        ):
            raise RuntimeError("Invalid paper account data")

        self.balance = float(account["balance"])
        self.realized_pnl = float(account["realized_pnl"])

        if self.balance < 0:
            raise ValueError("Account balance cannot be negative")

        self.live_marks = {}

    def _validate_config(self):

        checks = [
            (INITIAL_BALANCE, "INITIAL_BALANCE", lambda x: x > 0),
            (RISK_PER_TRADE_PCT, "RISK_PER_TRADE_PCT",
             lambda x: 0 < x <= 1),
            (MAX_ALLOCATION_PCT, "MAX_ALLOCATION_PCT",
             lambda x: 0 < x <= 1),
            (FEE_RATE, "FEE_RATE", lambda x: 0 <= x < 1),
            (SIMULATED_SLIPPAGE_BPS, "SIMULATED_SLIPPAGE_BPS",
             lambda x: 0 <= x < 10000),
            (STOP_ATR_MULTIPLIER, "STOP_ATR_MULTIPLIER",
             lambda x: x > 0),
            (TARGET_R_MULTIPLIER, "TARGET_R_MULTIPLIER",
             lambda x: x > 0),
        ]

        for value, name, condition in checks:
            if (
                not valid_number(value)
                or not condition(float(value))
            ):
                raise ValueError(f"Invalid configuration: {name}")

        if (
            isinstance(MAX_OPEN_POSITIONS, bool)
            or not isinstance(MAX_OPEN_POSITIONS, int)
            or MAX_OPEN_POSITIONS < 1
        ):
            raise ValueError("Invalid MAX_OPEN_POSITIONS")

    def _get_positions(self):

        positions = self.db.get_positions()

        if not isinstance(positions, list):
            raise RuntimeError(
                "Invalid positions returned by database"
            )

        result = []

        for position in positions:
            if not isinstance(position, dict):
                raise RuntimeError(
                    "Database returned an invalid position"
                )

            result.append(dict(position))

        return result

    def _validate_position(self, position):

        if not isinstance(position, dict):
            return False

        symbol = position.get("symbol")

        if not isinstance(symbol, str) or not symbol.strip():
            return False

        quantity = position.get("quantity")
        entry_price = position.get("entry_price")
        allocation = position.get("allocation")
        entry_fee = position.get("entry_fee")

        if not all(
            valid_number(value)
            for value in (
                quantity,
                entry_price,
                allocation,
                entry_fee,
            )
        ):
            return False

        quantity = float(quantity)
        entry_price = float(entry_price)
        allocation = float(allocation)
        entry_fee = float(entry_fee)

        if (
            quantity <= 0
            or entry_price <= 0
            or allocation <= 0
            or entry_fee < 0
        ):
            return False

        return math.isclose(
            quantity * entry_price,
            allocation,
            rel_tol=1e-8,
            abs_tol=1e-8,
        )

    def _slippage(self):

        return float(SIMULATED_SLIPPAGE_BPS) / 10000.0

    def _calculate_position_size(self, price, stop_distance):

        slippage = self._slippage()
        fee_rate = float(FEE_RATE)

        entry_price = price * (1.0 + slippage)
        stop_loss = entry_price - stop_distance

        if (
            not valid_number(entry_price)
            or not valid_number(stop_loss)
            or entry_price <= 0
            or stop_loss <= 0
        ):
            return None

        estimated_stop_exit = stop_loss * (1.0 - slippage)

        entry_fee_per_unit = entry_price * fee_rate
        exit_fee_per_unit = estimated_stop_exit * fee_rate

        estimated_loss_per_unit = (
            entry_price
            - estimated_stop_exit
            + entry_fee_per_unit
            + exit_fee_per_unit
        )

        if (
            not valid_number(estimated_loss_per_unit)
            or estimated_loss_per_unit <= 0
        ):
            return None

        risk_budget = self.balance * float(RISK_PER_TRADE_PCT)
        max_allocation = self.balance * float(MAX_ALLOCATION_PCT)

        quantity_by_risk = risk_budget / estimated_loss_per_unit
        quantity_by_allocation = max_allocation / entry_price

        quantity = min(
            quantity_by_risk,
            quantity_by_allocation,
        )

        if not valid_number(quantity) or quantity <= 0:
            return None

        return {
            "quantity": quantity,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
        }

    def open_position(self, symbol, price, atr):

        with self.lock:

            if not isinstance(symbol, str):
                return False

            symbol = symbol.strip().upper()

            if not symbol:
                return False

            if (
                not valid_number(price)
                or not valid_number(atr)
            ):
                return False

            price = float(price)
            atr = float(atr)

            if price <= 0 or atr <= 0:
                return False

            if (
                not valid_number(self.balance)
                or self.balance <= 0
            ):
                return False

            try:
                positions = self._get_positions()
            except Exception:
                logger.exception(
                    "Unable to read positions before opening %s",
                    symbol,
                )
                return False

            if any(
                str(p.get("symbol", "")).strip().upper() == symbol
                for p in positions
            ):
                return False

            if len(positions) >= MAX_OPEN_POSITIONS:
                return False

            stop_distance = atr * float(STOP_ATR_MULTIPLIER)

            if (
                not valid_number(stop_distance)
                or stop_distance <= 0
            ):
                return False

            sizing = self._calculate_position_size(
                price,
                stop_distance,
            )

            if not isinstance(sizing, dict):
                return False

            quantity = sizing["quantity"]
            entry_price = sizing["entry_price"]
            stop_loss = sizing["stop_loss"]

            allocation = quantity * entry_price
            entry_fee = allocation * float(FEE_RATE)
            total_cost = allocation + entry_fee

            if (
                not all(valid_number(v) for v in (
                    allocation,
                    entry_fee,
                    total_cost,
                ))
                or allocation <= 0
                or total_cost <= 0
                or total_cost > self.balance
            ):
                return False

            take_profit = (
                entry_price
                + stop_distance * float(TARGET_R_MULTIPLIER)
            )

            if (
                not valid_number(take_profit)
                or take_profit <= entry_price
            ):
                return False

            new_balance = self.balance - total_cost

            if not valid_number(new_balance) or new_balance < 0:
                return False

            position = {
                "symbol": symbol,
                "quantity": quantity,
                "entry_price": entry_price,
                "allocation": allocation,
                "entry_fee": entry_fee,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
            }

            try:
                success = self.db.open_position_atomic(
                    position,
                    new_balance,
                )
            except Exception:
                logger.exception(
                    "Database error while opening %s",
                    symbol,
                )
                return False

            if not success:
                return False

            self.balance = new_balance

            self.live_marks[symbol] = {
                "current_price": entry_price,
                "unrealized_pnl": 0.0,
            }

            logger.info("Paper position opened: %s", symbol)

            return True

    def close_position(self, symbol, price, reason=""):

        with self.lock:

            if not isinstance(symbol, str):
                return False

            symbol = symbol.strip().upper()

            if not symbol or not valid_number(price):
                return False

            price = float(price)

            if price <= 0:
                return False

            try:
                positions = self._get_positions()
            except Exception:
                logger.exception(
                    "Unable to read positions before closing %s",
                    symbol,
                )
                return False

            position = next(
                (
                    p for p in positions
                    if str(p.get("symbol", "")).strip().upper() == symbol
                ),
                None,
            )

            if position is None:
                return False

            if not self._validate_position(position):
                logger.error("Invalid stored position: %s", symbol)
                return False

            quantity = float(position["quantity"])
            entry_price = float(position["entry_price"])
            allocation = float(position["allocation"])
            entry_fee = float(position["entry_fee"])

            exit_price = price * (1.0 - self._slippage())

            if (
                not valid_number(exit_price)
                or exit_price <= 0
            ):
                return False

            exit_value = quantity * exit_price
            exit_fee = exit_value * float(FEE_RATE)
            gross_pnl = exit_value - allocation

            net_pnl = gross_pnl - entry_fee - exit_fee

            new_balance = (
                self.balance
                + exit_value
                - exit_fee
            )

            new_realized = self.realized_pnl + net_pnl

            calculated_values = (
                exit_value,
                exit_fee,
                gross_pnl,
                net_pnl,
                new_balance,
                new_realized,
            )

            if not all(valid_number(v) for v in calculated_values):
                return False

            if new_balance < 0:
                return False

            if not isinstance(reason, str):
                reason = "Position closed"

            trade = {
                "quantity": quantity,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "gross_pnl": gross_pnl,
                "net_pnl": net_pnl,
                "entry_fee": entry_fee,
                "exit_fee": exit_fee,
                "reason": reason[:200],
            }

            try:
                success = self.db.close_position_atomic(
                    symbol,
                    trade,
                    new_balance,
                    new_realized,
                )
            except Exception:
                logger.exception(
                    "Database error while closing %s",
                    symbol,
                )
                return False

            if not success:
                return False

            self.balance = new_balance
            self.realized_pnl = new_realized
            self.live_marks.pop(symbol, None)

            logger.info(
                "Paper position closed: %s | Net PnL: %.6f",
                symbol,
                net_pnl,
            )

            return True

    async def update_positions(self, market):

        async with self.update_lock:

            try:
                positions = self._get_positions()
            except Exception:
                logger.exception(
                    "Unable to load positions for update"
                )
                return

            for position in positions:

                symbol = position.get("symbol")

                if (
                    not isinstance(symbol, str)
                    or not symbol.strip()
                    or not self._validate_position(position)
                ):
                    logger.warning(
                        "Skipping invalid position during update"
                    )
                    continue

                symbol = symbol.strip().upper()

                try:
                    ticker = await market.get_ticker(symbol)

                    if not isinstance(ticker, dict):
                        continue

                    raw_price = ticker.get("price")

                    if (
                        not valid_number(raw_price)
                        or float(raw_price) <= 0
                    ):
                        continue

                    price = float(raw_price)

                    quantity = float(position["quantity"])
                    allocation = float(position["allocation"])
                    entry_fee = float(position["entry_fee"])

                    current_value = quantity * price
                    estimated_exit_fee = (
                        current_value * float(FEE_RATE)
                    )

                    unrealized_pnl = (
                        current_value
                        - allocation
                        - entry_fee
                        - estimated_exit_fee
                    )

                    if not all(valid_number(v) for v in (
                        current_value,
                        estimated_exit_fee,
                        unrealized_pnl,
                    )):
                        continue

                    # Do not add a mark for a position that
                    # has already been closed while awaiting the ticker.
                    with self.lock:
                        current_positions = self._get_positions()

                        still_open = any(
                            str(p.get("symbol", "")).strip().upper()
                            == symbol
                            for p in current_positions
                        )

                        if not still_open:
                            self.live_marks.pop(symbol, None)
                            continue

                        self.live_marks[symbol] = {
                            "current_price": price,
                            "unrealized_pnl": unrealized_pnl,
                        }

                    stop_loss = float(position.get("stop_loss", 0) or 0)
                    take_profit = float(position.get("take_profit", 0) or 0)

                    if stop_loss > 0 and price <= stop_loss:
                        self.close_position(
                            symbol,
                            price,
                            "Stop loss",
                        )

                    elif take_profit > 0 and price >= take_profit:
                        self.close_position(
                            symbol,
                            price,
                            "Take profit",
                        )

                except asyncio.CancelledError:
                    raise

                except Exception:
                    logger.exception(
                        "Position update failed for %s",
                        symbol,
                    )

    def get_summary(self):

        with self.lock:

            positions = self._get_positions()

            display_positions = []

            reserved = 0.0
            market_value = 0.0
            unrealized_pnl = 0.0
            estimated_exit_fees = 0.0

            for position in positions:

                if not self._validate_position(position):
                    raise RuntimeError(
                        "Invalid position data; refusing inaccurate summary"
                    )

                symbol = position["symbol"].strip().upper()

                quantity = float(position["quantity"])
                allocation = float(position["allocation"])
                entry_price = float(position["entry_price"])
                entry_fee = float(position["entry_fee"])

                mark = self.live_marks.get(symbol)

                if isinstance(mark, dict):
                    current_price = safe_float(
                        mark.get("current_price"),
                        entry_price,
                    )
                else:
                    current_price = entry_price

                if current_price <= 0:
                    current_price = entry_price

                current_value = quantity * current_price
                exit_fee = current_value * float(FEE_RATE)

                position_unrealized = (
                    current_value
                    - allocation
                    - entry_fee
                    - exit_fee
                )

                reserved += allocation
                market_value += current_value
                estimated_exit_fees += exit_fee
                unrealized_pnl += position_unrealized

                display_position = dict(position)
                display_position["current_price"] = current_price
                display_position["unrealized_pnl"] = position_unrealized

                display_positions.append(display_position)

            equity = (
                self.balance
                + market_value
                - estimated_exit_fees
            )

            if not all(valid_number(v) for v in (
                reserved,
                market_value,
                estimated_exit_fees,
                unrealized_pnl,
                equity,
            )):
                raise RuntimeError("Invalid paper account summary")

            trades = self.db.get_recent_trades(500)

            if not isinstance(trades, list):
                raise RuntimeError(
                    "Invalid trades returned by database"
                )

            wins = 0
            total = 0

            for trade in trades:

                if not isinstance(trade, dict):
                    continue

                pnl = safe_float(
                    trade.get("net_pnl"),
                    None,
                )

                if pnl is None:
                    continue

                total += 1

                if pnl > 0:
                    wins += 1

            win_rate = (
                wins / total * 100.0
                if total > 0
                else 0.0
            )

            return {
                "balance": self.balance,
                "equity": equity,
                "realized_pnl": self.realized_pnl,
                "unrealized_pnl": unrealized_pnl,
                "reserved": reserved,
                "positions": display_positions,
                "win_rate": win_rate,
            }
