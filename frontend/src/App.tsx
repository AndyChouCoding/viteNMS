import { useEffect, useState } from 'react'
import { AuthScreen } from './components/AuthScreen'
import { DeviceInfoPanel } from './components/DeviceInfoPanel'
import { TopologyGraph } from './components/TopologyGraph'
import { useAuth } from './context/auth-context'
import { getTopology } from './lib/api'
import type { TopologyGraph as TopologyGraphData } from './types/topology'

function MainView() {
  const { user, logout } = useAuth()
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
        <div className="flex items-center gap-4">
          {graph && <span className="text-xs text-slate-400">source: {graph.source}</span>}
          <span className="text-sm text-slate-500">
            {user?.username} <span className="text-slate-400">({user?.role})</span>
          </span>
          <button
            type="button"
            onClick={() => void logout()}
            className="rounded border border-slate-300 px-3 py-1 text-sm text-slate-600 hover:bg-slate-100"
          >
            Sign out
          </button>
        </div>
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

function App() {
  const { status } = useAuth()

  if (status === 'loading') {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-slate-50 text-slate-400">
        Loading…
      </div>
    )
  }

  if (status === 'needs-bootstrap' || status === 'logged-out') {
    return <AuthScreen />
  }

  return <MainView />
}

export default App
