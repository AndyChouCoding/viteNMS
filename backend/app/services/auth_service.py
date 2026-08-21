"""User accounts and session management: password hashing (argon2id) and
SQLite-backed user/session storage.

Sessions are opaque random tokens looked up in the sessions table on every
request, not JWTs — deliberately, so a session can be revoked immediately
(delete the row) rather than remaining valid until a self-contained
token's embedded expiry. There's no second backend or service that would
benefit from JWT's stateless-verification property here; this is a single
local FastAPI process.
"""

import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

from app.core.config import settings
from app.core.db import get_db
from app.models.user import Role, User

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerificationError:
        return False


async def has_any_user() -> bool:
    db = get_db()
    async with db.execute("SELECT 1 FROM users LIMIT 1") as cursor:
        row = await cursor.fetchone()
    return row is not None


async def list_users() -> list[User]:
    db = get_db()
    async with db.execute(
        "SELECT id, username, role FROM users WHERE is_active = 1 ORDER BY username"
    ) as cursor:
        rows = await cursor.fetchall()
    return [User(id=row["id"], username=row["username"], role=row["role"]) for row in rows]


async def get_user_by_id(user_id: int) -> User | None:
    db = get_db()
    async with db.execute(
        "SELECT id, username, role FROM users WHERE id = ? AND is_active = 1", (user_id,)
    ) as cursor:
        row = await cursor.fetchone()
    if row is None:
        return None
    return User(id=row["id"], username=row["username"], role=row["role"])


async def count_admins() -> int:
    db = get_db()
    async with db.execute(
        "SELECT COUNT(*) AS count FROM users WHERE role = 'admin' AND is_active = 1"
    ) as cursor:
        row = await cursor.fetchone()
    return row["count"]


async def count_users() -> int:
    db = get_db()
    async with db.execute("SELECT COUNT(*) AS count FROM users WHERE is_active = 1") as cursor:
        row = await cursor.fetchone()
    return row["count"]


async def update_password(user_id: int, password: str) -> None:
    """Sets a new password and invalidates that user's existing sessions —
    same reasoning as delete_user's session cascade: a credential change
    should force re-authentication, not leave already-issued tokens valid
    under a password the holder may no longer know."""
    db = get_db()
    await db.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), user_id)
    )
    await db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    await db.commit()


async def delete_user(user_id: int) -> None:
    db = get_db()
    await db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    await db.commit()


async def create_user(username: str, password: str, role: Role) -> User:
    db = get_db()
    password_hash = hash_password(password)
    created_at = datetime.now(UTC).isoformat()
    cursor = await db.execute(
        "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
        (username, password_hash, role, created_at),
    )
    await db.commit()
    assert cursor.lastrowid is not None
    return User(id=cursor.lastrowid, username=username, role=role)


async def authenticate(username: str, password: str) -> User | None:
    db = get_db()
    async with db.execute(
        "SELECT id, username, password_hash, role FROM users WHERE username = ? AND is_active = 1",
        (username,),
    ) as cursor:
        row = await cursor.fetchone()
    if row is None or not verify_password(password, row["password_hash"]):
        return None
    return User(id=row["id"], username=row["username"], role=row["role"])


async def create_session(user_id: int) -> tuple[str, datetime]:
    db = get_db()
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=settings.SESSION_DURATION_HOURS)
    await db.execute(
        "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token, user_id, now.isoformat(), expires_at.isoformat()),
    )
    await db.commit()
    return token, expires_at


async def get_user_by_session(token: str) -> User | None:
    db = get_db()
    async with db.execute(
        """
        SELECT users.id, users.username, users.role, sessions.expires_at
        FROM sessions JOIN users ON users.id = sessions.user_id
        WHERE sessions.token = ? AND users.is_active = 1
        """,
        (token,),
    ) as cursor:
        row = await cursor.fetchone()
    if row is None:
        return None
    if datetime.fromisoformat(row["expires_at"]) < datetime.now(UTC):
        await delete_session(token)
        return None
    return User(id=row["id"], username=row["username"], role=row["role"])


async def delete_session(token: str) -> None:
    db = get_db()
    await db.execute("DELETE FROM sessions WHERE token = ?", (token,))
    await db.commit()
