from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.topology import DeviceNode, TopologyGraph

client = TestClient(app)


def test_health_ok() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_topology_serves_cached_graph() -> None:
    """The endpoint just serves whatever the background poller last put in
    the cache — see test_topology_builder.py for the discovery logic
    itself, and topology_cache.py for why this isn't a live SNMP walk."""
    fake_graph = TopologyGraph(
        nodes=[DeviceNode(id="a", label="A", online=True)],
        edges=[],
        source="snmp",
    )
    with patch("app.api.topology.topology_cache.get", return_value=fake_graph):
        response = client.get("/api/topology")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "snmp"
    assert len(body["nodes"]) == 1
    assert body["nodes"][0]["id"] == "a"


def test_topology_defaults_to_empty_graph_before_first_poll() -> None:
    response = client.get("/api/topology")
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "uninitialized"
    assert body["nodes"] == []
