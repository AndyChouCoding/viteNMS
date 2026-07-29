import cytoscape from 'cytoscape'
import dagre from 'cytoscape-dagre'
import { useMemo } from 'react'
import CytoscapeComponent from 'react-cytoscapejs'
import type { TopologyGraph as TopologyGraphData } from '../types/topology'

cytoscape.use(dagre)

const layout = {
  name: 'dagre',
  rankDir: 'LR',
  nodeSep: 60,
  rankSep: 100,
} as cytoscape.LayoutOptions

const stylesheet: cytoscape.StylesheetJson = [
  {
    selector: 'node',
    style: {
      label: 'data(label)',
      'background-color': '#3b82f6',
      color: '#0f172a',
      'font-size': 14,
      'text-valign': 'bottom',
      'text-margin-y': 6,
      width: 48,
      height: 48,
    },
  },
  {
    selector: 'node[online = "false"]',
    style: { 'background-color': '#94a3b8' },
  },
  {
    selector: 'node:selected',
    style: { 'border-width': 4, 'border-color': '#f59e0b' },
  },
  {
    selector: 'edge',
    style: {
      width: 2,
      'line-color': '#94a3b8',
      'curve-style': 'bezier',
      // Port labels near each endpoint — e.g. Switch A's Gi0/1 side vs
      // Switch B's Gi0/24 side of the same physical link. Empty string
      // (ARP-only edges with no LLDP/CDP port data) renders as no label.
      'source-label': 'data(sourcePort)',
      'target-label': 'data(targetPort)',
      'font-size': 9,
      color: '#64748b',
      'source-text-offset': 18,
      'target-text-offset': 18,
      'text-background-color': '#f8fafc',
      'text-background-opacity': 1,
      'text-background-padding': '2',
    },
  },
]

interface TopologyGraphProps {
  graph: TopologyGraphData
  onSelectNode: (nodeId: string | null) => void
}

export function TopologyGraph({ graph, onSelectNode }: TopologyGraphProps) {
  const elements = useMemo(
    () =>
      CytoscapeComponent.normalizeElements({
        nodes: graph.nodes.map((node) => ({
          data: { id: node.id, label: node.label, online: String(node.online) },
        })),
        edges: graph.edges.map((edge) => ({
          data: {
            id: `${edge.source}-${edge.target}`,
            source: edge.source,
            target: edge.target,
            sourcePort: edge.source_port ?? '',
            targetPort: edge.target_port ?? '',
          },
        })),
      }),
    [graph],
  )

  return (
    <CytoscapeComponent
      elements={elements}
      layout={layout}
      stylesheet={stylesheet}
      style={{ width: '100%', height: '100%' }}
      minZoom={0.3}
      maxZoom={3}
      userZoomingEnabled={true}
      userPanningEnabled={true}
      boxSelectionEnabled={false}
      cy={(cy) => {
        cy.off('tap')
        cy.on('tap', 'node', (event) => onSelectNode(event.target.id()))
        cy.on('tap', (event) => {
          if (event.target === cy) onSelectNode(null)
        })
      }}
    />
  )
}
