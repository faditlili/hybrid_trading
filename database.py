import sqlite3
import json
import logging
import threading
import math

from datetime import datetime, timezone

from config import INITIAL_BALANCE, DB_PATH


logger = logging.getLogger(__name__)


def utc_timestamp():
    return datetime.now(timezone.utc).isoformat()


def valid_number(value):
    if isinstance(value, bool):
        return False

    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def safe_float(value, default=None):
    if valid_number(value):
        return float(value)

    return default


def close_enough(a, b):
    return math.isclose(
        float(a),
        float(b),
        rel_tol=1e-8,
        abs_tol=1e-8
    )


class Database:

    def __init__(self, db_path=None):

        self.db_path = db_path or DB_PATH

        if not valid_number(INITIAL_BALANCE):
            raise ValueError("Invalid INITIAL_BALANCE")

        if float(INITIAL_BALANCE) <= 0:
            raise ValueError(
                "INITIAL_BALANCE must be positive"
            )

        self.lock = threading.RLock()

        self.conn = sqlite3.connect(
            self.db_path,
            timeout=30,
            check_same_thread=False
        )

        self.conn.row_factory = sqlite3.Row

        try:
            with self.lock:
                self.conn.execute("PRAGMA journal_mode=WAL")
                self.conn.execute("PRAGMA busy_timeout=30000")
                self.conn.execute("PRAGMA foreign_keys=ON")

                self._create_tables()
                self._migrate()

            logger.info(
                "Database initialized: %s",
                self.db_path
            )

        except Exception:
            if self.conn is not None:
                self.conn.close()
                self.conn = None

            raise

    def _ensure_open(self):

        if self.conn is None:
            raise RuntimeError(
                "Database connection is closed"
            )

    def _create_tables(self):

        self._ensure_open()

        self.conn.executescript("""

        CREATE TABLE IF NOT EXISTS account (
            id INTEGER PRIMARY KEY,
            balance REAL NOT NULL,
            realized_pnl REAL NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL UNIQUE,
            quantity REAL NOT NULL,
            entry_price REAL NOT NULL,
            allocation REAL NOT NULL,
            entry_fee REAL NOT NULL,
            stop_loss REAL NOT NULL,
            take_profit REAL NOT NULL,
            opened_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL DEFAULT 'BUY',
            quantity REAL NOT NULL,
            entry_price REAL NOT NULL,
            exit_price REAL NOT NULL,
            gross_pnl REAL NOT NULL,
            net_pnl REAL NOT NULL,
            entry_fee REAL NOT NULL,
            exit_fee REAL NOT NULL,
            reason TEXT,
            opened_at TEXT,
            closed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            action TEXT NOT NULL,
            score INTEGER NOT NULL DEFAULT 0,
            ai_vote TEXT,
            reasons TEXT,
            timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );

        """)

        self.conn.execute(
            """
            INSERT OR IGNORE INTO account
            (id, balance, realized_pnl)
            VALUES (1, ?, 0)
            """,
            (float(INITIAL_BALANCE),)
        )

        self.conn.commit()

    def _ensure_columns(self, table, definitions):

        self._ensure_open()

        existing = {
            row["name"]
            for row in self.conn.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()
        }

        for column, definition in definitions.items():

            if column not in existing:
                self.conn.execute(
                    f"ALTER TABLE {table} "
                    f"ADD COLUMN {column} {definition}"
                )

                logger.info(
                    "Database migration: added %s.%s",
                    table,
                    column
                )

    def _migrate(self):

        self._ensure_open()

        with self.conn:

            self._ensure_columns(
                "account",
                {
                    "balance": "REAL NOT NULL DEFAULT 0",
                    "realized_pnl": "REAL NOT NULL DEFAULT 0"
                }
            )

            self._ensure_columns(
                "positions",
                {
                    "symbol": "TEXT",
                    "quantity": "REAL NOT NULL DEFAULT 0",
                    "entry_price": "REAL NOT NULL DEFAULT 0",
                    "allocation": "REAL NOT NULL DEFAULT 0",
                    "entry_fee": "REAL NOT NULL DEFAULT 0",
                    "stop_loss": "REAL NOT NULL DEFAULT 0",
                    "take_profit": "REAL NOT NULL DEFAULT 0",
                    "opened_at": "TEXT"
                }
            )

            self._ensure_columns(
                "trades",
                {
                    "symbol": "TEXT",
                    "side": "TEXT NOT NULL DEFAULT 'BUY'",
                    "quantity": "REAL NOT NULL DEFAULT 0",
                    "entry_price": "REAL NOT NULL DEFAULT 0",
                    "exit_price": "REAL NOT NULL DEFAULT 0",
                    "gross_pnl": "REAL NOT NULL DEFAULT 0",
                    "net_pnl": "REAL NOT NULL DEFAULT 0",
                    "entry_fee": "REAL NOT NULL DEFAULT 0",
                    "exit_fee": "REAL NOT NULL DEFAULT 0",
                    "reason": "TEXT",
                    "opened_at": "TEXT",
                    "closed_at": "TEXT"
                }
            )

            self._ensure_columns(
                "decisions",
                {
                    "symbol": "TEXT",
                    "action": "TEXT",
                    "score": "INTEGER NOT NULL DEFAULT 0",
                    "ai_vote": "TEXT",
                    "reasons": "TEXT",
                    "timestamp": "TEXT"
                }
            )

            self._ensure_columns(
                "events",
                {
                    "level": "TEXT",
                    "message": "TEXT",
                    "timestamp": "TEXT"
                }
            )

            # Normalize existing symbols before adding
            # the unique index.
            self.conn.execute(
                """
                UPDATE positions
                SET symbol = UPPER(TRIM(symbol))
                WHERE symbol IS NOT NULL
                """
            )

            duplicates = self.conn.execute(
                """
                SELECT symbol, COUNT(*) AS total
                FROM positions
                WHERE symbol IS NOT NULL
                GROUP BY symbol
                HAVING COUNT(*) > 1
                """
            ).fetchall()

            if duplicates:
                duplicate_symbols = [
                    row["symbol"] for row in duplicates
                ]

                raise RuntimeError(
                    "Duplicate position symbols found. "
                    "Back up and repair the database first: "
                    + ", ".join(duplicate_symbols)
                )

            self.conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS
                idx_positions_symbol_unique
                ON positions(symbol)
                """
            )

        logger.info(
            "Database migrations completed"
        )

    def get_account(self):

        with self.lock:
            self._ensure_open()

            row = self.conn.execute(
                """
                SELECT *
                FROM account
                WHERE id=1
                """
            ).fetchone()

            return dict(row) if row else None

    def get_positions(self):

        with self.lock:
            self._ensure_open()

            rows = self.conn.execute(
                """
                SELECT *
                FROM positions
                ORDER BY opened_at
                """
            ).fetchall()

            return [
                {
                    "symbol": row["symbol"],
                    "quantity": row["quantity"],
                    "entry_price": row["entry_price"],
                    "allocation": row["allocation"],
                    "entry_fee": row["entry_fee"],
                    "stop_loss": row["stop_loss"],
                    "take_profit": row["take_profit"],
                    "opened_at": row["opened_at"]
                }
                for row in rows
            ]

    def open_position_atomic(
        self,
        position,
        new_balance
    ):

        if not isinstance(position, dict):
            return False

        symbol = position.get("symbol")

        if not isinstance(symbol, str) or not symbol.strip():
            return False

        symbol = symbol.strip().upper()

        quantity = safe_float(position.get("quantity"))
        entry_price = safe_float(position.get("entry_price"))
        allocation = safe_float(position.get("allocation"))
        entry_fee = safe_float(position.get("entry_fee"))
        stop_loss = safe_float(position.get("stop_loss"))
        take_profit = safe_float(position.get("take_profit"))
        new_balance = safe_float(new_balance)

        values = (
            quantity,
            entry_price,
            allocation,
            entry_fee,
            stop_loss,
            take_profit,
            new_balance
        )

        if any(value is None for value in values):
            return False

        if (
            quantity <= 0
            or entry_price <= 0
            or allocation <= 0
            or entry_fee < 0
            or stop_loss <= 0
            or take_profit <= entry_price
            or stop_loss >= entry_price
            or new_balance < 0
        ):
            return False

        if not close_enough(
            quantity * entry_price,
            allocation
        ):
            return False

        with self.lock:
            self._ensure_open()

            try:
                with self.conn:

                    self.conn.execute("BEGIN IMMEDIATE")

                    account = self.conn.execute(
                        """
                        SELECT balance
                        FROM account
                        WHERE id=1
                        """
                    ).fetchone()

                    if account is None:
                        raise sqlite3.IntegrityError(
                            "Account record missing"
                        )

                    current_balance = safe_float(
                        account["balance"]
                    )

                    if current_balance is None:
                        raise sqlite3.IntegrityError(
                            "Invalid account balance"
                        )

                    expected_balance = (
                        current_balance
                        - allocation
                        - entry_fee
                    )

                    if expected_balance < -1e-8:
                        raise sqlite3.IntegrityError(
                            "Insufficient paper balance"
                        )

                    if not close_enough(
                        new_balance,
                        max(0.0, expected_balance)
                    ):
                        raise sqlite3.IntegrityError(
                            "New balance calculation mismatch"
                        )

                    self.conn.execute(
                        """
                        INSERT INTO positions (
                            symbol,
                            quantity,
                            entry_price,
                            allocation,
                            entry_fee,
                            stop_loss,
                            take_profit,
                            opened_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            symbol,
                            quantity,
                            entry_price,
                            allocation,
                            entry_fee,
                            stop_loss,
                            take_profit,
                            position.get(
                                "opened_at",
                                utc_timestamp()
                            )
                        )
                    )

                    cursor = self.conn.execute(
                        """
                        UPDATE account
                        SET balance=?
                        WHERE id=1
                        """,
                        (max(0.0, expected_balance),)
                    )

                    if cursor.rowcount != 1:
                        raise sqlite3.IntegrityError(
                            "Account update failed"
                        )

                return True

            except sqlite3.Error:
                logger.exception(
                    "Failed to open paper position"
                )
                return False

    def close_position_atomic(
        self,
        symbol,
        trade,
        new_balance,
        new_realized_pnl
    ):

        if not isinstance(symbol, str) or not symbol.strip():
            return False

        if not isinstance(trade, dict):
            return False

        symbol = symbol.strip().upper()

        quantity = safe_float(trade.get("quantity"))
        entry_price = safe_float(trade.get("entry_price"))
        exit_price = safe_float(trade.get("exit_price"))
        gross_pnl = safe_float(trade.get("gross_pnl"))
        net_pnl = safe_float(trade.get("net_pnl"))
        entry_fee = safe_float(trade.get("entry_fee"))
        exit_fee = safe_float(trade.get("exit_fee"))
        new_balance = safe_float(new_balance)
        new_realized_pnl = safe_float(new_realized_pnl)

        values = (
            quantity,
            entry_price,
            exit_price,
            gross_pnl,
            net_pnl,
            entry_fee,
            exit_fee,
            new_balance,
            new_realized_pnl
        )

        if any(value is None for value in values):
            return False

        if (
            quantity <= 0
            or entry_price <= 0
            or exit_price <= 0
            or entry_fee < 0
            or exit_fee < 0
            or new_balance < 0
        ):
            return False

        with self.lock:
            self._ensure_open()

            try:
                with self.conn:

                    self.conn.execute("BEGIN IMMEDIATE")

                    row = self.conn.execute(
                        """
                        SELECT
                            quantity,
                            entry_price,
                            allocation,
                            entry_fee,
                            opened_at
                        FROM positions
                        WHERE symbol=?
                        """,
                        (symbol,)
                    ).fetchone()

                    if row is None:
                        raise sqlite3.IntegrityError(
                            "Position does not exist"
                        )

                    stored_quantity = float(row["quantity"])
                    stored_entry = float(row["entry_price"])
                    stored_allocation = float(row["allocation"])
                    stored_entry_fee = float(row["entry_fee"])

                    if not close_enough(
                        quantity,
                        stored_quantity
                    ):
                        raise sqlite3.IntegrityError(
                            "Position quantity mismatch"
                        )

                    if not close_enough(
                        entry_price,
                        stored_entry
                    ):
                        raise sqlite3.IntegrityError(
                            "Position entry price mismatch"
                        )

                    if not close_enough(
                        entry_fee,
                        stored_entry_fee
                    ):
                        raise sqlite3.IntegrityError(
                            "Position entry fee mismatch"
                        )

                    if not close_enough(
                        quantity * entry_price,
                        stored_allocation
                    ):
                        raise sqlite3.IntegrityError(
                            "Stored allocation mismatch"
                        )

                    expected_gross = (
                        quantity * exit_price
                        - quantity * entry_price
                    )

                    expected_net = (
                        expected_gross
                        - entry_fee
                        - exit_fee
                    )

                    if not close_enough(
                        gross_pnl,
                        expected_gross
                    ):
                        raise sqlite3.IntegrityError(
                            "Gross PnL mismatch"
                        )

                    if not close_enough(
                        net_pnl,
                        expected_net
                    ):
                        raise sqlite3.IntegrityError(
                            "Net PnL mismatch"
                        )

                    account = self.conn.execute(
                        """
                        SELECT balance, realized_pnl
                        FROM account
                        WHERE id=1
                        """
                    ).fetchone()

                    if account is None:
                        raise sqlite3.IntegrityError(
                            "Account record missing"
                        )

                    current_balance = safe_float(
                        account["balance"]
                    )

                    current_realized = safe_float(
                        account["realized_pnl"]
                    )

                    if (
                        current_balance is None
                        or current_realized is None
                    ):
                        raise sqlite3.IntegrityError(
                            "Invalid account values"
                        )

                    # The allocation was reserved when
                    # the position was opened.
                    expected_balance = (
                        current_balance
                        + stored_allocation
                        + gross_pnl
                        - exit_fee
                    )

                    expected_realized = (
                        current_realized
                        + net_pnl
                    )

                    if expected_balance < -1e-8:
                        raise sqlite3.IntegrityError(
                            "Invalid resulting balance"
                        )

                    if not close_enough(
                        new_balance,
                        max(0.0, expected_balance)
                    ):
                        raise sqlite3.IntegrityError(
                            "New balance calculation mismatch"
                        )

                    if not close_enough(
                        new_realized_pnl,
                        expected_realized
                    ):
                        raise sqlite3.IntegrityError(
                            "Realized PnL calculation mismatch"
                        )

                    self.conn.execute(
                        """
                        INSERT INTO trades (
                            symbol,
                            side,
                            quantity,
                            entry_price,
                            exit_price,
                            gross_pnl,
                            net_pnl,
                            entry_fee,
                            exit_fee,
                            reason,
                            opened_at,
                            closed_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            symbol,
                            "BUY",
                            quantity,
                            entry_price,
                            exit_price,
                            gross_pnl,
                            net_pnl,
                            entry_fee,
                            exit_fee,
                            str(
                                trade.get("reason", "")
                            )[:200],
                            row["opened_at"],
                            utc_timestamp()
                        )
                    )

                    cursor = self.conn.execute(
                        """
                        DELETE FROM positions
                        WHERE symbol=?
                        """,
                        (symbol,)
                    )

                    if cursor.rowcount != 1:
                        raise sqlite3.IntegrityError(
                            "Position deletion failed"
                        )

                    cursor = self.conn.execute(
                        """
                        UPDATE account
                        SET balance=?, realized_pnl=?
                        WHERE id=1
                        """,
                        (
                            max(0.0, expected_balance),
                            expected_realized
                        )
                    )

                    if cursor.rowcount != 1:
                        raise sqlite3.IntegrityError(
                            "Account update failed"
                        )

                return True

            except sqlite3.Error:
                logger.exception(
                    "Failed to close paper position"
                )
                return False

    def log_decision(self, *args, **kwargs):

        if args and isinstance(args[0], dict):
            data = args[0]

        else:
            data = kwargs

            if args:
                keys = [
                    "symbol",
                    "action",
                    "score",
                    "reasons",
                    "ai_vote",
                    "timestamp"
                ]

                data = {
                    **dict(zip(keys, args)),
                    **kwargs
                }

        if not isinstance(data, dict):
            return False

        try:
            reasons = data.get("reasons", [])

            if isinstance(reasons, str):
                reasons_text = reasons
            else:
                reasons_text = json.dumps(
                    reasons,
                    ensure_ascii=False
                )

            score = safe_float(
                data.get("score", 0)
            )

            if score is None:
                score = 0

            score = max(
                0,
                min(100, int(score))
            )

            with self.lock:
                self._ensure_open()

                with self.conn:
                    self.conn.execute(
                        """
                        INSERT INTO decisions (
                            symbol,
                            action,
                            score,
                            ai_vote,
                            reasons,
                            timestamp
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(
                                data.get("symbol", "UNKNOWN")
                            )[:50],
                            str(
                                data.get("action", "WAIT")
                            )[:50],
                            score,
                            str(
                                data.get("ai_vote", "")
                            )[:50],
                            reasons_text[:5000],
                            str(
                                data.get(
                                    "timestamp",
                                    utc_timestamp()
                                )
                            )
                        )
                    )

            return True

        except (
            sqlite3.Error,
            TypeError,
            ValueError,
            RuntimeError
        ):
            logger.exception(
                "Failed to log decision"
            )
            return False

    def get_recent_decisions(self, limit=15):

        limit = self._safe_limit(limit)

        with self.lock:
            self._ensure_open()

            rows = self.conn.execute(
                """
                SELECT *
                FROM decisions
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,)
            ).fetchall()

            results = []

            for row in rows:
                item = dict(row)

                try:
                    item["reasons"] = json.loads(
                        item["reasons"] or "[]"
                    )

                except (TypeError, ValueError):
                    item["reasons"] = [
                        str(item.get("reasons", ""))
                    ]

                results.append(item)

            return results

    def get_recent_trades(self, limit=15):

        limit = self._safe_limit(limit)

        with self.lock:
            self._ensure_open()

            rows = self.conn.execute(
                """
                SELECT *
                FROM trades
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,)
            ).fetchall()

            return [
                dict(row) for row in rows
            ]

    def log_event(self, level, message):

        with self.lock:
            self._ensure_open()

            try:
                with self.conn:
                    self.conn.execute(
                        """
                        INSERT INTO events (
                            level,
                            message,
                            timestamp
                        )
                        VALUES (?, ?, ?)
                        """,
                        (
                            str(level)[:30],
                            str(message)[:2000],
                            utc_timestamp()
                        )
                    )

                return True

            except sqlite3.Error:
                logger.exception(
                    "Failed to log event"
                )
                return False

    def get_recent_events(self, limit=50):

        limit = self._safe_limit(limit)

        with self.lock:
            self._ensure_open()

            rows = self.conn.execute(
                """
                SELECT *
                FROM events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,)
            ).fetchall()

            return [
                dict(row) for row in rows
            ]

    @staticmethod
    def _safe_limit(limit):

        try:
            limit = int(limit)
        except (TypeError, ValueError, OverflowError):
            limit = 15

        return max(
            1,
            min(limit, 500)
        )

    def close(self):

        with self.lock:
            if self.conn is not None:
                self.conn.close()
                self.conn = None

                logger.info(
                    "Database connection closed"
                )
