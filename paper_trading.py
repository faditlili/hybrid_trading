
"""Paper-only portfolio accounting.
No exchange order functionality exists here.
"""

import math
from datetime import datetime, timezone

import config


PORTFOLIO_RISK_FRACTION = 0.10

PORTFOLIO_EXPOSURE_LIMIT = config.PORTFOLIO_EXPOSURE_LIMIT
MAX_OPEN_POSITIONS = config.MAX_OPEN_POSITIONS
FEE_RATE = config.FEE_RATE
SLIPPAGE_BPS = config.SLIPPAGE_BPS
STOP_ATR_MULTIPLIER = config.STOP_ATR_MULTIPLIER
TARGET_R_MULTIPLIER = config.TARGET_R_MULTIPLIER


class PaperTrader:

    def __init__(self, db):
        self.db = db

    @staticmethod
    def now():
        return datetime.now(timezone.utc).isoformat()

    def equity(self, prices=None):
        """Current total portfolio value including unrealized P/L."""

        prices = prices or {}
        account = self.db.account()
        positions = self.db.positions()

        market_value = sum(
            p["qty"] * float(
                prices.get(p["symbol"], p["entry"])
            )
            for p in positions
        )

        return float(account["cash"]) + market_value

    def exposure(self, prices=None):
        """Current market value of all open positions."""

        prices = prices or {}

        return sum(
            p["qty"] * float(
                prices.get(p["symbol"], p["entry"])
            )
            for p in self.db.positions()
        )

    def risk_budget(self, prices=None):
        """10% of current total portfolio equity."""

        return max(
            0.0,
            self.equity(prices) * PORTFOLIO_RISK_FRACTION
        )

    def open_position(self, symbol, price, atr, prices=None):
        """Open a simulated position using portfolio-based risk sizing."""

        try:
            price = float(price)
            atr = float(atr)

            if not all(
                math.isfinite(x) and x > 0
                for x in (price, atr)
            ):
                return False

            prices = prices or {}

            positions = self.db.positions()

            if len(positions) >= MAX_OPEN_POSITIONS:
                return False

            if any(
                p["symbol"] == symbol
                for p in positions
            ):
                return False

            equity = self.equity(prices)
            cash = float(self.db.account()["cash"])

            if equity <= 0 or cash <= 0:
                return False

            # Portfolio exposure limit.
            current_exposure = self.exposure(prices)

            exposure_cap = (
                equity * PORTFOLIO_EXPOSURE_LIMIT
            )

            remaining_exposure = (
                exposure_cap - current_exposure
            )

            if remaining_exposure <= 0:
                return False

            # Simulated entry price including slippage.
            slippage = SLIPPAGE_BPS / 10000

            fill = price * (1 + slippage)

            # Stop-loss and take-profit.
            stop = (
                fill - STOP_ATR_MULTIPLIER * atr
            )

            if stop <= 0 or stop >= fill:
                return False

            target = (
                fill
                + (fill - stop) * TARGET_R_MULTIPLIER
            )

            # Calculate actual loss per unit if stop is reached.
            stop_fill = stop * (1 - slippage)

            loss_per_unit = (
                fill * (1 + FEE_RATE)
                - stop_fill * (1 - FEE_RATE)
            )

            if (
                not math.isfinite(loss_per_unit)
                or loss_per_unit <= 0
            ):
                return False

            # Dynamic risk budget based on total equity.
            risk_budget = (
                equity * PORTFOLIO_RISK_FRACTION
            )

            risk_quantity = (
                risk_budget / loss_per_unit
            )

            # Exposure constraint, including entry fee.
            max_exposure_notional = (
                remaining_exposure
                / (
                    1
                    + PORTFOLIO_EXPOSURE_LIMIT
                    * FEE_RATE
                )
            )

            # Available cash constraint.
            max_cash_notional = (
                cash / (1 + FEE_RATE)
            )

            # Final position size must satisfy all limits.
            notional = min(
                risk_quantity * fill,
                max_exposure_notional,
                max_cash_notional
            )

            if notional < 1:
                return False

            qty = notional / fill
            fee = notional * FEE_RATE

            if qty <= 0:
                return False

            # Atomic database transaction.
            with self.db.lock:

                try:
                    self.db.conn.execute(
                        "BEGIN IMMEDIATE"
                    )

                    account = self.db.conn.execute(
                        "SELECT cash FROM account WHERE id=1"
                    ).fetchone()

                    if (
                        account is None
                        or account[0] < notional + fee
                    ):
                        self.db.conn.rollback()
                        return False

                    self.db.conn.execute(
                        """
                        UPDATE account
                        SET cash = cash - ?
                        WHERE id = 1
                        """,
                        (notional + fee,)
                    )

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
                            fee,
                            self.now()
                        )
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
                            "PAPER_BUY",
                            qty,
                            fill,
                            0,
                            fee,
                            self.now(),
                            "Portfolio risk-based paper entry"
                        )
                    )

                    self.db.conn.commit()

                    return True

                except Exception:
                    self.db.conn.rollback()
                    raise

        except (TypeError, ValueError, OverflowError):
            return False

    def update(self, prices):
        """Update open positions and simulate stop/target exits."""

        closed = []

        for position in self.db.positions():

            symbol = position["symbol"]
            price = prices.get(symbol)

            if price is None:
                continue

            try:
                price = float(price)

                if not math.isfinite(price) or price <= 0:
                    continue

                entry = float(position["entry"])
                qty = float(position["qty"])
                stop = float(position["stop"])
                target = float(position["target"])
                entry_fee = float(position["entry_fee"])

                if price > stop and price < target:
                    continue

                # Conservative simulated exit with slippage.
                fill = price * (
                    1 - SLIPPAGE_BPS / 10000
                )

                gross = (fill - entry) * qty

                exit_fee = fill * qty * FEE_RATE

                pnl = (
                    gross
                    - entry_fee
                    - exit_fee
                )

                proceeds = (
                    fill * qty - exit_fee
                )

                with self.db.lock:

                    try:
                        self.db.conn.execute(
                            "BEGIN IMMEDIATE"
                        )

                        self.db.conn.execute(
                            """
                            UPDATE account
                            SET cash = cash + ?,
                                realized_pnl = realized_pnl + ?
                            WHERE id = 1
                            """,
                            (proceeds, pnl)
                        )

                        self.db.conn.execute(
                            """
                            DELETE FROM positions
                            WHERE id = ?
                            """,
                            (position["id"],)
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
                                self.now(),
                                "Stop/target paper simulation"
                            )
                        )

                        self.db.conn.commit()

                        closed.append({
                            "symbol": symbol,
                            "pnl": pnl,
                            "exit_price": fill
                        })

                    except Exception:
                        self.db.conn.rollback()
                        raise

            except (TypeError, ValueError, OverflowError):
                continue

        return closed
