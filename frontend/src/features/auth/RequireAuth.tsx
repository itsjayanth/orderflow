import { Navigate, Outlet } from 'react-router-dom'

import { OrderflowLogo } from '@/assets/logo'
import { Skeleton } from '@/components/ui/skeleton'

import { useAuthStore } from './authStore'
import { useAuthBootstrap } from './useAuth'

// A shell-shaped skeleton (sidebar + top bar + content blocks) that
// approximates Layout.tsx's authenticated shell, so the brief window while
// the silent-refresh bootstrap resolves reads as "the app is loading" rather
// than a jarring blank-then-text flash.
function AuthShellSkeleton() {
  return (
    <div className="flex min-h-svh" aria-busy="true" aria-live="polite">
      <span className="sr-only">Loading…</span>
      <aside className="hidden h-svh w-64 shrink-0 flex-col border-r p-4 lg:flex">
        <div className="mb-6 flex items-center gap-2">
          <OrderflowLogo className="size-7 shrink-0 animate-pulse opacity-70" />
          <Skeleton className="h-5 w-24" />
        </div>
        <div className="flex flex-1 flex-col gap-2">
          {Array.from({ length: 6 }).map((_, index) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: static skeleton placeholder rows, never reordered
            <Skeleton key={index} className="h-9 w-full rounded-lg" />
          ))}
        </div>
        <Skeleton className="h-11 w-full rounded-lg" />
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center justify-between border-b px-4 py-3 sm:px-6">
          <OrderflowLogo className="size-6 opacity-70 lg:hidden" />
          <div className="ml-auto flex items-center gap-2">
            <Skeleton className="size-8 rounded-full" />
          </div>
        </div>
        <main className="mx-auto w-full max-w-6xl flex-1 space-y-6 px-4 py-8 sm:px-6 sm:py-10">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-40 w-full rounded-xl" />
          <Skeleton className="h-64 w-full rounded-xl" />
        </main>
      </div>
    </div>
  )
}

export function RequireAuth() {
  useAuthBootstrap()
  const status = useAuthStore((s) => s.status)

  if (status === 'idle') {
    return <AuthShellSkeleton />
  }

  if (status === 'unauthenticated') {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
