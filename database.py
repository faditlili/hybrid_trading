
"""SQLite persistence for AI QUANT.
Paper trading only. Supports legacy database migration.
"""

import sqlite3
import threading
import logging
from pathlib import Path
from datetime import datetime, timezone

from config import DB_PATH, STARTING_BALANCE

logger = logging.getLogger(__name__)


class Database:

    def __init__(self, path=DB_PATH):

        self.path = str(path)
        self.lock = threading.RLock()

        if self.path != ":memory:":
            db_path = Path(self.path).expanduser()
            db_path.parent.mkdir(
                parents=True,
                exist_ok=True
            )
            self.path = str(db_path)

        self.conn = sqlite3.connect(
            self.path,
            check_same_thread=False,
            timeout=30
        )

        self.conn.row_factory = sqlite3.Row

        with self.lock:
            self.conn.execute("PRAGMA busy_timeout=30000")
            self.conn.execute("PRAGMA foreign_keys=ON")

            if self.path != ":memory:":
                self.conn.execute("PRAGMA journal_mode=WAL")

            self._create_tables()
            self._migrate_legacy_database()

        logger.info("AI QUANT database initialized.")

    @staticmethod
    def now():
        return datetime.now(timezone.utc).isoformat()

    def _columns(self, table):

        rows = self.conn.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()

        return {row["name"] for row in rows}

    def _create_tables(self):

        with self.conn:

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS account (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    cash REAL NOT NULL,
                    realized_pnl REAL NOT NULL DEFAULT 0,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    qty REAL NOT NULL,
                    entry REAL NOT NULL,
                    stop REAL NOT NULL,
                    target REAL NOT NULL,
                    notional REAL NOT NULL,
                    entry_fee REAL NOT NULL DEFAULT 0,
                    opened_at TEXT NOT NULL
                )
            """)

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    qty REAL NOT NULL,
                    price REAL NOT NULL,
                    pnl REAL NOT NULL DEFAULT 0,
                    fee REAL NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    reason TEXT DEFAULT ''
                )
            """)

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    score REAL DEFAULT 0,
                    reason TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_positions_symbol
                ON positions(symbol)
            """)

            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_trades_created
                ON trades(created_at)
            """)

            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_decisions_created
                ON decisions(created_at)
            """)

            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_events_created
                ON events(created_at)
            """)

            self.conn.execute("""
                INSERT OR IGNORE INTO account
                (id, cash, realized_pnl)
                VALUES (1, ?, 0)
            """, (STARTING_BALANCE,))

    def _migrate_legacy_database(self):
        """Migrate the previous balance/equity schema safely."""

        with self.conn:

            # Account migration.
            account_columns = self._columns("account")

            if "cash" not in account_columns:

                if "balance" in account_columns:

                    old = self.conn.execute("""
                        SELECT balance
                        FROM account
                        WHERE id=1
                    """).fetchone()

                    cash = (
                        float(old["balance"])
                        if old else STARTING_BALANCE
                    )

                else:
                    cash = STARTING_BALANCE

                self.conn.execute("""
                    ALTER TABLE account
                    RENAME TO account_legacy
                """)

                self.conn.execute("""
                    CREATE TABLE account (
                        id INTEGER PRIMARY KEY CHECK (id=1),
                        cash REAL NOT NULL,
                        realized_pnl REAL NOT NULL DEFAULT 0,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                self.conn.execute("""
                    INSERT INTO account
                    (id, cash, realized_pnl)
                    VALUES (1, ?, 0)
                """, (cash,))

                self.conn.execute(
                    "DROP TABLE account_legacy"
                )

            # Position migration.
            position_columns = self._columns("positions")

            if "qty" not in position_columns:

                rows = self.conn.execute(
                    "SELECT * FROM positions"
                ).fetchall()

                self.conn.execute("""
                    ALTER TABLE positions
                    RENAME TO positions_legacy
                """)

                self.conn.execute("""
                    CREATE TABLE positions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        qty REAL NOT NULL,
                        entry REAL NOT NULL,
                        stop REAL NOT NULL,
                        target REAL NOT NULL,
                        notional REAL NOT NULL,
                        entry_fee REAL NOT NULL DEFAULT 0,
                        opened_at TEXT NOT NULL
                    )
                """)

                for row in rows:

                    if row["status"] != "OPEN":
                        continue

                    qty = float(row["quantity"])
                    entry = float(row["entry_price"])

                    self.conn.execute("""
                        INSERT INTO positions
                        (
                            id, symbol, qty, entry,
                            stop, target, notional,
                            entry_fee, opened_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
                    """, (
                        row["id"],
                        row["symbol"],
                        qty,
                        entry,
                        row["stop_loss"],
                        row["take_profit"],
                        qty * entry,
                        row["opened_at"]
                    ))

                self.conn.execute(
                    "DROP TABLE positions_legacy"
                )

            # Trade history migration.
            trade_columns = self._columns("trades")

            if "qty" not in trade_columns:

                rows = self.conn.execute(
                    "SELECT * FROM trades"
                ).fetchall()

                self.conn.execute("""
                    ALTER TABLE trades
                    RENAME TO trades_legacy
                """)

                self.conn.execute("""
                    CREATE TABLE trades (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        side TEXT NOT NULL,
                        qty REAL NOT NULL,
                        price REAL NOT NULL,
                        pnl REAL NOT NULL DEFAULT 0,
                        fee REAL NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL,
                        reason TEXT DEFAULT ''
                    )
                """)

                for row in rows:

                    self.conn.execute("""
                        INSERT INTO trades
                        (
                            id, symbol, side, qty,
                            price, pnl, fee,
                            created_at, reason
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row["id"],
                        row["symbol"],
                        row["side"],
                        row["quantity"],
                        row["price"],
                        row["pnl"],
                        row["fee"],
                        row["created_at"],
                        "Migrated legacy trade"
                    ))

                self.conn.execute(
                    "DROP TABLE trades_legacy"
                )

        logger.info("Database migration completed.")

    # --------------------------------------------------
    # Core account API
    # --------------------------------------------------

    def account(self):

        row = self.fetch_one("""
            SELECT * FROM account
            WHERE id=1
        """)

        if row is None:
            raise RuntimeError("Portfolio account missing")

        result = dict(row)

        # Compatibility with older dashboard code.
        result["balance"] = result["cash"]
        result["equity"] = result["cash"]

        return result

    def positions(self):

        return self.fetch_all("""
            SELECT *
            FROM positions
            ORDER BY opened_at DESC
        """)

    # --------------------------------------------------
    # Decisions and events
    # --------------------------------------------------

    def record_decision(
        self,
        symbol,
        action,
        score,
        reason,
        created_at=None
    ):

        self.execute("""
            INSERT INTO decisions
            (symbol, action, score, reason, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            symbol,
            action,
            score,
            reason,
            created_at or self.now()
        ))

    def log_event(
        self,
        level,
        message,
        created_at=None
    ):

        self.execute("""
            INSERT INTO events
            (level, message, created_at)
            VALUES (?, ?, ?)
        """, (
            level,
            str(message),
            created_at or self.now()
        ))

    # --------------------------------------------------
    # Dashboard and history API
    # --------------------------------------------------

    def get_account(self):
        return self.account()

    def get_positions(self):
        return self.positions()

    def get_trades(self, limit=100):

        return self.fetch_all("""
            SELECT *
            FROM trades
            ORDER BY id DESC
            LIMIT ?
        """, (max(1, int(limit)),))

    def get_decisions(self, limit=100):

        return self.fetch_all("""
            SELECT *
            FROM decisions
            ORDER BY id DESC
            LIMIT ?
        """, (max(1, int(limit)),))

    def get_events(self, limit=100):

        return self.fetch_all("""
            SELECT *
            FROM events
            ORDER BY id DESC
            LIMIT ?
        """, (max(1, int(limit)),))

    # --------------------------------------------------
    # General SQL helpers
    # --------------------------------------------------

    def execute(self, query, params=()):

        with self.lock:

            cursor = self.conn.execute(
                query,
                params
            )

            self.conn.commit()

            return cursor

    def fetch_one(self, query, params=()):

        with self.lock:

            row = self.conn.execute(
                query,
                params
            ).fetchone()

            return dict(row) if row else None

    def fetch_all(self, query, params=()):

        with self.lock:

            rows = self.conn.execute(
                query,
                params
            ).fetchall()

            return [dict(row) for row in rows]

    def update_account(self, balance, equity):

        # Compatibility helper for older dashboard code.
        # Equity is calculated dynamically by PaperTrader.

        self.execute("""
            UPDATE account
            SET cash=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=1
        """, (balance,))

    # --------------------------------------------------
    # Shutdown
    # --------------------------------------------------

    def close(self):

        with self.lock:

            if self.conn is not None:
                self.conn.close()
                self.conn = None

                logger.info(
                    "AI QUANT database connection closed."
                )
