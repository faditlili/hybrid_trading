
"""Paper-only portfolio accounting.

No exchange order functionality exists here.
All positions are simulated.
Aggregate theoretical portfolio risk is capped at 10%.
Provides detailed trade data for optional Telegram notifications.
"""

import math
from datetime import datetime, timezone

import config


PORTFOLIO_RISK_FRACTION = config.PORTFOLIO_RISK_FRACTION
PORTFOLIO_EXPOSURE_LIMIT = config.PORTFOLIO_EXPOSURE_LIMIT
MAX_OPEN_POSITIONS = config.MAX_OPEN_POSITIONS

FEE_RATE = config.FEE_RATE
SLIPPAGE_BPS = config.SLIPPAGE_BPS

STOP_ATR_MULTIPLIER = config.STOP_ATR_MULTIPLIER
TARGET_R_MULTIPLIER = config.TARGET_R_MULTIPLIER

SLIPPAGE_RATE = SLIPPAGE_BPS / 10000.0


class PaperTrader:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def now():
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _valid_positive(value):
        try:
            value = float(value)
            return math.isfinite(value) and value > 0
        except (TypeError, ValueError, OverflowError):
            return False

    def _mark_price(self, symbol, entry, prices):
        """Return a valid current mark price."""

        if symbol not in prices:
            return float(entry)

        value = prices[symbol]

        if not self._valid_positive(value):
            raise ValueError(
                f"Invalid market price for {symbol}"
            )

        return float(value)

    def _position_risk(self, position):
        """Estimate one open position's loss at its stop.

        Includes original entry fee and estimated exit
        slippage and fee.
        """

        qty = float(position["qty"])
        entry = float(position["entry"])
        stop = float(position["stop"])
        entry_fee = float(position["entry_fee"])

        values = (qty, entry, stop, entry_fee)

        if not all(math.isfinite(x) for x in values):
            raise ValueError("Invalid open-position risk data")

        if qty <= 0 or entry <= 0 or stop <= 0:
            raise ValueError("Invalid open position")

        if stop >= entry or entry_fee < 0:
            raise ValueError("Invalid stop or entry fee")

        estimated_exit = stop * (1 - SLIPPAGE_RATE)

        estimated_exit_proceeds = (
            estimated_exit * qty * (1 - FEE_RATE)
        )

        entry_cost = entry * qty + entry_fee

        risk = entry_cost - estimated_exit_proceeds

        if not math.isfinite(risk) or risk <= 0:
            raise ValueError("Invalid position risk")

        return risk

    def _portfolio_values(self, account, positions, prices):
        """Calculate equity, exposure and aggregate open risk."""

        cash = float(account["cash"])

        if not math.isfinite(cash) or cash < 0:
            raise ValueError("Invalid portfolio cash")

        market_value = 0.0
        aggregate_risk = 0.0

        for position in positions:
            qty = float(position["qty"])
            entry = float(position["entry"])

            if not math.isfinite(qty) or qty <= 0:
                raise ValueError("Invalid position quantity")

            mark = self._mark_price(
                position["symbol"],
                entry,
                prices,
            )

            market_value += qty * mark
            aggregate_risk += self._position_risk(position)

        equity = cash + market_value

        if not all(
            math.isfinite(x)
            for x in (equity, market_value, aggregate_risk)
        ):
            raise ValueError("Invalid portfolio valuation")

        return equity, market_value, aggregate_risk

    # --------------------------------------------------
    # Portfolio information
    # --------------------------------------------------

    def equity(self, prices=None):
        """Current portfolio equity including unrealized P/L."""

        prices = prices or {}

        account = self.db.account()
        positions = self.db.positions()

        equity, _, _ = self._portfolio_values(
            account,
            positions,
            prices,
        )

        return equity

    def exposure(self, prices=None):
        """Current market value of all open positions."""

        prices = prices or {}

        account = self.db.account()
        positions = self.db.positions()

        _, exposure, _ = self._portfolio_values(
            account,
            positions,
            prices,
        )

        return exposure

    def total_open_risk(self):
        """Total theoretical risk of all open positions."""

        positions = self.db.positions()

        return sum(
            self._position_risk(position)
            for position in positions
        )

    def risk_budget(self, prices=None):
        """Maximum aggregate risk based on current equity."""

        equity = self.equity(prices)

        return max(
            0.0,
            equity * PORTFOLIO_RISK_FRACTION,
        )

    def remaining_risk(self, prices=None):
        """Risk budget remaining after existing open positions."""

        prices = prices or {}

        account = self.db.account()
        positions = self.db.positions()

        equity, _, aggregate_risk = self._portfolio_values(
            account,
            positions,
            prices,
        )

        budget = equity * PORTFOLIO_RISK_FRACTION

        return max(0.0, budget - aggregate_risk)

    def get_position(self, symbol):
        """Return one currently open simulated position."""

        symbol = str(symbol).strip().upper()

        for position in self.db.positions():
            if position["symbol"] == symbol:
                return dict(position)

        return None

    # --------------------------------------------------
    # Open simulated position
    # --------------------------------------------------

    def open_position(self, symbol, price, atr, prices=None):
        """Open a simulated position within aggregate portfolio limits."""

        try:
            symbol = str(symbol).strip().upper()
            price = float(price)
            atr = float(atr)

            if not symbol:
                return False

            if not all(
                math.isfinite(x) and x > 0
                for x in (price, atr)
            ):
                return False

            prices = prices or {}

            fill = price * (1 + SLIPPAGE_RATE)

            stop = (
                fill - STOP_ATR_MULTIPLIER * atr
            )

            if not math.isfinite(stop) or stop <= 0 or stop >= fill:
                return False

            target = (
                fill
                + (fill - stop) * TARGET_R_MULTIPLIER
            )

            if not math.isfinite(target) or target <= fill:
                return False

            stop_fill = stop * (1 - SLIPPAGE_RATE)

            loss_per_unit = (
                fill * (1 + FEE_RATE)
                - stop_fill * (1 - FEE_RATE)
            )

            if (
                not math.isfinite(loss_per_unit)
                or loss_per_unit <= 0
            ):
                return False

            # All critical checks are repeated using fresh
            # database state inside one atomic transaction.
            with self.db.lock:
                try:
                    self.db.conn.execute("BEGIN IMMEDIATE")

                    account_row = self.db.conn.execute(
                        """
                        SELECT cash
                        FROM account
                        WHERE id = 1
                        """
                    ).fetchone()

                    if account_row is None:
                        self.db.conn.rollback()
                        return False

                    cash = float(account_row[0])

                    rows = self.db.conn.execute(
                        """
                        SELECT
                            id,
                            symbol,
                            qty,
                            entry,
                            stop,
                            target,
                            notional,
                            entry_fee,
                            opened_at
                        FROM positions
                        """
                    ).fetchall()

                    positions = [
                        dict(row)
                        for row in rows
                    ]

                    if len(positions) >= MAX_OPEN_POSITIONS:
                        self.db.conn.rollback()
                        return False

                    if any(
                        position["symbol"] == symbol
                        for position in positions
                    ):
                        self.db.conn.rollback()
                        return False

                    account = {"cash": cash}

                    equity, current_exposure, current_risk = (
                        self._portfolio_values(
                            account,
                            positions,
                            prices,
                        )
                    )

                    if equity <= 0 or cash <= 0:
                        self.db.conn.rollback()
                        return False

                    # Aggregate risk limit across all open positions.
                    risk_cap = (
                        equity * PORTFOLIO_RISK_FRACTION
                    )

                    remaining_risk = risk_cap - current_risk

                    if remaining_risk <= 0:
                        self.db.conn.rollback()
                        return False

                    # Independent market exposure limit.
                    exposure_cap = (
                        equity * PORTFOLIO_EXPOSURE_LIMIT
                    )

                    remaining_exposure = (
                        exposure_cap - current_exposure
                    )

                    if remaining_exposure <= 0:
                        self.db.conn.rollback()
                        return False

                    risk_quantity = (
                        remaining_risk / loss_per_unit
                    )

                    max_risk_notional = (
                        risk_quantity * fill
                    )

                    max_exposure_notional = (
                        remaining_exposure
                    )

                    max_cash_notional = (
                        cash / (1 + FEE_RATE)
                    )

                    notional = min(
                        max_risk_notional,
                        max_exposure_notional,
                        max_cash_notional,
                    )

                    if (
                        not math.isfinite(notional)
                        or notional < 1.0
                    ):
                        self.db.conn.rollback()
                        return False

                    qty = notional / fill
                    entry_fee = notional * FEE_RATE

                    if (
                        not math.isfinite(qty)
                        or qty <= 0
                        or notional + entry_fee > cash
                    ):
                        self.db.conn.rollback()
                        return False

                    # Final risk verification before insertion.
                    new_position_risk = (
                        qty * loss_per_unit
                    )

                    if (
                        current_risk + new_position_risk
                        > risk_cap + 1e-9
                    ):
                        self.db.conn.rollback()
                        return False

                    if (
                        current_exposure + notional
                        > exposure_cap + 1e-9
                    ):
                        self.db.conn.rollback()
                        return False

                    opened_at = self.now()

                    # Debit simulated cash.
                    self.db.conn.execute(
                        """
                        UPDATE account
                        SET cash = cash - ?
                        WHERE id = 1
                        """,
                        (notional + entry_fee,),
                    )

                    # Create simulated position.
                    self.db.conn.execute(
                        """
                        INSERT INTO positions
                        (
                            symbol,
                            qty,
                            entry,
                            stop,
                            target,
                            notional,
                            entry_fee,
                            opened_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            symbol,
                            qty,
                            fill,
                            stop,
                            target,
                            notional,
                            entry_fee,
                            opened_at,
                        ),
                    )

                    # Record simulated buy.
                    self.db.conn.execute(
                        """
                        INSERT INTO trades
                        (
                            symbol,
                            side,
                            qty,
                            price,
                            pnl,
                            fee,
                            created_at,
                            reason
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            symbol,
                            "PAPER_BUY",
                            qty,
                            fill,
                            0.0,
                            entry_fee,
                            opened_at,
                            "Aggregate portfolio risk-based paper entry",
                        ),
                    )

                    self.db.conn.commit()

                    return True

                except Exception:
                    self.db.conn.rollback()
                    raise

        except (TypeError, ValueError, OverflowError):
            return False

    # --------------------------------------------------
    # Update and close simulated positions
    # --------------------------------------------------

    def update(self, prices):
        """Update positions and simulate stop/target exits.

        Returns detailed records only for successfully committed
        simulated closures. These records can be used by the
        engine to send optional Telegram notifications.
        """

        prices = prices or {}
        closed = []

        for position in self.db.positions():
            symbol = position["symbol"]

            if symbol not in prices:
                continue

            try:
                price = float(prices[symbol])

                if not math.isfinite(price) or price <= 0:
                    continue

                stop = float(position["stop"])
                target = float(position["target"])

                if stop <= 0 or target <= stop:
                    continue

                # Stop exit: account for adverse price gaps.
                if price <= stop:
                    trigger_price = min(price, stop)
                    reason = "PAPER_STOP_LOSS"

                # Target exit: do not assume a better fill
                # than the configured target.
                elif price >= target:
                    trigger_price = target
                    reason = "PAPER_TAKE_PROFIT"

                else:
                    continue

                fill = trigger_price * (1 - SLIPPAGE_RATE)

                if not math.isfinite(fill) or fill <= 0:
                    continue

                qty = float(position["qty"])
                entry = float(position["entry"])
                entry_fee = float(position["entry_fee"])

                if (
                    not all(
                        math.isfinite(x)
                        for x in (qty, entry, entry_fee)
                    )
                    or qty <= 0
                    or entry <= 0
                    or entry_fee < 0
                ):
                    continue

                gross = (fill - entry) * qty
                exit_fee = fill * qty * FEE_RATE

                pnl = gross - entry_fee - exit_fee
                proceeds = fill * qty - exit_fee

                closed_at = self.now()

                with self.db.lock:
                    try:
                        self.db.conn.execute("BEGIN IMMEDIATE")

                        # Ensure the position still exists.
                        existing = self.db.conn.execute(
                            """
                            SELECT id
                            FROM positions
                            WHERE id = ?
                            """,
                            (position["id"],),
                        ).fetchone()

                        if existing is None:
                            self.db.conn.rollback()
                            continue

                        self.db.conn.execute(
                            """
                            UPDATE account
                            SET cash = cash + ?,
                                realized_pnl = realized_pnl + ?
                            WHERE id = 1
                            """,
                            (proceeds, pnl),
                        )

                        self.db.conn.execute(
                            """
                            DELETE FROM positions
                            WHERE id = ?
                            """,
                            (position["id"],),
                        )

                        self.db.conn.execute(
                            """
                            INSERT INTO trades
                            (
                                symbol,
                                side,
                                qty,
                                price,
                                pnl,
                                fee,
                                created_at,
                                reason
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                symbol,
                                "PAPER_SELL",
                                qty,
                                fill,
                                pnl,
                                exit_fee,
                                closed_at,
                                reason,
                            ),
                        )

                        self.db.conn.commit()

                        # Returned only after successful database commit.
                        closed.append({
                            "position_id": position["id"],
                            "symbol": symbol,
                            "side": "PAPER_SELL",
                            "qty": qty,
                            "entry_price": entry,
                            "exit_price": fill,
                            "gross_pnl": gross,
                            "entry_fee": entry_fee,
                            "exit_fee": exit_fee,
                            "total_fees": entry_fee + exit_fee,
                            "pnl": pnl,
                            "reason": reason,
                            "closed_at": closed_at,
                        })

                    except Exception:
                        self.db.conn.rollback()
                        raise

            except (TypeError, ValueError, OverflowError):
                continue

        return closed
