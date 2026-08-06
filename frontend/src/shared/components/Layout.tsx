import { NavLink, Outlet } from 'react-router-dom'

import { OrderflowLogo } from '@/assets/logo'
import { Button } from '@/components/ui/button'
import { useLogout, useMe } from '@/features/auth/useAuth'
import { cn } from '@/lib/utils'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', end: true },
  { to: '/orders', label: 'Orders' },
  { to: '/catalog', label: 'Catalog' },
  { to: '/customers', label: 'Customers' },
  { to: '/onboarding', label: 'Onboarding' },
  { to: '/settings', label: 'Settings' },
]

function initials(name: string) {
  return name
    .split(' ')
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

export function Layout() {
  const me = useMe()
  const logout = useLogout()

  return (
    <div className="min-h-svh">
      <header className="border-border/70 bg-background/85 sticky top-0 z-10 border-b backdrop-blur-sm">
        <nav className="mx-auto flex max-w-6xl items-center gap-1 px-4 py-3 sm:px-6">
          <span className="mr-4 flex shrink-0 items-center gap-2">
            <OrderflowLogo className="size-6" />
            <span className="text-primary font-serif text-lg tracking-tight">Orderflow</span>
          </span>
          <div className="flex flex-1 items-center gap-1 overflow-x-auto">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    'rounded-md px-3 py-1.5 text-sm font-medium whitespace-nowrap transition-colors duration-150',
                    isActive
                      ? 'bg-secondary text-foreground'
                      : 'text-muted-foreground hover:text-foreground hover:bg-secondary/60',
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </div>
          {me.data && (
            <div className="ml-4 hidden items-center gap-2 md:flex">
              <span className="bg-primary text-primary-foreground flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold">
                {initials(me.data.merchant.business_name)}
              </span>
              <span className="text-muted-foreground text-sm">
                {me.data.merchant.business_name}
              </span>
            </div>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="ml-2 shrink-0"
            onClick={() => logout.mutate()}
          >
            Log out
          </Button>
        </nav>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">
        <Outlet />
      </main>
    </div>
  )
}
