import { useState } from 'react'
import { ApiError, pingDevice } from '../lib/api'
import type { DeviceNode, PingResult } from '../types/topology'

interface HostMonitorProps {
  nodes: DeviceNode[]
  canPing: boolean
}

type PingState =
  | { status: 'idle' }
  | { status: 'pinging' }
  | { status: 'done'; result: PingResult }
  | { status: 'error'; message: string }

function formatLatency(latencyMs: number | null): string {
  if (latencyMs === null) return 'reply received'
  return latencyMs < 1 ? '< 1 ms' : `${latencyMs} ms`
}

function ResultCell({ ping }: { ping: PingState }) {
  switch (ping.status) {
    case 'idle':
      return <span className="text-slate-300">—</span>
    case 'pinging':
      return <span className="text-slate-400">Pinging…</span>
    case 'error':
      return <span className="text-red-500">{ping.message}</span>
    case 'done':
      return ping.result.success ? (
        <span className="text-emerald-600">Reply • {formatLatency(ping.result.latency_ms)}</span>
      ) : (
        <span className="text-red-500">No reply (timeout)</span>
      )
  }
}

export function HostMonitor({ nodes, canPing }: HostMonitorProps) {
  const [pings, setPings] = useState<Record<string, PingState>>({})

  async function handlePing(deviceId: string) {
    setPings((prev) => ({ ...prev, [deviceId]: { status: 'pinging' } }))
    try {
      const result = await pingDevice(deviceId)
      setPings((prev) => ({ ...prev, [deviceId]: { status: 'done', result } }))
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Ping request failed'
      setPings((prev) => ({ ...prev, [deviceId]: { status: 'error', message } }))
    }
  }

  if (nodes.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-slate-400">
        No devices discovered yet
      </div>
    )
  }

  return (
    <div className="h-full overflow-auto p-6">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-slate-500">
            <th className="py-2 pr-4 font-medium">Device</th>
            <th className="py-2 pr-4 font-medium">IP Address</th>
            <th className="py-2 pr-4 font-medium">MAC Address</th>
            <th className="py-2 pr-4 font-medium">Status</th>
            <th className="py-2 pr-4 font-medium">Ping</th>
            <th className="py-2 font-medium">Result</th>
          </tr>
        </thead>
        <tbody>
          {nodes.map((device) => {
            const ping = pings[device.id] ?? { status: 'idle' }
            const canPingThisDevice = canPing && device.ip_address !== null
            const disabledReason = !canPing
              ? 'Requires operator role or higher'
              : device.ip_address === null
                ? 'No known IP address for this device'
                : undefined

            return (
              <tr key={device.id} className="border-b border-slate-100">
                <td className="py-2 pr-4 text-slate-900">{device.label}</td>
                <td className="py-2 pr-4 font-mono text-slate-700">{device.ip_address ?? '—'}</td>
                <td className="py-2 pr-4 font-mono text-slate-500">{device.mac_address ?? '—'}</td>
                <td className="py-2 pr-4">
                  <span
                    className={`rounded px-2 py-0.5 text-xs ${
                      device.online
                        ? 'bg-emerald-100 text-emerald-700'
                        : 'bg-slate-100 text-slate-500'
                    }`}
                  >
                    {device.online ? 'Online' : 'Offline'}
                  </span>
                </td>
                <td className="py-2 pr-4">
                  <button
                    type="button"
                    disabled={!canPingThisDevice || ping.status === 'pinging'}
                    onClick={() => void handlePing(device.id)}
                    title={disabledReason}
                    className="min-h-11 touch-manipulation rounded border border-slate-300 px-4 text-xs text-slate-600 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {ping.status === 'pinging' ? 'Pinging…' : 'Ping'}
                  </button>
                </td>
                <td className="py-2 text-slate-700">
                  <ResultCell ping={ping} />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
