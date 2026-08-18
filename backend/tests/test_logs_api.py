from fastapi.testclient import TestClient

from app.core.security.dependencies import get_current_user
from app.main import app
from app.models.user import User
from app.services import log_service

client = TestClient(app)


def _bypass_auth(role: str = "viewer"):
    app.dependency_overrides[get_current_user] = lambda: User(id=1, username="test", role=role)


def _clear_auth():
    app.dependency_overrides.pop(get_current_user, None)


def test_get_logs_requires_authentication() -> None:
    _clear_auth()
    response = client.get("/api/logs")
    assert response.status_code == 401


async def test_get_logs_returns_recorded_events_newest_first() -> None:
    _bypass_auth("viewer")
    try:
        await log_service.record_event("First", "first description")
        await log_service.record_event("Second", "second description")

        response = client.get("/api/logs")
    finally:
        _clear_auth()

    assert response.status_code == 200
    titles = [entry["title"] for entry in response.json()]
    assert titles[:2] == ["Second", "First"]
