import { Navigate, Outlet } from 'react-router-dom'

import { useAuthStore } from './authStore'
import { useAuthBootstrap } from './useAuth'

export function RequireAuth() {
  useAuthBootstrap()
  const status = useAuthStore((s) => s.status)

  if (status === 'idle') {
    return <div className="text-muted-foreground p-8 text-sm">Loading…</div>
  }

  if (status === 'unauthenticated') {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
