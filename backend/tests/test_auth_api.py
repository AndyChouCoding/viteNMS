from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_bootstrap_status_true_when_no_users() -> None:
    response = client.get("/api/auth/bootstrap-status")
    assert response.status_code == 200
    assert response.json()["needs_bootstrap"] is True


def test_bootstrap_creates_admin_and_logs_in() -> None:
    response = client.post(
        "/api/auth/bootstrap", json={"username": "alice", "password": "password123", "role": "admin"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["username"] == "alice"
    assert body["user"]["role"] == "admin"
    assert body["token"]

    status_after = client.get("/api/auth/bootstrap-status")
    assert status_after.json()["needs_bootstrap"] is False


def test_bootstrap_rejected_once_a_user_exists() -> None:
    client.post(
        "/api/auth/bootstrap", json={"username": "alice", "password": "password123", "role": "admin"}
    )
    second = client.post(
        "/api/auth/bootstrap", json={"username": "mallory", "password": "password123", "role": "admin"}
    )
    assert second.status_code == 409


def test_login_success_and_failure() -> None:
    client.post(
        "/api/auth/bootstrap", json={"username": "alice", "password": "password123", "role": "admin"}
    )

    good = client.post("/api/auth/login", json={"username": "alice", "password": "password123"})
    assert good.status_code == 200
    assert good.json()["token"]

    bad = client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
    assert bad.status_code == 401


def test_me_requires_valid_token() -> None:
    no_token = client.get("/api/auth/me")
    assert no_token.status_code == 401

    bad_token = client.get("/api/auth/me", headers=_auth_header("not-a-real-token"))
    assert bad_token.status_code == 401


def test_login_success_failure_and_logout_are_recorded_in_the_system_log() -> None:
    client.post(
        "/api/auth/bootstrap", json={"username": "alice", "password": "password123", "role": "admin"}
    )
    good = client.post("/api/auth/login", json={"username": "alice", "password": "password123"})
    client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
    client.post("/api/auth/logout", headers=_auth_header(good.json()["token"]))

    me_after_logout = client.get("/api/auth/me", headers=_auth_header(good.json()["token"]))
    assert me_after_logout.status_code == 401  # session was just logged out

    fresh_token = client.post(
        "/api/auth/login", json={"username": "alice", "password": "password123"}
    ).json()["token"]
    entries = client.get("/api/logs", headers=_auth_header(fresh_token)).json()

    titles = [e["title"] for e in entries]
    assert titles.count("Login") == 2  # the initial login plus this re-login
    assert titles.count("Login Failed") == 1
    assert titles.count("Logout") == 1


def test_logout_invalidates_the_token() -> None:
    login = client.post(
        "/api/auth/bootstrap", json={"username": "alice", "password": "password123", "role": "admin"}
    )
    token = login.json()["token"]

    logout = client.post("/api/auth/logout", headers=_auth_header(token))
    assert logout.status_code == 200

    me_after_logout = client.get("/api/auth/me", headers=_auth_header(token))
    assert me_after_logout.status_code == 401


def test_create_user_requires_admin_role() -> None:
    admin_login = client.post(
        "/api/auth/bootstrap", json={"username": "alice", "password": "password123", "role": "admin"}
    )
    admin_token = admin_login.json()["token"]

    create_viewer = client.post(
        "/api/auth/users",
        json={"username": "bob", "password": "password123", "role": "viewer"},
        headers=_auth_header(admin_token),
    )
    assert create_viewer.status_code == 201

    viewer_login = client.post("/api/auth/login", json={"username": "bob", "password": "password123"})
    viewer_token = viewer_login.json()["token"]

    forbidden = client.post(
        "/api/auth/users",
        json={"username": "carol", "password": "password123", "role": "viewer"},
        headers=_auth_header(viewer_token),
    )
    assert forbidden.status_code == 403


def test_create_user_rejects_duplicate_username() -> None:
    admin_login = client.post(
        "/api/auth/bootstrap", json={"username": "alice", "password": "password123", "role": "admin"}
    )
    admin_token = admin_login.json()["token"]

    duplicate = client.post(
        "/api/auth/users",
        json={"username": "alice", "password": "password123", "role": "viewer"},
        headers=_auth_header(admin_token),
    )
    assert duplicate.status_code == 409


def test_delete_user_requires_admin_role() -> None:
    admin_login = client.post(
        "/api/auth/bootstrap", json={"username": "alice", "password": "password123", "role": "admin"}
    )
    admin_token = admin_login.json()["token"]

    viewer = client.post(
        "/api/auth/users",
        json={"username": "bob", "password": "password123", "role": "viewer"},
        headers=_auth_header(admin_token),
    ).json()

    viewer_token = client.post(
        "/api/auth/login", json={"username": "bob", "password": "password123"}
    ).json()["token"]

    forbidden = client.delete(f"/api/auth/users/{viewer['id']}", headers=_auth_header(viewer_token))
    assert forbidden.status_code == 403


def test_delete_user_removes_the_account_and_its_sessions() -> None:
    admin_login = client.post(
        "/api/auth/bootstrap", json={"username": "alice", "password": "password123", "role": "admin"}
    )
    admin_token = admin_login.json()["token"]

    bob = client.post(
        "/api/auth/users",
        json={"username": "bob", "password": "password123", "role": "viewer"},
        headers=_auth_header(admin_token),
    ).json()
    bob_token = client.post(
        "/api/auth/login", json={"username": "bob", "password": "password123"}
    ).json()["token"]

    deleted = client.delete(f"/api/auth/users/{bob['id']}", headers=_auth_header(admin_token))
    assert deleted.status_code == 204

    # The now-deleted user's existing session is no longer valid.
    assert client.get("/api/auth/me", headers=_auth_header(bob_token)).status_code == 401

    # Deleting again 404s instead of silently succeeding.
    again = client.delete(f"/api/auth/users/{bob['id']}", headers=_auth_header(admin_token))
    assert again.status_code == 404


def test_delete_user_refuses_to_orphan_remaining_accounts() -> None:
    admin_login = client.post(
        "/api/auth/bootstrap", json={"username": "alice", "password": "password123", "role": "admin"}
    )
    admin_token = admin_login.json()["token"]
    admin_id = admin_login.json()["user"]["id"]

    client.post(
        "/api/auth/users",
        json={"username": "bob", "password": "password123", "role": "viewer"},
        headers=_auth_header(admin_token),
    )

    response = client.delete(f"/api/auth/users/{admin_id}", headers=_auth_header(admin_token))
    assert response.status_code == 409


def test_delete_user_allows_removing_the_sole_remaining_account() -> None:
    admin_login = client.post(
        "/api/auth/bootstrap", json={"username": "alice", "password": "password123", "role": "admin"}
    )
    admin_token = admin_login.json()["token"]
    admin_id = admin_login.json()["user"]["id"]

    response = client.delete(f"/api/auth/users/{admin_id}", headers=_auth_header(admin_token))
    assert response.status_code == 204

    assert client.get("/api/auth/bootstrap-status").json()["needs_bootstrap"] is True


def test_topology_endpoint_requires_authentication() -> None:
    response = client.get("/api/topology")
    assert response.status_code == 401
