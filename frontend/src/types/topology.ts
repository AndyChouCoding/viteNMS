export interface DeviceNode {
  id: string
  label: string
  ip_address: string | null
  mac_address: string | null
  vendor: string | null
  online: boolean
}

export interface TopologyEdge {
  source: string
  target: string
  source_port: string | null
  target_port: string | null
}

export interface TopologyGraph {
  nodes: DeviceNode[]
  edges: TopologyEdge[]
  source: string
}
