import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from app.core.db import get_db
from app.services import auth_service as auth


async def test_password_hash_round_trip() -> None:
    hashed = auth.hash_password("correct-horse-battery-staple")
    assert auth.verify_password("correct-horse-battery-staple", hashed) is True
    assert auth.verify_password("wrong-password", hashed) is False


async def test_has_any_user_before_and_after_creation() -> None:
    assert await auth.has_any_user() is False
    await auth.create_user("alice", "password123", "admin")
    assert await auth.has_any_user() is True


async def test_create_user_rejects_duplicate_username() -> None:
    await auth.create_user("alice", "password123", "admin")
    with pytest.raises(sqlite3.IntegrityError):
        await auth.create_user("alice", "different-password", "viewer")


async def test_authenticate_rejects_wrong_password() -> None:
    await auth.create_user("alice", "password123", "viewer")
    assert await auth.authenticate("alice", "wrong") is None


async def test_authenticate_rejects_unknown_username() -> None:
    assert await auth.authenticate("ghost", "anything") is None


async def test_authenticate_accepts_correct_credentials() -> None:
    created = await auth.create_user("alice", "password123", "operator")
    authed = await auth.authenticate("alice", "password123")
    assert authed == created


async def test_session_round_trip() -> None:
    user = await auth.create_user("alice", "password123", "viewer")
    token, _ = await auth.create_session(user.id)

    fetched = await auth.get_user_by_session(token)
    assert fetched == user


async def test_unknown_session_token_returns_none() -> None:
    assert await auth.get_user_by_session("not-a-real-token") is None


async def test_deleted_session_no_longer_resolves() -> None:
    user = await auth.create_user("alice", "password123", "viewer")
    token, _ = await auth.create_session(user.id)

    await auth.delete_session(token)

    assert await auth.get_user_by_session(token) is None


async def test_expired_session_is_rejected_and_cleaned_up() -> None:
    user = await auth.create_user("alice", "password123", "viewer")
    token, _ = await auth.create_session(user.id)

    # Force the session into the past directly in the DB — create_session
    # always computes a future expiry, so this simulates time passing
    # rather than testing a contrived expiry value.
    db = get_db()
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    await db.execute("UPDATE sessions SET expires_at = ? WHERE token = ?", (past, token))
    await db.commit()

    assert await auth.get_user_by_session(token) is None

    # Expired sessions are pruned on access, not just rejected in place.
    async with db.execute("SELECT 1 FROM sessions WHERE token = ?", (token,)) as cursor:
        assert await cursor.fetchone() is None
