import { useEffect, useRef, useState } from 'react'
import { useAuth } from '../context/auth-context'

interface AccountMenuProps {
  onManageUsers: () => void
}

export function AccountMenu({ onManageUsers }: AccountMenuProps) {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handlePointerDown)
    return () => document.removeEventListener('mousedown', handlePointerDown)
  }, [])

  if (!user) return null

  return (
    <div
      ref={containerRef}
      className="relative"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex h-11 w-11 touch-manipulation items-center justify-center rounded-full border border-slate-300 text-slate-500 hover:bg-slate-100"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-6 w-6">
          <circle cx="12" cy="8" r="3.5" />
          <path d="M4.5 19.5c1.5-3.5 4.5-5.5 7.5-5.5s6 2 7.5 5.5" strokeLinecap="round" />
        </svg>
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full z-10 mt-1 w-56 rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
        >
          <div className="border-b border-slate-100 px-4 py-2">
            <p className="truncate text-sm font-medium text-slate-900">{user.username}</p>
            <p className="text-xs capitalize text-slate-400">{user.role}</p>
          </div>
          {user.role === 'admin' && (
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false)
                onManageUsers()
              }}
              className="block min-h-11 w-full touch-manipulation px-4 text-left text-sm text-slate-700 hover:bg-slate-100"
            >
              Manage Users
            </button>
          )}
          <button
            type="button"
            role="menuitem"
            onClick={() => void logout()}
            className="block min-h-11 w-full touch-manipulation px-4 text-left text-sm text-slate-700 hover:bg-slate-100"
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  )
}
