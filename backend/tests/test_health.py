from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_topology_stub() -> None:
    response = client.get("/api/topology")
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "stub"
    assert len(body["nodes"]) == 3
    assert len(body["edges"]) == 2
