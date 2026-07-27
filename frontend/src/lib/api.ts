import type { TopologyGraph } from '../types/topology'

// The backend is a localhost-only sidecar process — see backend/app/core/config.py.
// This is intentionally not env-configurable to a non-loopback host.
const API_BASE = 'http://127.0.0.1:8756/api'

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`)
  if (!response.ok) {
    throw new Error(`Request to ${path} failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}

export function getTopology(): Promise<TopologyGraph> {
  return getJson<TopologyGraph>('/topology')
}
