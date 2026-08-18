import { useEffect, useState } from 'react'
import { AuthScreen } from './components/AuthScreen'
import { DeviceInfoPanel } from './components/DeviceInfoPanel'
import { HostMonitor } from './components/HostMonitor'
import { SystemLog } from './components/SystemLog'
import { TopologyGraph } from './components/TopologyGraph'
import { useAuth } from './context/auth-context'
import { getTopology } from './lib/api'
import type { TopologyGraph as TopologyGraphData } from './types/topology'

type Tab = 'topology' | 'hostMonitor' | 'systemLog'

const TABS: { id: Tab; label: string }[] = [
  { id: 'topology', label: 'Topology' },
  { id: 'hostMonitor', label: 'Host Monitor' },
  { id: 'systemLog', label: 'System Log' },
]

function MainView() {
  const { user, logout } = useAuth()
  const [tab, setTab] = useState<Tab>('topology')
  const [graph, setGraph] = useState<TopologyGraphData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)

  useEffect(() => {
    getTopology()
      .then(setGraph)
      .catch((err: Error) => setError(err.message))
  }, [])

  const selectedDevice = graph?.nodes.find((node) => node.id === selectedNodeId) ?? null
  // Ping actively sends network traffic at the caller's request, so the
  // backend gates it behind operator — see app/api/devices.py.
  const canPing = user?.role === 'operator' || user?.role === 'admin'

  return (
    <div className="flex h-screen w-screen flex-col bg-slate-50">
      <header className="flex flex-wrap items-center justify-between gap-y-2 border-b border-slate-200 bg-white px-4 py-2 sm:px-6 sm:py-3">
        <div className="flex flex-wrap items-center gap-3 sm:gap-6">
          <h1 className="text-lg font-semibold text-slate-900">Open Vision Vite</h1>
          <nav className="flex gap-1">
            {TABS.map(({ id, label }) => (
              <button
                key={id}
                type="button"
                onClick={() => setTab(id)}
                className={`min-h-11 touch-manipulation rounded px-4 text-sm font-medium ${
                  tab === id
                    ? 'bg-slate-900 text-white'
                    : 'text-slate-500 hover:bg-slate-100'
                }`}
              >
                {label}
              </button>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-3 sm:gap-4">
          {graph && (
            <span className="hidden text-xs text-slate-400 sm:inline">source: {graph.source}</span>
          )}
          <span className="text-sm text-slate-500">
            {user?.username} <span className="text-slate-400">({user?.role})</span>
          </span>
          <button
            type="button"
            onClick={() => void logout()}
            className="min-h-11 touch-manipulation rounded border border-slate-300 px-4 text-sm text-slate-600 hover:bg-slate-100"
          >
            Sign out
          </button>
        </div>
      </header>

      <main className="flex flex-1 overflow-hidden">
        {tab !== 'systemLog' && error && (
          <div className="flex flex-1 items-center justify-center text-red-500">
            Failed to load topology: {error}
          </div>
        )}
        {tab !== 'systemLog' && !error && !graph && (
          <div className="flex flex-1 items-center justify-center text-slate-400">
            Loading topology…
          </div>
        )}
        {graph && tab === 'topology' && (
          <div className="flex flex-1 flex-col overflow-hidden md:flex-row">
            <div className="min-h-0 flex-1">
              <TopologyGraph graph={graph} onSelectNode={setSelectedNodeId} />
            </div>
            <aside className="h-48 shrink-0 overflow-auto border-t border-slate-200 bg-white md:h-auto md:w-80 md:border-t-0 md:border-l">
              <DeviceInfoPanel device={selectedDevice} />
            </aside>
          </div>
        )}
        {graph && tab === 'hostMonitor' && (
          <div className="flex-1">
            <HostMonitor nodes={graph.nodes} canPing={canPing} />
          </div>
        )}
        {tab === 'systemLog' && (
          <div className="flex-1">
            <SystemLog />
          </div>
        )}
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
