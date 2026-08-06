from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.security.dependencies import get_current_user
from app.main import app
from app.models.topology import DeviceNode, TopologyGraph
from app.models.user import User
from app.services.network_discovery import PingOutcome

client = TestClient(app)


@pytest.fixture(autouse=True)
def _bypass_auth():
    """Scoped to this file only — see test_health.py for why an unscoped
    override would leak into other test files sharing the same app
    instance. Defaults to admin so `require_role("operator")` passes;
    test_ping_requires_operator_role below overrides this with a real
    logged-in viewer to exercise the boundary itself."""
    app.dependency_overrides[get_current_user] = lambda: User(
        id=1, username="test", role="admin"
    )
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _fake_graph() -> TopologyGraph:
    return TopologyGraph(
        nodes=[
            DeviceNode(id="known-with-ip", label="Switch A", ip_address="192.0.2.10", online=True),
            DeviceNode(id="known-no-ip", label="Multi-hop node", ip_address=None, online=True),
        ],
        edges=[],
        source="snmp",
    )


def test_ping_unknown_device_returns_404() -> None:
    with patch("app.api.devices.topology_cache.get", return_value=_fake_graph()):
        response = client.post("/api/devices/does-not-exist/ping")
    assert response.status_code == 404


def test_ping_device_without_known_ip_returns_400() -> None:
    with patch("app.api.devices.topology_cache.get", return_value=_fake_graph()):
        response = client.post("/api/devices/known-no-ip/ping")
    assert response.status_code == 400


def test_ping_success_returns_latency() -> None:
    with (
        patch("app.api.devices.topology_cache.get", return_value=_fake_graph()),
        patch(
            "app.api.devices.ping_once",
            AsyncMock(return_value=PingOutcome(success=True, latency_ms=4.2)),
        ) as mock_ping,
    ):
        response = client.post("/api/devices/known-with-ip/ping")

    assert response.status_code == 200
    assert response.json() == {"success": True, "latency_ms": 4.2}
    mock_ping.assert_awaited_once_with("192.0.2.10")


def test_ping_failure_returns_success_false() -> None:
    with (
        patch("app.api.devices.topology_cache.get", return_value=_fake_graph()),
        patch(
            "app.api.devices.ping_once",
            AsyncMock(return_value=PingOutcome(success=False, latency_ms=None)),
        ),
    ):
        response = client.post("/api/devices/known-with-ip/ping")

    assert response.status_code == 200
    assert response.json() == {"success": False, "latency_ms": None}


def test_ping_requires_operator_role() -> None:
    """Unlike the other tests here, this needs a *real* role on the token
    (not the admin-by-default bypass), so it drops the fixture override and
    goes through actual bootstrap/login — mirrors
    test_auth_api.py::test_create_user_requires_admin_role."""
    app.dependency_overrides.pop(get_current_user, None)

    admin_login = client.post(
        "/api/auth/bootstrap", json={"username": "alice", "password": "password123", "role": "admin"}
    )
    admin_token = admin_login.json()["token"]
    client.post(
        "/api/auth/users",
        json={"username": "bob", "password": "password123", "role": "viewer"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    viewer_token = client.post(
        "/api/auth/login", json={"username": "bob", "password": "password123"}
    ).json()["token"]

    with patch("app.api.devices.topology_cache.get", return_value=_fake_graph()):
        forbidden = client.post(
            "/api/devices/known-with-ip/ping",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
    assert forbidden.status_code == 403


def test_ping_requires_authentication() -> None:
    app.dependency_overrides.pop(get_current_user, None)
    response = client.post("/api/devices/known-with-ip/ping")
    assert response.status_code == 401
