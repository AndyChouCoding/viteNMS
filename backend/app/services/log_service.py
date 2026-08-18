"""Append-only system event log backing the System Log tab — records
login/logout, ping attempts, and device connect/disconnect transitions.

Capped at _MAX_ENTRIES rows so a device left running for weeks doesn't
grow the table without bound; this is an on-screen activity feed, not an
audit trail requiring indefinite retention.
"""

from datetime import UTC, datetime

from app.core.db import get_db
from app.models.log import LogEntry

_MAX_ENTRIES = 500


async def record_event(title: str, description: str) -> None:
    db = get_db()
    await db.execute(
        "INSERT INTO logs (title, description, created_at) VALUES (?, ?, ?)",
        (title, description, datetime.now(UTC).isoformat()),
    )
    await db.execute(
        "DELETE FROM logs WHERE id NOT IN (SELECT id FROM logs ORDER BY id DESC LIMIT ?)",
        (_MAX_ENTRIES,),
    )
    await db.commit()


async def list_events(limit: int = _MAX_ENTRIES) -> list[LogEntry]:
    db = get_db()
    async with db.execute(
        "SELECT id, title, description, created_at FROM logs ORDER BY id DESC LIMIT ?",
        (limit,),
    ) as cursor:
        rows = await cursor.fetchall()
    return [LogEntry(**dict(row)) for row in rows]
