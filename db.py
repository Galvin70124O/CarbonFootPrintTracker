"""Small database layer: SQLite locally, Postgres when DATABASE_URL is set.

All queries in the app use "?" placeholders and portable SQL, so the same code
runs on both. On Render's free plan the disk is wiped on every deploy, so use a
Postgres DATABASE_URL (for example a free Neon database) in production.
"""
import os
import sqlite3

DATABASE_URL = os.environ.get("DATABASE_URL", "")
DATABASE_PATH = os.environ.get("DATABASE_PATH", "carbon_tracker.db")

if DATABASE_URL.startswith(("postgres://", "postgresql://")):
    import psycopg
    from psycopg.rows import dict_row

    IS_POSTGRES = True
    IntegrityError = psycopg.IntegrityError
else:
    IS_POSTGRES = False
    IntegrityError = sqlite3.IntegrityError


class Database:
    """Thin wrapper so routes can call db.query / db.execute on either engine."""

    def __init__(self, conn):
        self.conn = conn

    def _sql(self, sql):
        return sql.replace("?", "%s") if IS_POSTGRES else sql

    def query(self, sql, params=()):
        cur = self.conn.execute(self._sql(sql), params)
        return [dict(row) for row in cur.fetchall()]

    def one(self, sql, params=()):
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql, params=()):
        self.conn.execute(self._sql(sql), params)

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()


def connect():
    if IS_POSTGRES:
        url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        return Database(psycopg.connect(url, row_factory=dict_row))
    conn = sqlite3.connect(os.environ.get("DATABASE_PATH", DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return Database(conn)


def init_schema(db):
    pk = "SERIAL PRIMARY KEY" if IS_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS users (
            id {pk},
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            monthly_goal REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS activities (
            id {pk},
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            category TEXT NOT NULL,
            activity_type TEXT NOT NULL,
            amount REAL NOT NULL,
            unit TEXT NOT NULL,
            emission REAL NOT NULL,
            date TEXT NOT NULL,
            manual_date TEXT
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_activities_user_date ON activities (user_id, date)")

    # Older databases were created without monthly_goal.
    if IS_POSTGRES:
        db.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS monthly_goal REAL")
    else:
        cols = [r["name"] for r in db.query("PRAGMA table_info(users)")]
        if "monthly_goal" not in cols:
            db.execute("ALTER TABLE users ADD COLUMN monthly_goal REAL")
    db.commit()
