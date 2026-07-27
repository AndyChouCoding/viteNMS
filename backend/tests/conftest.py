import pytest

from app.core.db import close_db, init_db


@pytest.fixture(autouse=True)
async def _test_db(tmp_path):
    """Every test gets its own throwaway SQLite DB — none of this should
    ever touch the real backend/data/app.db, and tests must not leak
    users/sessions into each other."""
    await init_db(tmp_path / "test.db")
    yield
    await close_db()
