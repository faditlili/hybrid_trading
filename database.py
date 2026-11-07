"""SQLite persistence for a paper-only portfolio."""
import sqlite3
import threading
from pathlib import Path
from config import DB_PATH, STARTING_BALANCE

class Database:
    def __init__(self, path=DB_PATH):
        self.path = path
        if path != ":memory:":
            Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
        self.conn.row_factory = sqlite3.Row
        with self.lock:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA busy_timeout=30000")
            self._init_schema()

    def _init_schema(self):
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS account(id INTEGER PRIMARY KEY CHECK(id=1), cash REAL NOT NULL, realized_pnl REAL NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS positions(id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL UNIQUE, qty REAL NOT NULL, entry REAL NOT NULL, stop REAL NOT NULL, target REAL NOT NULL, notional REAL NOT NULL, entry_fee REAL NOT NULL, opened_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS trades(id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL, side TEXT NOT NULL, qty REAL NOT NULL, price REAL NOT NULL, pnl REAL NOT NULL, fee REAL NOT NULL, created_at TEXT NOT NULL, reason TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS decisions(id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL, action TEXT NOT NULL, score REAL NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, level TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL);
        """)
        self.conn.execute("INSERT OR IGNORE INTO account(id,cash,realized_pnl) VALUES(1,?,0)", (STARTING_BALANCE,))
        self.conn.commit()

    def account(self):
        with self.lock:
            return dict(self.conn.execute("SELECT * FROM account WHERE id=1").fetchone())

    def positions(self):
        with self.lock:
            return [dict(r) for r in self.conn.execute("SELECT * FROM positions ORDER BY opened_at")]

    def recent(self, table, limit=50):
        if table not in {"trades", "decisions", "events"}: raise ValueError("Unsupported table")
        with self.lock:
            return [dict(r) for r in self.conn.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT ?", (int(limit),))]

    def record_decision(self, symbol, action, score, reason, now):
        with self.lock:
            self.conn.execute("INSERT INTO decisions(symbol,action,score,reason,created_at) VALUES(?,?,?,?,?)", (symbol,action,float(score),reason,now)); self.conn.commit()

    def log_event(self, level, message, now):
        with self.lock:
            self.conn.execute("INSERT INTO events(level,message,created_at) VALUES(?,?,?)", (level,str(message)[:1000],now)); self.conn.commit()

    def close(self):
        with self.lock: self.conn.close()
