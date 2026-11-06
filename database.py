import sqlite3
import json
import logging
import threading

from datetime import datetime, timezone

from config import INITIAL_BALANCE, DB_PATH


logger = logging.getLogger(__name__)


def utc_timestamp():
    return datetime.now(timezone.utc).isoformat()


class Database:

    def __init__(self, db_path=None):

        self.db_path = db_path or DB_PATH

        self.lock = threading.RLock()
        self.conn = sqlite3.connect(
            self.db_path,
            timeout=30,
            check_same_thread=False
        )

        self.conn.row_factory = sqlite3.Row

        with self.lock:

            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA busy_timeout=30000")
            self.conn.execute("PRAGMA foreign_keys=ON")

            self._create_tables()
            self._migrate()

        logger.info("Database initialized: %s", self.db_path)

    def _create_tables(self):

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
            (INITIAL_BALANCE,)
        )

        self.conn.commit()

    def _migrate(self):

        columns = {
            row["name"]
            for row in self.conn.execute(
                "PRAGMA table_info(decisions)"
            ).fetchall()
        }

        if "ai_vote" not in columns:

            self.conn.execute(
                "ALTER TABLE decisions ADD COLUMN ai_vote TEXT"
            )

        self.conn.commit()

    def get_account(self):

        with self.lock:

            row = self.conn.execute(
                "SELECT * FROM account WHERE id=1"
            ).fetchone()

            return dict(row) if row else None

    def get_positions(self):

        with self.lock:

            rows = self.conn.execute(
                "SELECT * FROM positions ORDER BY opened_at"
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

    def open_position_atomic(self, position, new_balance):

        with self.lock:

            try:

                with self.conn:

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
                            position["symbol"],
                            position["quantity"],
                            position["entry_price"],
                            position["allocation"],
                            position["entry_fee"],
                            position["stop_loss"],
                            position["take_profit"],
                            position.get("opened_at", utc_timestamp())
                        )
                    )

                    self.conn.execute(
                        """
                        UPDATE account
                        SET balance=?
                        WHERE id=1
                        """,
                        (new_balance,)
                    )

                return True

            except sqlite3.Error:

                logger.exception("Failed to open paper position")
                return False

    def close_position_atomic(
        self,
        symbol,
        trade,
        new_balance,
        new_realized_pnl
    ):

        with self.lock:

            try:

                with self.conn:

                    row = self.conn.execute(
                        """
                        SELECT opened_at
                        FROM positions
                        WHERE symbol=?
                        """,
                        (symbol,)
                    ).fetchone()

                    if not row:
                        return False

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
                            trade["quantity"],
                            trade["entry_price"],
                            trade["exit_price"],
                            trade["gross_pnl"],
                            trade["net_pnl"],
                            trade["entry_fee"],
                            trade["exit_fee"],
                            trade.get("reason", ""),
                            row["opened_at"],
                            utc_timestamp()
                        )
                    )

                    self.conn.execute(
                        "DELETE FROM positions WHERE symbol=?",
                        (symbol,)
                    )

                    self.conn.execute(
                        """
                        UPDATE account
                        SET balance=?, realized_pnl=?
                        WHERE id=1
                        """,
                        (
                            new_balance,
                            new_realized_pnl
                        )
                    )

                return True

            except sqlite3.Error:

                logger.exception("Failed to close paper position")
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

        reasons = data.get("reasons", [])

        if not isinstance(reasons, str):

            reasons = json.dumps(
                reasons,
                ensure_ascii=False
            )

        with self.lock:

            try:

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
                            str(data.get("symbol", "UNKNOWN")),
                            str(data.get("action", "WAIT")),
                            int(data.get("score", 0)),
                            str(data.get("ai_vote", "")),
                            reasons,
                            data.get("timestamp", utc_timestamp())
                        )
                    )

                return True

            except (sqlite3.Error, TypeError, ValueError):

                logger.exception("Failed to log decision")
                return False

    def get_recent_decisions(self, limit=15):

        limit = max(1, min(int(limit), 500))

        with self.lock:

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
                    item["reasons"] = []

                results.append(item)

            return results

    def get_recent_trades(self, limit=15):

        limit = max(1, min(int(limit), 500))

        with self.lock:

            rows = self.conn.execute(
                """
                SELECT *
                FROM trades
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,)
            ).fetchall()

            results = []

            for row in rows:

                item = dict(row)

                item["entry_price"] = item["entry_price"]
                item["exit_price"] = item["exit_price"]
                item["net_pnl"] = item["net_pnl"]

                results.append(item)

            return results

    def log_event(self, level, message):

        with self.lock:

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
                            str(level),
                            str(message)[:2000],
                            utc_timestamp()
                        )
                    )

                return True

            except sqlite3.Error:

                logger.exception("Failed to log event")
                return False

    def get_recent_events(self, limit=50):

        limit = max(1, min(int(limit), 500))

        with self.lock:

            rows = self.conn.execute(
                """
                SELECT *
                FROM events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,)
            ).fetchall()

            return [dict(row) for row in rows]

    def close(self):

        with self.lock:

            if self.conn:

                self.conn.close()
                self.conn = None

                logger.info("Database connection closed")
