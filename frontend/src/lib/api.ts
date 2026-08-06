import type { LoginResponse, User } from '../types/auth'
import type { PingResult, TopologyGraph } from '../types/topology'

// The backend is a localhost-only sidecar process — see backend/app/core/config.py.
// This is intentionally not env-configurable to a non-loopback host.
const API_BASE = 'http://127.0.0.1:8756/api'

// Cross-origin cookies don't work cleanly between the Tauri webview origin
// (tauri://localhost) and the backend's http://127.0.0.1:8756 origin, so
// auth uses a bearer token instead of a session cookie — see
// backend/app/services/auth_service.py for the full rationale.
let authToken: string | null = null

export function setAuthToken(token: string | null): void {
  authToken = token
}

class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (authToken) headers.set('Authorization', `Bearer ${authToken}`)
  if (init?.body) headers.set('Content-Type', 'application/json')

  const response = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (!response.ok) {
    throw new ApiError(`Request to ${path} failed: ${response.status}`, response.status)
  }
  return response.json() as Promise<T>
}

export { ApiError }

export function getTopology(): Promise<TopologyGraph> {
  return request<TopologyGraph>('/topology')
}

export function pingDevice(deviceId: string): Promise<PingResult> {
  return request<PingResult>(`/devices/${encodeURIComponent(deviceId)}/ping`, {
    method: 'POST',
  })
}

export function getBootstrapStatus(): Promise<{ needs_bootstrap: boolean }> {
  return request('/auth/bootstrap-status')
}

export function bootstrap(username: string, password: string): Promise<LoginResponse> {
  return request('/auth/bootstrap', {
    method: 'POST',
    body: JSON.stringify({ username, password, role: 'admin' }),
  })
}

export function login(username: string, password: string): Promise<LoginResponse> {
  return request('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export function logout(): Promise<void> {
  return request('/auth/logout', { method: 'POST' })
}

export function getMe(): Promise<User> {
  return request('/auth/me')
}
