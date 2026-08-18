import { useEffect, useState, type ReactNode } from 'react'
import * as api from '../lib/api'
import { ApiError, setAuthToken } from '../lib/api'
import type { LoginResponse, User } from '../types/auth'
import { AuthContext, type AuthStatus } from './auth-context'

const TOKEN_STORAGE_KEY = 'ovv_auth_token'
const BACKEND_RETRY_DELAY_MS = 1_000

// The backend sidecar (a frozen PyInstaller exe in production) can take a
// few seconds to start listening after the window opens. A plain fetch
// failure here means "not up yet", not "logged out" — retry instead of
// assuming the latter, which used to hide the bootstrap screen entirely.
async function waitForBackend<T>(fn: () => Promise<T>): Promise<T> {
  for (;;) {
    try {
      return await fn()
    } catch (err) {
      if (err instanceof ApiError) throw err
      await new Promise((resolve) => setTimeout(resolve, BACKEND_RETRY_DELAY_MS))
    }
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading')
  const [user, setUser] = useState<User | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void initialize()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function initialize() {
    const storedToken = localStorage.getItem(TOKEN_STORAGE_KEY)
    if (storedToken) {
      setAuthToken(storedToken)
      try {
        const me = await waitForBackend(() => api.getMe())
        setUser(me)
        setStatus('logged-in')
        return
      } catch {
        // Backend reachable but rejected the token (invalid/expired) —
        // fall through to a fresh login.
        localStorage.removeItem(TOKEN_STORAGE_KEY)
        setAuthToken(null)
      }
    }

    const { needs_bootstrap } = await waitForBackend(() => api.getBootstrapStatus())
    setStatus(needs_bootstrap ? 'needs-bootstrap' : 'logged-out')
  }

  function applySession(response: LoginResponse) {
    localStorage.setItem(TOKEN_STORAGE_KEY, response.token)
    setAuthToken(response.token)
    setUser(response.user)
    setStatus('logged-in')
  }

  async function login(username: string, password: string) {
    setError(null)
    try {
      applySession(await api.login(username, password))
    } catch {
      setError('Incorrect username or password')
      throw new Error('login failed')
    }
  }

  async function bootstrapAccount(username: string, password: string) {
    setError(null)
    try {
      applySession(await api.bootstrap(username, password))
    } catch {
      setError('Failed to create the admin account')
      throw new Error('bootstrap failed')
    }
  }

  async function logout() {
    try {
      await api.logout()
    } finally {
      localStorage.removeItem(TOKEN_STORAGE_KEY)
      setAuthToken(null)
      setUser(null)
      setStatus('logged-out')
    }
  }

  return (
    <AuthContext.Provider
      value={{ status, user, error, login, bootstrap: bootstrapAccount, logout }}
    >
      {children}
    </AuthContext.Provider>
  )
}
