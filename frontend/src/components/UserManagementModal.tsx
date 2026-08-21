import { useEffect, useState, type FormEvent } from 'react'
import { useAuth } from '../context/auth-context'
import { ApiError, createUser, deleteUser, listUsers } from '../lib/api'
import type { Role, User } from '../types/auth'

interface UserManagementModalProps {
  onClose: () => void
}

const ROLES: Role[] = ['viewer', 'operator', 'admin']

export function UserManagementModal({ onClose }: UserManagementModalProps) {
  const { user: currentUser } = useAuth()
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [listError, setListError] = useState<string | null>(null)

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<Role>('viewer')
  const [creating, setCreating] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  async function refresh() {
    try {
      setUsers(await listUsers())
      setListError(null)
    } catch {
      setListError('Failed to load users')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleCreate(e: FormEvent) {
    e.preventDefault()
    setFormError(null)
    if (password.length < 8) {
      setFormError('Password must be at least 8 characters')
      return
    }

    setCreating(true)
    try {
      await createUser(username, password, role)
      setUsername('')
      setPassword('')
      setRole('viewer')
      await refresh()
    } catch (err) {
      setFormError(
        err instanceof ApiError && err.status === 409
          ? 'That username is already taken'
          : 'Failed to create account',
      )
    } finally {
      setCreating(false)
    }
  }

  async function handleDelete(target: User) {
    if (!window.confirm(`Delete account "${target.username}"?`)) return
    try {
      await deleteUser(target.id)
      await refresh()
    } catch (err) {
      setListError(
        err instanceof ApiError && err.status === 409
          ? 'Cannot delete the last admin account while other accounts remain'
          : 'Failed to delete account',
      )
    }
  }

  return (
    <div
      className="fixed inset-0 z-20 flex items-center justify-center bg-black/30 p-4"
      onClick={onClose}
    >
      <div
        className="max-h-[90vh] w-full max-w-lg overflow-auto rounded-lg bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">Manage Users</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="flex min-h-11 min-w-11 touch-manipulation items-center justify-center rounded text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          >
            ✕
          </button>
        </div>

        {listError && <p className="mb-3 text-sm text-red-500">{listError}</p>}

        {loading ? (
          <p className="mb-6 text-sm text-slate-400">Loading…</p>
        ) : (
          <ul className="mb-6 divide-y divide-slate-100 border-y border-slate-100">
            {users.map((u) => (
              <li key={u.id} className="flex items-center justify-between gap-2 py-2">
                <div>
                  <p className="text-sm font-medium text-slate-900">
                    {u.username}
                    {u.id === currentUser?.id && (
                      <span className="ml-2 text-xs text-slate-400">(you)</span>
                    )}
                  </p>
                  <p className="text-xs capitalize text-slate-400">{u.role}</p>
                </div>
                <button
                  type="button"
                  onClick={() => void handleDelete(u)}
                  className="min-h-11 touch-manipulation rounded border border-red-200 px-3 text-sm text-red-600 hover:bg-red-50"
                >
                  Delete
                </button>
              </li>
            ))}
          </ul>
        )}

        <h3 className="mb-2 text-sm font-medium text-slate-700">Create account</h3>
        <form onSubmit={handleCreate} className="flex flex-col gap-3">
          <input
            className="min-h-11 w-full rounded border border-slate-300 px-3 py-2 text-base"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
          <input
            type="password"
            className="min-h-11 w-full rounded border border-slate-300 px-3 py-2 text-base"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <select
            className="min-h-11 w-full rounded border border-slate-300 px-3 py-2 text-base"
            value={role}
            onChange={(e) => setRole(e.target.value as Role)}
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
          {formError && <p className="text-sm text-red-500">{formError}</p>}
          <button
            type="submit"
            disabled={creating}
            className="min-h-11 touch-manipulation rounded bg-blue-600 py-2 text-base font-medium text-white disabled:opacity-50"
          >
            Create account
          </button>
        </form>
      </div>
    </div>
  )
}
