"""Unit tests for the BFS topology builder, mocking the ARP and SNMP
layers entirely — these verify graph-building logic (dedup, cycles, hop
limits), not real network behavior."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.network_discovery import ArpEntry
from app.services.snmp_service import LldpNeighbor
from app.services.topology_builder import ROOT_NODE_ID, discover_topology


@pytest.fixture(autouse=True)
def _no_real_ping_sweep():
    """discover_topology() calls sweep_local_subnets() before reading ARP —
    without this, every test in this file would fire real ICMP pings at
    the machine's actual local subnet, which is slow and non-deterministic
    in CI. See test_network_discovery.py for sweep's own tests."""
    with (
        patch("app.services.topology_builder.sweep_local_subnets", AsyncMock(return_value=None)),
        patch(
            "app.services.topology_builder.get_primary_local_address",
            return_value=("172.20.10.3", "aa:aa:aa:aa:aa:aa"),
        ),
    ):
        yield


def _arp(ip: str, mac: str) -> ArpEntry:
    return ArpEntry(ip=ip, mac=mac)


async def test_no_arp_entries_yields_root_only_graph() -> None:
    with patch(
        "app.services.topology_builder.read_arp_table", AsyncMock(return_value=[])
    ):
        graph = await discover_topology()

    assert [n.id for n in graph.nodes] == [ROOT_NODE_ID]
    assert graph.edges == []


async def test_root_node_carries_this_devices_own_ip_and_mac() -> None:
    """The root node used to ship with no ip_address/mac_address at all,
    which left "Tablet (this device)" showing "—" for both and disabled
    the Host Monitor's Ping button for it, even though the info was
    available via get_primary_local_address()."""
    with patch(
        "app.services.topology_builder.read_arp_table", AsyncMock(return_value=[])
    ):
        graph = await discover_topology()

    root = next(n for n in graph.nodes if n.id == ROOT_NODE_ID)
    assert root.ip_address == "172.20.10.3"
    assert root.mac_address == "aa:aa:aa:aa:aa:aa"


async def test_arp_only_device_with_no_snmp_still_becomes_a_node() -> None:
    """A device with no SNMP agent (e.g. a phone, a printer) should still
    show up as a node from ARP alone — just not expanded further."""
    arp_entries = [_arp("192.0.2.5", "aa:bb:cc:dd:ee:01")]

    async def fake_query_device(ip, community, timeout):
        return None, None, []  # SNMP unreachable

    with (
        patch(
            "app.services.topology_builder.read_arp_table",
            AsyncMock(return_value=arp_entries),
        ),
        patch(
            "app.services.topology_builder._query_device",
            side_effect=fake_query_device,
        ),
    ):
        graph = await discover_topology()

    node_ids = {n.id for n in graph.nodes}
    assert node_ids == {ROOT_NODE_ID, "aa:bb:cc:dd:ee:01"}
    assert len(graph.edges) == 1


async def test_arp_only_device_gets_vendor_from_mac_oui() -> None:
    """No SNMP agent means no sysDescr — vendor should still get filled in
    from the MAC's OUI (e80ab9 is a real Cisco-assigned prefix) so devices
    without SNMP aren't left with a blank Vendor field."""
    arp_entries = [_arp("192.0.2.5", "e8:0a:b9:11:22:33")]

    async def fake_query_device(ip, community, timeout):
        return None, None, []  # SNMP unreachable

    with (
        patch(
            "app.services.topology_builder.read_arp_table",
            AsyncMock(return_value=arp_entries),
        ),
        patch(
            "app.services.topology_builder._query_device",
            side_effect=fake_query_device,
        ),
    ):
        graph = await discover_topology()

    node = next(n for n in graph.nodes if n.id == "e8:0a:b9:11:22:33")
    assert node.vendor == "Cisco Systems, Inc"


async def test_snmp_sys_descr_vendor_is_not_overridden_by_oui() -> None:
    """When SNMP answers, its sysDescr-derived vendor (a specific device
    description) should win over the OUI table's manufacturer-only guess,
    not get clobbered by it."""
    arp_entries = [_arp("192.0.2.5", "e8:0a:b9:11:22:33")]

    async def fake_query_device(ip, community, timeout):
        return "Cisco IOS Software, C2960 Software", "switch-a", []

    with (
        patch(
            "app.services.topology_builder.read_arp_table",
            AsyncMock(return_value=arp_entries),
        ),
        patch(
            "app.services.topology_builder._query_device",
            side_effect=fake_query_device,
        ),
    ):
        graph = await discover_topology()

    node = next(n for n in graph.nodes if n.id == "e8:0a:b9:11:22:33")
    assert node.vendor == "Cisco IOS Software"


async def test_lldp_neighbor_not_in_arp_becomes_unexpanded_node() -> None:
    """A neighbor discovered via LLDP but absent from the tablet's own ARP
    table (multi-hop) should appear with its sysName label and no IP, and
    not be queried further (there's no address to query it at)."""
    arp_entries = [_arp("192.0.2.5", "aa:bb:cc:dd:ee:01")]

    async def fake_query_device(ip, community, timeout):
        assert ip == "192.0.2.5"
        return (
            "Cisco IOS",
            "switch-a",
            [LldpNeighbor(chassis_id="11:22:33:44:55:66", port_id="Gi0/1", sys_name="switch-b")],
        )

    with (
        patch(
            "app.services.topology_builder.read_arp_table",
            AsyncMock(return_value=arp_entries),
        ),
        patch(
            "app.services.topology_builder._query_device",
            side_effect=fake_query_device,
        ),
    ):
        graph = await discover_topology()

    nodes_by_id = {n.id: n for n in graph.nodes}
    assert set(nodes_by_id) == {ROOT_NODE_ID, "aa:bb:cc:dd:ee:01", "11:22:33:44:55:66"}
    assert nodes_by_id["aa:bb:cc:dd:ee:01"].label == "switch-a"
    assert nodes_by_id["11:22:33:44:55:66"].label == "switch-b"
    assert nodes_by_id["11:22:33:44:55:66"].ip_address is None

    edge_pairs = {(e.source, e.target) for e in graph.edges}
    assert (ROOT_NODE_ID, "aa:bb:cc:dd:ee:01") in edge_pairs or (
        "aa:bb:cc:dd:ee:01",
        ROOT_NODE_ID,
    ) in edge_pairs
    assert ("aa:bb:cc:dd:ee:01", "11:22:33:44:55:66") in edge_pairs or (
        "11:22:33:44:55:66",
        "aa:bb:cc:dd:ee:01",
    ) in edge_pairs


async def test_lldp_cycle_between_two_seeds_does_not_duplicate_or_self_loop() -> None:
    """Switch A and Switch B, both in the tablet's ARP table, each report
    the other as an LLDP neighbor — a real, common cyclic topology. Must
    not infinite-loop, duplicate the edge, or produce a self-loop."""
    mac_a, mac_b = "aa:aa:aa:aa:aa:aa", "bb:bb:bb:bb:bb:bb"
    arp_entries = [_arp("192.0.2.1", mac_a), _arp("192.0.2.2", mac_b)]

    async def fake_query_device(ip, community, timeout):
        if ip == "192.0.2.1":
            return "IOS", "switch-a", [LldpNeighbor(chassis_id=mac_b, port_id="Gi0/1", sys_name="switch-b")]
        return "IOS", "switch-b", [LldpNeighbor(chassis_id=mac_a, port_id="Gi0/2", sys_name="switch-a")]

    with (
        patch(
            "app.services.topology_builder.read_arp_table",
            AsyncMock(return_value=arp_entries),
        ),
        patch(
            "app.services.topology_builder._query_device",
            side_effect=fake_query_device,
        ),
    ):
        graph = await discover_topology()

    assert {n.id for n in graph.nodes} == {ROOT_NODE_ID, mac_a, mac_b}
    edge_pairs = {frozenset((e.source, e.target)) for e in graph.edges}
    assert frozenset((mac_a, mac_b)) in edge_pairs
    assert len(edge_pairs) == 3  # root-a, root-b, a-b — no duplicate a-b edge
    assert all(e.source != e.target for e in graph.edges)


async def test_lldp_edge_carries_local_and_remote_port_labels() -> None:
    """When two switches are linked, the edge should show which port on
    each side the link uses — e.g. Switch A's Gi0/1 to Switch B's Gi0/24."""
    mac_a, mac_b = "aa:aa:aa:aa:aa:aa", "bb:bb:bb:bb:bb:bb"
    arp_entries = [_arp("192.0.2.1", mac_a)]

    async def fake_query_device(ip, community, timeout):
        return (
            "IOS",
            "switch-a",
            [
                LldpNeighbor(
                    chassis_id=mac_b,
                    port_id="Gi0/24",  # the neighbor's (switch B's) port
                    sys_name="switch-b",
                    local_port="Gi0/1",  # switch A's own port
                )
            ],
        )

    with (
        patch(
            "app.services.topology_builder.read_arp_table",
            AsyncMock(return_value=arp_entries),
        ),
        patch(
            "app.services.topology_builder._query_device",
            side_effect=fake_query_device,
        ),
    ):
        graph = await discover_topology()

    edge = next(e for e in graph.edges if {e.source, e.target} == {mac_a, mac_b})
    # mac_a < mac_b lexicographically, so it's the canonical "source" and
    # keeps its own port association rather than being swapped.
    assert edge.source == mac_a
    assert edge.source_port == "Gi0/1"
    assert edge.target_port == "Gi0/24"


async def test_max_hops_limits_expansion_depth(monkeypatch) -> None:
    """A chain root -> A -> B -> C -> ... should stop expanding once the
    configured hop limit is reached, even if more neighbors exist."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "SNMP_MAX_HOPS", 1)

    mac_a, mac_b = "aa:aa:aa:aa:aa:aa", "bb:bb:bb:bb:bb:bb"
    arp_entries = [_arp("192.0.2.1", mac_a)]

    async def fake_query_device(ip, community, timeout):
        # A knows about B, but B is not in ARP so it'd only be reachable by
        # querying it directly — which requires hop 2, beyond the limit.
        return "IOS", "switch-a", [LldpNeighbor(chassis_id=mac_b, port_id="Gi0/1", sys_name="switch-b")]

    with (
        patch(
            "app.services.topology_builder.read_arp_table",
            AsyncMock(return_value=arp_entries),
        ),
        patch(
            "app.services.topology_builder._query_device",
            side_effect=fake_query_device,
        ) as mock_query,
    ):
        graph = await discover_topology()

    # B shows up as a node (learned from A's LLDP table) but is never
    # itself queried, since expansion stopped at hop 1.
    assert {n.id for n in graph.nodes} == {ROOT_NODE_ID, mac_a, mac_b}
    mock_query.assert_called_once()
