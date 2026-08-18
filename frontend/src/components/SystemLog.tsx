import { useEffect, useState } from 'react'
import { ApiError, getLogs } from '../lib/api'
import type { LogEntry } from '../types/log'

const REFRESH_INTERVAL_MS = 10_000

function formatTime(isoTimestamp: string): string {
  return new Date(isoTimestamp).toLocaleString('en-US')
}

export function SystemLog() {
  const [entries, setEntries] = useState<LogEntry[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function refresh() {
      try {
        const logs = await getLogs()
        if (!cancelled) {
          setEntries(logs)
          setError(null)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : 'Failed to load system log')
        }
      }
    }

    void refresh()
    const interval = setInterval(() => void refresh(), REFRESH_INTERVAL_MS)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [])

  if (error && entries === null) {
    return (
      <div className="flex h-full items-center justify-center text-red-500">
        Failed to load system log: {error}
      </div>
    )
  }

  if (entries === null) {
    return (
      <div className="flex h-full items-center justify-center text-slate-400">
        Loading system log…
      </div>
    )
  }

  if (entries.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-slate-400">
        No events recorded yet
      </div>
    )
  }

  return (
    <div className="h-full overflow-auto p-6">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-slate-500">
            <th className="py-2 pr-4 font-medium">Title</th>
            <th className="py-2 pr-4 font-medium">Description</th>
            <th className="py-2 font-medium">Time</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr key={entry.id} className="border-b border-slate-100">
              <td className="py-2 pr-4 text-slate-900">{entry.title}</td>
              <td className="py-2 pr-4 text-slate-700">{entry.description}</td>
              <td className="py-2 whitespace-nowrap font-mono text-xs text-slate-500">
                {formatTime(entry.created_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
