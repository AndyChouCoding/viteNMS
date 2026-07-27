from pydantic import BaseModel


class DeviceNode(BaseModel):
    id: str
    label: str
    ip_address: str | None = None
    mac_address: str | None = None
    vendor: str | None = None
    online: bool = True


class TopologyEdge(BaseModel):
    source: str
    target: str


class TopologyGraph(BaseModel):
    nodes: list[DeviceNode]
    edges: list[TopologyEdge]
    source: str  # "stub" for v1.0.0 scaffold, "snmp" once real discovery lands
