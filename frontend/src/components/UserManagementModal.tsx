import { useEffect, useState, type FormEvent } from 'react'
import { useAuth } from '../context/auth-context'
import { ApiError, createUser, deleteUser, listUsers, updateUserPassword } from '../lib/api'
import type { Role, User } from '../types/auth'

interface UserManagementModalProps {
  onClose: () => void
}

const ROLES: Role[] = ['viewer', 'operator', 'admin']

export function UserManagementModal({ onClose }: UserManagementModalProps) {
  const { user: currentUser, logout } = useAuth()
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [listError, setListError] = useState<string | null>(null)

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<Role>('viewer')
  const [creating, setCreating] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const [editingUserId, setEditingUserId] = useState<number | null>(null)
  const [editPassword, setEditPassword] = useState('')
  const [editError, setEditError] = useState<string | null>(null)
  const [savingPassword, setSavingPassword] = useState(false)

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

  function startEditing(target: User) {
    setEditingUserId(target.id)
    setEditPassword('')
    setEditError(null)
  }

  async function handleSavePassword(target: User) {
    setEditError(null)
    if (editPassword.length < 8) {
      setEditError('Password must be at least 8 characters')
      return
    }

    setSavingPassword(true)
    try {
      await updateUserPassword(target.id, editPassword)
      setEditingUserId(null)
      setEditPassword('')
      // Changing a password invalidates that account's sessions server-side
      // (see auth_service.update_password) — including this one, if it's
      // our own. Sign out immediately instead of leaving the UI looking
      // logged in while every subsequent request silently 401s.
      if (target.id === currentUser?.id) {
        await logout()
      }
    } catch {
      setEditError('Failed to change password')
    } finally {
      setSavingPassword(false)
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
              <li key={u.id} className="py-2">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="text-sm font-medium text-slate-900">
                      {u.username}
                      {u.id === currentUser?.id && (
                        <span className="ml-2 text-xs text-slate-400">(you)</span>
                      )}
                    </p>
                    <p className="text-xs capitalize text-slate-400">{u.role}</p>
                  </div>
                  {u.role === 'admin' ? (
                    editingUserId !== u.id && (
                      <button
                        type="button"
                        onClick={() => startEditing(u)}
                        className="min-h-11 touch-manipulation rounded border border-slate-300 px-3 text-sm text-slate-600 hover:bg-slate-100"
                      >
                        Edit
                      </button>
                    )
                  ) : (
                    <button
                      type="button"
                      onClick={() => void handleDelete(u)}
                      className="min-h-11 touch-manipulation rounded border border-red-200 px-3 text-sm text-red-600 hover:bg-red-50"
                    >
                      Delete
                    </button>
                  )}
                </div>

                {editingUserId === u.id && (
                  <div className="mt-2 flex flex-col gap-2 rounded border border-slate-200 bg-slate-50 p-3">
                    <label className="text-xs text-slate-500" htmlFor={`new-password-${u.id}`}>
                      New password for {u.username}
                    </label>
                    <input
                      id={`new-password-${u.id}`}
                      type="password"
                      autoFocus
                      className="min-h-11 w-full rounded border border-slate-300 px-3 py-2 text-base"
                      value={editPassword}
                      onChange={(e) => setEditPassword(e.target.value)}
                    />
                    {editError && <p className="text-sm text-red-500">{editError}</p>}
                    <div className="flex gap-2">
                      <button
                        type="button"
                        disabled={savingPassword}
                        onClick={() => void handleSavePassword(u)}
                        className="min-h-11 flex-1 touch-manipulation rounded bg-blue-600 text-sm font-medium text-white disabled:opacity-50"
                      >
                        Save
                      </button>
                      <button
                        type="button"
                        onClick={() => setEditingUserId(null)}
                        className="min-h-11 flex-1 touch-manipulation rounded border border-slate-300 text-sm text-slate-600 hover:bg-slate-100"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
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
