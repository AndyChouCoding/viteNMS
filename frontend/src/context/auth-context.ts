import { createContext, useContext } from 'react'
import type { User } from '../types/auth'

export type AuthStatus = 'loading' | 'needs-bootstrap' | 'logged-out' | 'logged-in'

export interface AuthContextValue {
  status: AuthStatus
  user: User | null
  error: string | null
  login: (username: string, password: string) => Promise<void>
  bootstrap: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
