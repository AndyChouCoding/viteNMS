import { useState, type FormEvent } from 'react'
import { useAuth } from '../context/auth-context'

export function AuthScreen() {
  const { status, error, login, bootstrap } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  const isBootstrap = status === 'needs-bootstrap'

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setLocalError(null)

    if (isBootstrap && password !== confirmPassword) {
      setLocalError('Passwords do not match')
      return
    }
    if (password.length < 8) {
      setLocalError('Password must be at least 8 characters')
      return
    }

    setSubmitting(true)
    try {
      if (isBootstrap) {
        await bootstrap(username, password)
      } else {
        await login(username, password)
      }
    } catch {
      // AuthContext already recorded a user-facing error message
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex h-screen w-screen items-center justify-center bg-slate-50">
      <form
        onSubmit={handleSubmit}
        className="w-80 rounded-lg border border-slate-200 bg-white p-6 shadow-sm"
      >
        <h1 className="mb-1 text-lg font-semibold text-slate-900">Open Vision Vite</h1>
        <p className="mb-6 text-sm text-slate-500">
          {isBootstrap ? 'Create the first administrator account' : 'Sign in to continue'}
        </p>

        <label className="mb-1 block text-sm text-slate-600" htmlFor="username">
          Username
        </label>
        <input
          id="username"
          className="mb-4 w-full rounded border border-slate-300 px-3 py-2 text-base"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoFocus
          required
        />

        <label className="mb-1 block text-sm text-slate-600" htmlFor="password">
          Password
        </label>
        <input
          id="password"
          type="password"
          className="mb-4 w-full rounded border border-slate-300 px-3 py-2 text-base"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />

        {isBootstrap && (
          <>
            <label className="mb-1 block text-sm text-slate-600" htmlFor="confirm-password">
              Confirm password
            </label>
            <input
              id="confirm-password"
              type="password"
              className="mb-4 w-full rounded border border-slate-300 px-3 py-2 text-base"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
            />
          </>
        )}

        {(localError ?? error) && (
          <p className="mb-4 text-sm text-red-500">{localError ?? error}</p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded bg-blue-600 py-2 text-base font-medium text-white disabled:opacity-50"
        >
          {isBootstrap ? 'Create account' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}
