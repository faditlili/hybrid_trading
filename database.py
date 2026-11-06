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
            check_same_thread=False
        )
        self.conn.row_factory = sqlite3.Row
        self._init()

    def _init(self):
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

        cur.execute("SELECT id FROM account WHERE id=1")

        if not cur.fetchone():
            cur.execute("""
                INSERT INTO account(
                    id, balance, realized_pnl,
                    wins, losses, updated_at
                )
                VALUES(1, ?, 0, 0, 0, ?)
            """, (INITIAL_BALANCE, now_iso()))

        self.conn.commit()

    def account(self):
        row = self.conn.execute(
            "SELECT * FROM account WHERE id=1"
        ).fetchone()
        return dict(row)

    def update_account(self, balance, realized_pnl, wins, losses):
        self.conn.execute("""
            UPDATE account
            SET balance=?, realized_pnl=?,
                wins=?, losses=?, updated_at=?
            WHERE id=1
        """, (
            balance,
            realized_pnl,
            wins,
            losses,
            now_iso()
        ))
        self.conn.commit()

    def positions(self):
        return [
            dict(row)
            for row in self.conn.execute(
                "SELECT * FROM positions ORDER BY opened_at DESC"
            )
        ]

    def add_position(self, p):
        self.conn.execute("""
            INSERT OR REPLACE INTO positions(
                symbol, side, quantity, entry,
                stop, target, allocation,
                entry_fee, opened_at
            )
            VALUES(?,?,?,?,?,?,?,?,?)
        """, (
            p["symbol"],
            p["side"],
            p["quantity"],
            p["entry"],
            p["stop"],
            p["target"],
            p["allocation"],
            p["entry_fee"],
            p["opened_at"]
        ))
        self.conn.commit()

    def remove_position(self, symbol):
        self.conn.execute(
            "DELETE FROM positions WHERE symbol=?",
            (symbol,)
        )
        self.conn.commit()

    def add_trade(self, t):
        self.conn.execute("""
            INSERT INTO trades(
                symbol, side, entry, exit,
                quantity, pnl, reason,
                opened_at, closed_at
            )
            VALUES(?,?,?,?,?,?,?,?,?)
        """, (
            t["symbol"],
            t["side"],
            t["entry"],
            t["exit"],
            t["quantity"],
            t["pnl"],
            t["reason"],
            t["opened_at"],
            t["closed_at"]
        ))
        self.conn.commit()

    def log_decision(self, symbol, score, action, reasons):
        self.conn.execute("""
            INSERT INTO decisions(
                symbol, score, action, reasons, created_at
            )
            VALUES(?,?,?,?,?)
        """, (
            symbol,
            score,
            action,
            json.dumps(reasons, ensure_ascii=False),
            now_iso()
        ))
        self.conn.commit()

    def log_event(self, level, message):
        self.conn.execute("""
            INSERT INTO events(level, message, created_at)
            VALUES(?,?,?)
        """, (
            level,
            message[:1000],
            now_iso()
        ))
        self.conn.commit()

    def recent(self, table, limit=30):
        allowed = {"trades", "decisions", "events"}

        if table not in allowed:
            return []

        return [
            dict(row)
            for row in self.conn.execute(
                f"SELECT * FROM {table} ORDER BY id DESC LIMIT ?",
                (limit,)
            )
        ]

    def close(self):
        self.conn.close()
