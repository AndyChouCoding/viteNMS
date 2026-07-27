"""SNMP-based topology and device discovery.

v1.0.0 ships a stub implementation so the frontend/API contract is real
and exercised end-to-end before the actual LLDP-MIB/CDP-MIB neighbor walk
and ARP-table read are implemented. Swapping this stub for the real
pysnmp-based discovery is the next unit of work after the scaffold.
"""

from app.models.topology import DeviceNode, TopologyEdge, TopologyGraph


async def get_stub_topology() -> TopologyGraph:
    return TopologyGraph(
        nodes=[
            DeviceNode(id="tablet-host", label="Tablet (this device)", online=True),
            DeviceNode(
                id="switch-a",
                label="Switch A",
                ip_address="192.0.2.10",
                mac_address="00:11:22:33:44:10",
                vendor="stub-vendor",
                online=True,
            ),
            DeviceNode(
                id="switch-b",
                label="Switch B",
                ip_address="192.0.2.11",
                mac_address="00:11:22:33:44:11",
                vendor="stub-vendor",
                online=True,
            ),
        ],
        edges=[
            TopologyEdge(source="tablet-host", target="switch-a"),
            TopologyEdge(source="switch-a", target="switch-b"),
        ],
        source="stub",
    )
