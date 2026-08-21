import { Link } from 'react-router-dom'

import { OrderflowLogo } from '@/assets/logo'
import { Button } from '@/components/ui/button'

// Catch-all 404 -- rendered outside <RequireAuth> in App.tsx so it's
// reachable regardless of auth state (a nonexistent URL shouldn't force a
// login redirect first).
export function NotFoundPage() {
  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-4 px-4 text-center">
      <OrderflowLogo className="size-10 opacity-70" />
      <div className="space-y-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">Page not found</h1>
        <p className="text-muted-foreground text-sm">
          The page you're looking for doesn't exist or may have moved.
        </p>
      </div>
      <Button asChild>
        <Link to="/dashboard">Back to dashboard</Link>
      </Button>
    </div>
  )
}
