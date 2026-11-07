"""Database pipeline with learning loops."""
import sqlite3
import threading
import json
import time
import config

class Database:
    def __init__(self, path=None):
        self.path = path or config.DB_PATH
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(
            self.path, check_same_thread=False
        )
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._create_database_schema()
    def _create_database_schema(self):
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS account(
            id INTEGER PRIMARY KEY CHECK(id=1), 
            balance REAL NOT NULL, 
            equity REAL NOT NULL, 
            realized_pnl REAL NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS positions(
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            symbol TEXT NOT NULL, 
            entry REAL NOT NULL, 
            qty REAL NOT NULL, 
            stop REAL NOT NULL, 
            target REAL NOT NULL, 
            entry_fee REAL NOT NULL DEFAULT 0, 
            opened REAL NOT NULL, 
            status TEXT NOT NULL DEFAULT 'OPEN'
        );
        """)
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS trades(
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            symbol TEXT NOT NULL, 
            side TEXT NOT NULL, 
            price REAL NOT NULL, 
            qty REAL NOT NULL, 
            pnl REAL NOT NULL, 
            created REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS decisions(
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            symbol TEXT NOT NULL, 
            action TEXT NOT NULL, 
            score REAL NOT NULL, 
            details TEXT NOT NULL, 
            created REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            level TEXT NOT NULL, 
            message TEXT NOT NULL, 
            created REAL NOT NULL
        );
        """)
        # Ingesting dynamic initial funds into database cache
        self.conn.execute(
            "INSERT OR IGNORE INTO account"
            "(id, balance, equity, realized_pnl) "
            "VALUES(1, ?, ?, 0)", 
            (config.STARTING_BALANCE, 
             config.STARTING_BALANCE)
        )
        self.conn.commit()
    def account(self):
        with self.lock: 
            q = (
                "SELECT * FROM account "
                "WHERE id=1"
            )
            res = self.conn.execute(
                q
            ).fetchone()
            return dict(res)
    def positions(self):
        with self.lock: 
            q = (
                "SELECT * FROM positions "
                "WHERE status='OPEN' "
                "ORDER BY id"
            )
            cursor = self.conn.execute(
                q
            )
            return [
                dict(x) 
                for x in cursor
            ]
    def record_decision(
        self, symbol, action, 
        score, details
    ):
        with self.lock: 
            js = json.dumps(
                details, 
                ensure_ascii=False
            )
            q = (
                "INSERT INTO decisions"
                "(symbol, action, score, "
                "details, created) "
                "VALUES(?,?,?,?,?)"
            )
            self.conn.execute(
                q, 
                (symbol, action, 
                 score, js, 
                 time.time())
            )
            self.conn.commit()
    def recent(self, table, limit=50):
        _OK = {
            "trades", "decisions", 
            "events"
        }
        if table not in _OK: 
            raise ValueError(
                "Restricted table."
            )
        with self.lock: 
            lim = max(
                1, min(int(limit), 200)
            )
            q = (
                f"SELECT * FROM "
                f"{table} ORDER BY "
                f"id DESC LIMIT ?"
            )
            cursor = self.conn.execute(
                q, (lim,)
            )
            return [
                dict(x) 
                for x in cursor
            ]
    def log_event(self, level, message):
        with self.lock:
            q = (
                "INSERT INTO events"
                "(level, message, "
                "created) "
                "VALUES(?,?,?)"
            )
            self.conn.execute(
                q, 
                (level, message, 
                 time.time())
            )
            self.conn.commit()

    def get_symbol_recent_loss_count(
        self, symbol, hours=24
    ):
        sec = hours * 3600
        cutoff = time.time() - sec
        with self.lock:
            q = (
                "SELECT pnl FROM "
                "trades WHERE "
                "symbol=? AND "
                "created > ? "
                "ORDER BY id DESC "
                "LIMIT 3"
            )
            cursor = self.conn.execute(
                q, (symbol, cutoff)
            )
            rows = cursor.fetchall()
            losses = 0
            for r in rows:
                if r["pnl"] < 0: 
                    losses += 1
                else: 
                    break
            return losses
    def get_overall_win_rate(
        self, limit=20
    ):
        with self.lock:
            q = (
                "SELECT pnl FROM "
                "trades ORDER BY "
                "id DESC LIMIT ?"
            )
            cursor = self.conn.execute(
                q, (limit,)
            )
            rows = cursor.fetchall()
            if not rows: 
                return 0.50
            wins = sum(
                1 for r in rows 
                if r["pnl"] > 0
            )
            return wins / len(rows)

    def close(self):
        with self.lock: 
            self.conn.close()
