
"""SQLite persistence layer for AI QUANT.

Paper trading only.
Supports safe legacy migration, transactional updates,
and thread-safe database access.
"""

import logging
import math
import sqlite3
import threading

from datetime import datetime, timezone
from pathlib import Path

from config import DB_PATH, STARTING_BALANCE


logger = logging.getLogger("AI_QUANT.database")


class Database:

    def __init__(self, path=DB_PATH):
        self.path = str(path)
        self.lock = threading.RLock()
        self.conn = None

        if self.path != ":memory:":
            db_path = Path(self.path).expanduser()
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self.path = str(db_path)

        self.conn = sqlite3.connect(
            self.path,
            check_same_thread=False,
            timeout=30,
            isolation_level="DEFERRED",
        )

        self.conn.row_factory = sqlite3.Row

        try:
            with self.lock:
                self.conn.execute("PRAGMA busy_timeout=30000")
                self.conn.execute("PRAGMA foreign_keys=ON")

                if self.path != ":memory:":
                    self.conn.execute("PRAGMA journal_mode=WAL")
                    self.conn.execute("PRAGMA synchronous=NORMAL")

                self._initialize_schema()

            logger.info("AI QUANT database initialized.")

        except Exception:
            self.conn.close()
            self.conn = None
            raise

    # --------------------------------------------------
    # Utilities
    # --------------------------------------------------

    @staticmethod
    def now():
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _safe_float(value, default=0.0):
        try:
            number = float(value)

            if math.isfinite(number):
                return number

            return default

        except (TypeError, ValueError, OverflowError):
            return default

    @staticmethod
    def _first_value(item, *keys, default=None):
        for key in keys:
            value = item.get(key)

            if value is not None:
                return value

        return default

    @staticmethod
    def _valid_text(value):
        if value is None:
            return None

        value = str(value).strip()

        return value or None

    def _ensure_open(self):
        if self.conn is None:
            raise RuntimeError("Database connection is closed")

    def _table_exists(self, table):
        row = self.conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table' AND name=?
            """,
            (table,),
        ).fetchone()

        return row is not None

    def _columns(self, table):
        if not self._table_exists(table):
            return set()

        rows = self.conn.execute(
            f'PRAGMA table_info("{table}")'
        ).fetchall()

        return {row["name"] for row in rows}

    def _rename_legacy_table(self, table):
        """Preserve an incompatible table under a unique backup name."""

        base = f"{table}_legacy_migration"
        legacy_name = base
        suffix = 1

        while self._table_exists(legacy_name):
            suffix += 1
            legacy_name = f"{base}_{suffix}"

        self.conn.execute(
            f'ALTER TABLE "{table}" RENAME TO "{legacy_name}"'
        )

        return legacy_name

    # --------------------------------------------------
    # Schema initialization
    # --------------------------------------------------

    def _initialize_schema(self):
        legacy = {}

        expected = {
            "account": {
                "id",
                "cash",
                "realized_pnl",
                "updated_at",
            },
            "positions": {
                "id",
                "symbol",
                "qty",
                "entry",
                "stop",
                "target",
                "notional",
                "entry_fee",
                "opened_at",
            },
            "trades": {
                "id",
                "symbol",
                "side",
                "qty",
                "price",
                "pnl",
                "fee",
                "created_at",
                "reason",
            },
        }

        with self.conn:

            for table, required_columns in expected.items():

                if not self._table_exists(table):
                    continue

                existing_columns = self._columns(table)

                if not required_columns.issubset(existing_columns):
                    legacy[table] = self._rename_legacy_table(table)

            self._create_current_tables()

            if "account" in legacy:
                self._migrate_account(legacy["account"])

            if "positions" in legacy:
                self._migrate_positions(legacy["positions"])

            if "trades" in legacy:
                self._migrate_trades(legacy["trades"])

            self._create_indexes()

            self.conn.execute(
                """
                INSERT OR IGNORE INTO account
                    (id, cash, realized_pnl, updated_at)
                VALUES (1, ?, 0, ?)
                """,
                (
                    float(STARTING_BALANCE),
                    self.now(),
                ),
            )

        if legacy:
            logger.warning(
                "Legacy tables preserved as backups: %s",
                ", ".join(legacy.values()),
            )

    # --------------------------------------------------
    # Current schema
    # --------------------------------------------------

    def _create_current_tables(self):

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS account (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                cash REAL NOT NULL,
                realized_pnl REAL NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
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

    # --------------------------------------------------
    # Indexes
    # --------------------------------------------------

    def _create_indexes(self):

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_positions_symbol
            ON positions(symbol)
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_created
            ON trades(created_at)
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_decisions_created
            ON decisions(created_at)
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_created
            ON events(created_at)
        """)

    # --------------------------------------------------
    # Legacy migration
    # --------------------------------------------------

    def _migrate_account(self, legacy_table):

        row = self.conn.execute(
            f'SELECT * FROM "{legacy_table}" LIMIT 1'
        ).fetchone()

        if row is None:
            return

        values = dict(row)

        cash = self._safe_float(
            self._first_value(
                values,
                "cash",
                "balance",
                default=STARTING_BALANCE,
            ),
            STARTING_BALANCE,
        )

        realized_pnl = self._safe_float(
            values.get("realized_pnl"),
            0.0,
        )

        self.conn.execute(
            """
            INSERT OR REPLACE INTO account
                (id, cash, realized_pnl, updated_at)
            VALUES (1, ?, ?, ?)
            """,
            (
                cash,
                realized_pnl,
                self.now(),
            ),
        )

    def _migrate_positions(self, legacy_table):

        rows = self.conn.execute(
            f'SELECT * FROM "{legacy_table}"'
        ).fetchall()

        for row in rows:

            item = dict(row)

            status = str(
                item.get("status", "OPEN")
            ).strip().upper()

            if status != "OPEN":
                continue

            symbol = self._valid_text(item.get("symbol"))

            qty = self._safe_float(
                self._first_value(item, "qty", "quantity")
            )

            entry = self._safe_float(
                self._first_value(item, "entry", "entry_price")
            )

            stop = self._safe_float(
                self._first_value(item, "stop", "stop_loss")
            )

            target = self._safe_float(
                self._first_value(item, "target", "take_profit")
            )

            if (
                not symbol
                or qty <= 0
                or entry <= 0
                or stop <= 0
                or target <= entry
                or stop >= entry
            ):
                logger.warning(
                    "Skipped invalid legacy position id=%s",
                    item.get("id"),
                )
                continue

            notional = self._safe_float(
                item.get("notional"),
                qty * entry,
            )

            if notional <= 0:
                notional = qty * entry

            opened_at = (
                item.get("opened_at")
                or self.now()
            )

            entry_fee = self._safe_float(
                item.get("entry_fee"),
                0.0,
            )

            # Do not reuse old IDs: this avoids collisions
            # with positions already present in the new table.
            self.conn.execute(
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
                    entry,
                    stop,
                    target,
                    notional,
                    entry_fee,
                    opened_at,
                ),
            )

    def _migrate_trades(self, legacy_table):

        rows = self.conn.execute(
            f'SELECT * FROM "{legacy_table}"'
        ).fetchall()

        for row in rows:

            item = dict(row)

            symbol = self._valid_text(item.get("symbol"))
            side = self._valid_text(item.get("side"))

            qty = self._safe_float(
                self._first_value(item, "qty", "quantity")
            )

            price = self._safe_float(item.get("price"))

            if not symbol or not side or qty <= 0 or price <= 0:
                logger.warning(
                    "Skipped invalid legacy trade id=%s",
                    item.get("id"),
                )
                continue

            # Generate new IDs to avoid primary-key collisions.
            self.conn.execute(
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
                    side,
                    qty,
                    price,
                    self._safe_float(item.get("pnl")),
                    self._safe_float(item.get("fee")),
                    item.get("created_at") or self.now(),
                    item.get("reason") or "Migrated legacy trade",
                ),
            )

    # --------------------------------------------------
    # Account and positions
    # --------------------------------------------------

    def account(self):

        row = self.fetch_one(
            "SELECT * FROM account WHERE id=1"
        )

        if row is None:
            raise RuntimeError("Portfolio account is missing")

        row["balance"] = row["cash"]

        # Cash only. PaperTrader calculates mark-to-market equity.
        row["equity"] = row["cash"]

        return row

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
        created_at=None,
    ):

        score = self._safe_float(score)

        self.execute(
            """
            INSERT INTO decisions
                (symbol, action, score, reason, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(symbol),
                str(action),
                score,
                str(reason or ""),
                created_at or self.now(),
            ),
        )

    def log_event(self, level, message, created_at=None):

        self.execute(
            """
            INSERT INTO events
                (level, message, created_at)
            VALUES (?, ?, ?)
            """,
            (
                str(level),
                str(message),
                created_at or self.now(),
            ),
        )

    # --------------------------------------------------
    # Dashboard and history
    # --------------------------------------------------

    def get_account(self):
        return self.account()

    def get_positions(self):
        return self.positions()

    def get_trades(self, limit=100):

        limit = max(1, min(int(limit), 1000))

        return self.fetch_all(
            """
            SELECT *
            FROM trades
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )

    def get_decisions(self, limit=100):

        limit = max(1, min(int(limit), 1000))

        return self.fetch_all(
            """
            SELECT *
            FROM decisions
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )

    def get_events(self, limit=100):

        limit = max(1, min(int(limit), 1000))

        return self.fetch_all(
            """
            SELECT *
            FROM events
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )

    # --------------------------------------------------
    # SQL helpers
    # --------------------------------------------------

    def execute(self, query, params=()):

        with self.lock:
            self._ensure_open()

            try:
                cursor = self.conn.execute(query, params)
                self.conn.commit()
                return cursor

            except Exception:
                self.conn.rollback()
                raise

    def fetch_one(self, query, params=()):

        with self.lock:
            self._ensure_open()

            row = self.conn.execute(
                query,
                params,
            ).fetchone()

            return dict(row) if row else None

    def fetch_all(self, query, params=()):

        with self.lock:
            self._ensure_open()

            rows = self.conn.execute(
                query,
                params,
            ).fetchall()

            return [dict(row) for row in rows]

    # --------------------------------------------------
    # Account updates
    # --------------------------------------------------

    def update_account(self, balance, equity=None):
        """Update simulated cash balance.

        The equity argument is accepted for backward compatibility.
        It is not stored because mark-to-market equity is calculated
        from open positions by PaperTrader.
        """

        balance = float(balance)

        if not math.isfinite(balance) or balance < 0:
            raise ValueError("Invalid account balance")

        self.execute(
            """
            UPDATE account
            SET cash = ?,
                updated_at = ?
            WHERE id = 1
            """,
            (
                balance,
                self.now(),
            ),
        )

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
