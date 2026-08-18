from unittest.mock import AsyncMock, patch

from app.models.topology import DeviceNode, TopologyGraph
from app.services import log_service
from app.services.topology_cache import TopologyCache


def _node(id_: str, label: str, ip: str | None = None) -> DeviceNode:
    return DeviceNode(id=id_, label=label, ip_address=ip, online=True)


async def test_new_device_logs_a_connected_event() -> None:
    cache = TopologyCache()
    previous = TopologyGraph(nodes=[_node("root", "Tablet")], edges=[], source="snmp")
    current = TopologyGraph(
        nodes=[_node("root", "Tablet"), _node("aa:bb", "Switch A", "192.0.2.10")],
        edges=[],
        source="snmp",
    )

    with patch.object(log_service, "record_event", AsyncMock()) as mock_record:
        await cache._log_transitions(previous, current)

    mock_record.assert_awaited_once_with(
        "Device Connected", "Switch A (192.0.2.10) joined the network"
    )


async def test_missing_device_logs_a_disconnected_event() -> None:
    cache = TopologyCache()
    previous = TopologyGraph(
        nodes=[_node("root", "Tablet"), _node("aa:bb", "Switch A", "192.0.2.10")],
        edges=[],
        source="snmp",
    )
    current = TopologyGraph(nodes=[_node("root", "Tablet")], edges=[], source="snmp")

    with patch.object(log_service, "record_event", AsyncMock()) as mock_record:
        await cache._log_transitions(previous, current)

    mock_record.assert_awaited_once_with(
        "Device Disconnected", "Switch A (192.0.2.10) left the network"
    )


async def test_unchanged_device_set_logs_nothing() -> None:
    cache = TopologyCache()
    graph = TopologyGraph(nodes=[_node("root", "Tablet")], edges=[], source="snmp")

    with patch.object(log_service, "record_event", AsyncMock()) as mock_record:
        await cache._log_transitions(graph, graph)

    mock_record.assert_not_awaited()


async def test_first_poll_against_uninitialized_cache_logs_nothing() -> None:
    """The cache starts with an empty "uninitialized" placeholder graph —
    the first real poll must not log every discovered device as a fresh
    "connected" event, only genuine state changes after that baseline."""
    cache = TopologyCache()
    discovered = TopologyGraph(
        nodes=[_node("root", "Tablet"), _node("aa:bb", "Switch A", "192.0.2.10")],
        edges=[],
        source="snmp",
    )

    with (
        patch(
            "app.services.topology_cache.discover_topology", AsyncMock(return_value=discovered)
        ),
        patch.object(log_service, "record_event", AsyncMock()) as mock_record,
        patch("app.services.topology_cache.asyncio.sleep", AsyncMock(side_effect=asyncio_cancel)),
    ):
        try:
            await cache._poll_loop()
        except _StopLoop:
            pass

    mock_record.assert_not_awaited()
    assert cache.get() == discovered


class _StopLoop(Exception):
    pass


async def asyncio_cancel(*_args, **_kwargs):
    raise _StopLoop
