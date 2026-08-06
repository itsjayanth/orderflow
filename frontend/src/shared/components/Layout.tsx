import { Link, Outlet } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { useLogout, useMe } from '@/features/auth/useAuth'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard' },
  { to: '/orders', label: 'Orders' },
  { to: '/catalog', label: 'Catalog' },
  { to: '/customers', label: 'Customers' },
  { to: '/onboarding', label: 'Onboarding' },
  { to: '/settings', label: 'Settings' },
]

export function Layout() {
  const me = useMe()
  const logout = useLogout()

  return (
    <div className="min-h-svh">
      <header className="border-border border-b">
        <nav className="mx-auto flex max-w-5xl items-center gap-6 px-6 py-4">
          <span className="font-semibold">Orderflow</span>
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className="text-muted-foreground hover:text-foreground text-sm"
            >
              {item.label}
            </Link>
          ))}
          <span className="flex-1" />
          {me.data && (
            <span className="text-muted-foreground text-sm">{me.data.merchant.business_name}</span>
          )}
          <Button variant="ghost" size="sm" onClick={() => logout.mutate()}>
            Log out
          </Button>
        </nav>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
