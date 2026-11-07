"""SQLite persistence for a paper-only portfolio."""

import sqlite3
import threading
import logging
from pathlib import Path

from config import DB_PATH, STARTING_BALANCE

logger = logging.getLogger(__name__)


class Database:

    def __init__(self, path=DB_PATH):

        self.path = str(path)
        self.lock = threading.RLock()

        if self.path != ":memory:":
            db_path = Path(self.path).expanduser()

            # Create database directory if missing.
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
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA foreign_keys=ON")
            self.conn.execute("PRAGMA busy_timeout=30000")

            self._create_tables()

    def _create_tables(self):

        with self.conn:

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS account (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    balance REAL NOT NULL,
                    equity REAL NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    quantity REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    status TEXT DEFAULT 'OPEN',
                    opened_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    closed_at TEXT,
                    exit_price REAL,
                    pnl REAL DEFAULT 0
                )
            """)

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price REAL NOT NULL,
                    quantity REAL NOT NULL,
                    pnl REAL DEFAULT 0,
                    fee REAL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
                INSERT OR IGNORE INTO account
                (id, balance, equity)
                VALUES (1, ?, ?)
            """, (
                STARTING_BALANCE,
                STARTING_BALANCE
            ))

    def execute(self, query, params=()):

        with self.lock:
            cursor = self.conn.execute(query, params)
            self.conn.commit()
            return cursor

    def fetch_one(self, query, params=()):

        with self.lock:
            return self.conn.execute(
                query, params
            ).fetchone()

    def fetch_all(self, query, params=()):

        with self.lock:
            return self.conn.execute(
                query, params
            ).fetchall()

    def get_account(self):

        return self.fetch_one(
            "SELECT * FROM account WHERE id = 1"
        )

    def update_account(self, balance, equity):

        self.execute("""
            UPDATE account
            SET balance = ?,
                equity = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
        """, (balance, equity))

    def get_positions(self):

        return self.fetch_all("""
            SELECT * FROM positions
            WHERE status = 'OPEN'
            ORDER BY opened_at DESC
        """)

    def get_trades(self, limit=100):

        return self.fetch_all("""
            SELECT * FROM trades
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))

    def get_decisions(self, limit=100):

        return self.fetch_all("""
            SELECT * FROM decisions
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))

    def close(self):

        with self.lock:
            if self.conn:
                self.conn.close()
                self.conn = None
