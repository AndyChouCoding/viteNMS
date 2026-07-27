"""Builds a TopologyGraph by combining ARP-seeded local discovery with
recursive SNMP/LLDP (falling back to CDP) neighbor walking.

Node identity is the device's MAC address where known (LLDP chassis ID or
ARP-resolved MAC), since IPs can be reused/duplicated on a LAN and MAC is
the more stable key on a single broadcast domain. Devices discovered only
via a neighbor's LLDP table (multi-hop, not present in the tablet's own
ARP cache) have no known IP in v1.0.0 — they're still shown as nodes
(labeled from lldpRemSysName) but aren't expanded further, since there's
no address to query them at. Resolving multi-hop IPs is a natural
extension for a later version, not attempted here.
"""

import asyncio

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security.credential_store import get_credential
from app.models.topology import DeviceNode, TopologyEdge, TopologyGraph
from app.services.network_discovery import read_arp_table, sweep_local_subnets
from app.services.snmp_service import (
    LldpNeighbor,
    SnmpTarget,
    get_cdp_neighbors,
    get_lldp_neighbors,
    get_system_info,
)

logger = get_logger(__name__)

ROOT_NODE_ID = "tablet-host"
_MAC_STRING_LENGTH = 17  # "aa:bb:cc:dd:ee:ff"


class _BuilderState:
    def __init__(self) -> None:
        self.nodes: dict[str, DeviceNode] = {
            ROOT_NODE_ID: DeviceNode(id=ROOT_NODE_ID, label="Tablet (this device)", online=True)
        }
        self.edges: set[tuple[str, str]] = set()
        self.visited_ids: set[str] = {ROOT_NODE_ID}

    def add_edge(self, source: str, target: str) -> None:
        if source == target:
            return
        self.edges.add(tuple(sorted((source, target))))

    def to_graph(self) -> TopologyGraph:
        return TopologyGraph(
            nodes=list(self.nodes.values()),
            edges=[TopologyEdge(source=s, target=t) for s, t in self.edges],
            source="snmp",
        )


async def _query_device(
    ip: str, community: str, timeout: int
) -> tuple[str | None, str | None, list[LldpNeighbor]]:
    target = SnmpTarget(ip=ip, community=community, timeout=timeout)
    sys_descr, sys_name = await get_system_info(target)
    if sys_descr is None and sys_name is None:
        return None, None, []  # not SNMP-reachable/enabled — still a valid ARP-only node
    neighbors = await get_lldp_neighbors(target)
    if not neighbors:
        neighbors = await get_cdp_neighbors(target)
    return sys_descr, sys_name, neighbors


async def discover_topology() -> TopologyGraph:
    community = get_credential("snmp_community") or "public"
    timeout = settings.SNMP_TIMEOUT_SECONDS
    max_hops = settings.SNMP_MAX_HOPS

    await sweep_local_subnets()
    arp_entries = await read_arp_table()
    ip_by_mac = {entry.mac: entry.ip for entry in arp_entries}

    state = _BuilderState()
    if not arp_entries:
        logger.info("topology_discovery_no_arp_entries")
        return state.to_graph()

    # BFS frontier: (device_id, ip) to query this level. device_id is the
    # MAC address, used as the stable dedup key across hops.
    frontier: list[tuple[str, str]] = [(entry.mac, entry.ip) for entry in arp_entries]
    for device_id, ip in frontier:
        state.nodes.setdefault(
            device_id,
            DeviceNode(id=device_id, label=ip, ip_address=ip, mac_address=device_id, online=True),
        )
        state.add_edge(ROOT_NODE_ID, device_id)
    state.visited_ids.update(device_id for device_id, _ in frontier)

    hop = 0
    while frontier and hop < max_hops:
        hop += 1
        results = await asyncio.gather(
            *(_query_device(ip, community, timeout) for _, ip in frontier),
            return_exceptions=True,
        )

        next_frontier: list[tuple[str, str]] = []
        for (device_id, ip), result in zip(frontier, results):
            if isinstance(result, BaseException):
                logger.warning("snmp_query_failed", ip=ip, error=str(result))
                continue

            sys_descr, sys_name, neighbors = result
            node = state.nodes[device_id]
            if sys_name:
                node.label = sys_name
            if sys_descr:
                node.vendor = sys_descr.split(",")[0][:64]

            for neighbor in neighbors:
                neighbor_id = neighbor.chassis_id
                is_new = neighbor_id not in state.visited_ids
                neighbor_ip = ip_by_mac.get(neighbor_id)

                if is_new:
                    state.nodes[neighbor_id] = DeviceNode(
                        id=neighbor_id,
                        label=neighbor.sys_name or neighbor_id,
                        ip_address=neighbor_ip,
                        mac_address=neighbor_id
                        if len(neighbor_id) == _MAC_STRING_LENGTH
                        else None,
                        online=True,
                    )
                    state.visited_ids.add(neighbor_id)
                    if neighbor_ip:
                        next_frontier.append((neighbor_id, neighbor_ip))

                state.add_edge(device_id, neighbor_id)

        frontier = next_frontier

    return state.to_graph()
