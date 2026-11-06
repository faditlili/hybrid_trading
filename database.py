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
                    ai_vote TEXT DEFAULT 'N/A',
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

            # ترحيل قاعدة بيانات قديمة:
            # إضافة ai_vote إن لم يكن موجوداً
            decision_columns = {
                row["name"]
                for row in cur.execute(
                    "PRAGMA table_info(decisions)"
                ).fetchall()
            }

            if "ai_vote" not in decision_columns:

                cur.execute("""
                    ALTER TABLE decisions
                    ADD COLUMN ai_vote TEXT DEFAULT 'N/A'
                """)

            cur.execute(
                "SELECT id FROM account WHERE id=1"
            )

            if not cur.fetchone():

                cur.execute("""
                    INSERT INTO account(
                        id, balance, realized_pnl,
                        wins, losses, updated_at
                    )
                    VALUES(1, ?, 0, 0, 0, ?)
                """, (
                    INITIAL_BALANCE,
                    now_iso()
                ))

    # ACCOUNT

    def get_account(self):

        row = self.conn.execute(
            "SELECT * FROM account WHERE id=1"
        ).fetchone()

        return dict(row)

    def account(self):
        return self.get_account()

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

    # POSITIONS

    def get_positions(self):

        rows = self.conn.execute("""
            SELECT *
            FROM positions
            ORDER BY opened_at DESC
        """).fetchall()

        return [
            {
                "symbol": row["symbol"],
                "side": row["side"],
                "quantity": row["quantity"],
                "entry_price": row["entry"],
                "stop_loss": row["stop"],
                "take_profit": row["target"],
                "allocation": row["allocation"],
                "entry_fee": row["entry_fee"],
                "opened_at": row["opened_at"]
            }
            for row in rows
        ]

    def positions(self):
        return self.get_positions()

    # ATOMIC OPEN

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
                        symbol, side, quantity, entry,
                        stop, target, allocation,
                        entry_fee, opened_at
                    )
                    VALUES(?,?,?,?,?,?,?,?,?)
                """, (
                    position["symbol"],
                    "BUY",
                    position["quantity"],
                    position["entry_price"],
                    position["stop_loss"],
                    position["take_profit"],
                    position["allocation"],
                    position["entry_fee"],
                    now_iso()
                ))

                cur = self.conn.execute("""
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

                if cur.rowcount != 1:
                    raise RuntimeError("Account missing")

            return True

        except Exception:
            return False

    # ATOMIC CLOSE

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

                position = self.conn.execute("""
                    SELECT opened_at
                    FROM positions
                    WHERE symbol=?
                """, (symbol,)).fetchone()

                if not position:
                    raise RuntimeError("Position missing")

                self.conn.execute("""
                    INSERT INTO trades(
                        symbol, side, entry, exit,
                        quantity, pnl, reason,
                        opened_at, closed_at
                    )
                    VALUES(?,?,?,?,?,?,?,?,?)
                """, (
                    trade["symbol"],
                    "BUY",
                    trade["entry_price"],
                    trade["exit_price"],
                    trade["quantity"],
                    trade["net_pnl"],
                    trade["reason"],
                    position["opened_at"],
                    now_iso()
                ))

                cur = self.conn.execute("""
                    DELETE FROM positions
                    WHERE symbol=?
                """, (symbol,))

                if cur.rowcount != 1:
                    raise RuntimeError("Position deletion failed")

                cur = self.conn.execute("""
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

                if cur.rowcount != 1:
                    raise RuntimeError("Account missing")

            return True

        except Exception:
            return False

    # DECISIONS

    def log_decision(self, decision, *args):

        # دعم الصيغة القديمة والجديدة
        if isinstance(decision, dict):

            data = decision

        else:

            data = {
                "symbol": decision,
                "score": args[0],
                "action": args[1],
                "reasons": args[2]
            }

        with self.conn:

            self.conn.execute("""
                INSERT INTO decisions(
                    symbol, score, action,
                    reasons, ai_vote, created_at
                )
                VALUES(?,?,?,?,?,?)
            """, (
                data["symbol"],
                data.get("score", 0),
                data.get("action", "WAIT"),
                json.dumps(
                    data.get("reasons", []),
                    ensure_ascii=False
                ),
                data.get("ai_vote", "N/A"),
                data.get("timestamp", now_iso())
            ))

    def get_recent_decisions(self, limit=15):

        rows = self.recent("decisions", limit)

        for row in rows:

            try:
                row["reasons"] = json.loads(row["reasons"])
            except (TypeError, ValueError):
                row["reasons"] = []

        return rows

    # TRADES

    def get_recent_trades(self, limit=15):

        rows = self.recent("trades", limit)

        return [
            {
                **row,
                "entry_price": row["entry"],
                "exit_price": row["exit"],
                "net_pnl": row["pnl"]
            }
            for row in rows
        ]

    # EVENTS

    def log_event(self, level, message):

        with self.conn:

            self.conn.execute("""
                INSERT INTO events(level, message, created_at)
                VALUES(?,?,?)
            """, (
                level,
                str(message)[:1000],
                now_iso()
            ))

    # HISTORY

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

    # CLEANUP

    def close(self):

        if self.conn:
            self.conn.close()
