"""SQLite persistence for user accounts and sessions.

Plain SQL over aiosqlite rather than an ORM — the schema here is two small
tables with simple queries, and the project already leans toward avoiding
a framework layer where hand-written code is just as clear (see the raw
SNMP OID choice over MIB symbol resolution).

A single shared connection is used for the app's lifetime. aiosqlite
internally serializes all operations onto one background thread, so this
is safe for concurrent access from multiple request handlers without
extra locking on our side, and avoids reopening a connection per request
for what is a low-traffic local database (a handful of on-site users).
"""

from pathlib import Path

import aiosqlite

from app.core.paths import DATA_DIR

DB_PATH = DATA_DIR / "app.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('viewer', 'operator', 'admin')),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

_connection: aiosqlite.Connection | None = None


async def init_db(db_path: Path = DB_PATH) -> None:
    global _connection
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _connection = await aiosqlite.connect(db_path)
    _connection.row_factory = aiosqlite.Row
    await _connection.executescript(_SCHEMA)
    await _connection.commit()


async def close_db() -> None:
    global _connection
    if _connection is not None:
        await _connection.close()
        _connection = None


def get_db() -> aiosqlite.Connection:
    if _connection is None:
        raise RuntimeError("Database not initialized — call init_db() first")
    return _connection
