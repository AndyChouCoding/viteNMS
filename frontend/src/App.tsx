import { useEffect, useState } from 'react'
import { DeviceInfoPanel } from './components/DeviceInfoPanel'
import { TopologyGraph } from './components/TopologyGraph'
import { getTopology } from './lib/api'
import type { TopologyGraph as TopologyGraphData } from './types/topology'

function App() {
  const [graph, setGraph] = useState<TopologyGraphData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)

  useEffect(() => {
    getTopology()
      .then(setGraph)
      .catch((err: Error) => setError(err.message))
  }, [])

  const selectedDevice = graph?.nodes.find((node) => node.id === selectedNodeId) ?? null

  return (
    <div className="flex h-screen w-screen flex-col bg-slate-50">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
        <h1 className="text-lg font-semibold text-slate-900">Open Vision Vite</h1>
        {graph && <span className="text-xs text-slate-400">source: {graph.source}</span>}
      </header>

      <main className="flex flex-1 overflow-hidden">
        <div className="flex-1">
          {error && (
            <div className="flex h-full items-center justify-center text-red-500">
              Failed to load topology: {error}
            </div>
          )}
          {!error && !graph && (
            <div className="flex h-full items-center justify-center text-slate-400">
              Loading topology…
            </div>
          )}
          {graph && <TopologyGraph graph={graph} onSelectNode={setSelectedNodeId} />}
        </div>
        <aside className="w-80 border-l border-slate-200 bg-white">
          <DeviceInfoPanel device={selectedDevice} />
        </aside>
      </main>
    </div>
  )
}

export default App
