import sqlite3
import json

from datetime import datetime, timezone

from config import DATABASE_PATH, INITIAL_BALANCE


def now_iso():
    return datetime.now(timezone.utc).isoformat()


class Database:

    def __init__(self):

        self.conn = sqlite3.connect(
            DATABASE_PATH,
            check_same_thread=False,
            timeout=30
        )

        self.conn.row_factory = sqlite3.Row

        self.conn.execute("PRAGMA busy_timeout = 30000")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA foreign_keys = ON")

        self._init()

    # ======================================
    # INITIALIZATION
    # ======================================

    def _init(self):

        with self.conn:

            cur = self.conn.cursor()

            cur.execute("""
                CREATE TABLE IF NOT EXISTS account (
                    id INTEGER PRIMARY KEY CHECK(id=1),
                    balance REAL NOT NULL,
                    realized_pnl REAL NOT NULL DEFAULT 0,
                    wins INTEGER NOT NULL DEFAULT 0,
                    losses INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    symbol TEXT PRIMARY KEY,
                    side TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    entry REAL NOT NULL,
                    stop REAL NOT NULL,
                    target REAL NOT NULL,
                    allocation REAL NOT NULL,
                    entry_fee REAL NOT NULL,
                    opened_at TEXT NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry REAL NOT NULL,
                    exit REAL NOT NULL,
                    quantity REAL NOT NULL,
                    pnl REAL NOT NULL,
                    reason TEXT NOT NULL,
                    opened_at TEXT NOT NULL,
                    closed_at TEXT NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    score INTEGER,
                    action TEXT NOT NULL,
                    reasons TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            cur.execute(
                "SELECT id FROM account WHERE id=1"
            )

            if not cur.fetchone():

                cur.execute("""
                    INSERT INTO account(
                        id,
                        balance,
                        realized_pnl,
                        wins,
                        losses,
                        updated_at
                    )
                    VALUES(1, ?, 0, 0, 0, ?)
                """, (
                    INITIAL_BALANCE,
                    now_iso()
                ))

    # ======================================
    # ACCOUNT
    # ======================================

    def account(self):

        row = self.conn.execute(
            "SELECT * FROM account WHERE id=1"
        ).fetchone()

        return dict(row)

    def update_account(
        self,
        balance,
        realized_pnl,
        wins,
        losses
    ):

        with self.conn:

            self.conn.execute("""
                UPDATE account
                SET balance=?,
                    realized_pnl=?,
                    wins=?,
                    losses=?,
                    updated_at=?
                WHERE id=1
            """, (
                balance,
                realized_pnl,
                wins,
                losses,
                now_iso()
            ))

    # ======================================
    # POSITIONS
    # ======================================

    def positions(self):

        rows = self.conn.execute("""
            SELECT *
            FROM positions
            ORDER BY opened_at DESC
        """).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    def add_position(self, position):

        with self.conn:

            self.conn.execute("""
                INSERT INTO positions(
                    symbol,
                    side,
                    quantity,
                    entry,
                    stop,
                    target,
                    allocation,
                    entry_fee,
                    opened_at
                )
                VALUES(?,?,?,?,?,?,?,?,?)
            """, (
                position["symbol"],
                position["side"],
                position["quantity"],
                position["entry"],
                position["stop"],
                position["target"],
                position["allocation"],
                position["entry_fee"],
                position["opened_at"]
            ))

    def remove_position(self, symbol):

        with self.conn:

            self.conn.execute(
                "DELETE FROM positions WHERE symbol=?",
                (symbol,)
            )

    # ======================================
    # ATOMIC POSITION OPEN
    # ======================================

    def open_position_atomic(
        self,
        position,
        balance,
        realized_pnl,
        wins,
        losses
    ):

        try:

            with self.conn:

                self.conn.execute("""
                    INSERT INTO positions(
                        symbol,
                        side,
                        quantity,
                        entry,
                        stop,
                        target,
                        allocation,
                        entry_fee,
                        opened_at
                    )
                    VALUES(?,?,?,?,?,?,?,?,?)
                """, (
                    position["symbol"],
                    position["side"],
                    position["quantity"],
                    position["entry"],
                    position["stop"],
                    position["target"],
                    position["allocation"],
                    position["entry_fee"],
                    position["opened_at"]
                ))

                self.conn.execute("""
                    UPDATE account
                    SET balance=?,
                        realized_pnl=?,
                        wins=?,
                        losses=?,
                        updated_at=?
                    WHERE id=1
                """, (
                    balance,
                    realized_pnl,
                    wins,
                    losses,
                    now_iso()
                ))

            return True

        except sqlite3.Error:
            return False

    # ======================================
    # ATOMIC POSITION CLOSE
    # ======================================

    def close_position_atomic(
        self,
        symbol,
        trade,
        balance,
        realized_pnl,
        wins,
        losses
    ):

        try:

            with self.conn:

                self.conn.execute("""
                    INSERT INTO trades(
                        symbol,
                        side,
                        entry,
                        exit,
                        quantity,
                        pnl,
                        reason,
                        opened_at,
                        closed_at
                    )
                    VALUES(?,?,?,?,?,?,?,?,?)
                """, (
                    trade["symbol"],
                    trade["side"],
                    trade["entry"],
                    trade["exit"],
                    trade["quantity"],
                    trade["pnl"],
                    trade["reason"],
                    trade["opened_at"],
                    trade["closed_at"]
                ))

                cur = self.conn.execute("""
                    DELETE FROM positions
                    WHERE symbol=?
                """, (symbol,))

                if cur.rowcount != 1:
                    raise RuntimeError(
                        "Position does not exist in database"
                    )

                self.conn.execute("""
                    UPDATE account
                    SET balance=?,
                        realized_pnl=?,
                        wins=?,
                        losses=?,
                        updated_at=?
                    WHERE id=1
                """, (
                    balance,
                    realized_pnl,
                    wins,
                    losses,
                    now_iso()
                ))

            return True

        except Exception:
            return False

    # ======================================
    # TRADES
    # ======================================

    def add_trade(self, trade):

        with self.conn:

            self.conn.execute("""
                INSERT INTO trades(
                    symbol,
                    side,
                    entry,
                    exit,
                    quantity,
                    pnl,
                    reason,
                    opened_at,
                    closed_at
                )
                VALUES(?,?,?,?,?,?,?,?,?)
            """, (
                trade["symbol"],
                trade["side"],
                trade["entry"],
                trade["exit"],
                trade["quantity"],
                trade["pnl"],
                trade["reason"],
                trade["opened_at"],
                trade["closed_at"]
            ))

    # ======================================
    # DECISIONS
    # ======================================

    def log_decision(
        self,
        symbol,
        score,
        action,
        reasons
    ):

        with self.conn:

            self.conn.execute("""
                INSERT INTO decisions(
                    symbol,
                    score,
                    action,
                    reasons,
                    created_at
                )
                VALUES(?,?,?,?,?)
            """, (
                symbol,
                score,
                action,
                json.dumps(
                    reasons,
                    ensure_ascii=False
                ),
                now_iso()
            ))

    # ======================================
    # EVENTS
    # ======================================

    def log_event(self, level, message):

        with self.conn:

            self.conn.execute("""
                INSERT INTO events(
                    level,
                    message,
                    created_at
                )
                VALUES(?,?,?)
            """, (
                level,
                str(message)[:1000],
                now_iso()
            ))

    # ======================================
    # HISTORY
    # ======================================

    def recent(self, table, limit=30):

        allowed = {
            "trades",
            "decisions",
            "events"
        }

        if table not in allowed:
            return []

        limit = max(1, min(int(limit), 500))

        rows = self.conn.execute(
            f"""
            SELECT *
            FROM {table}
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    # ======================================
    # CLEANUP
    # ======================================

    def close(self):

        if self.conn:
            self.conn.close()
