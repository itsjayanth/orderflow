import { Link, Outlet } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard' },
  { to: '/orders', label: 'Orders' },
  { to: '/catalog', label: 'Catalog' },
  { to: '/customers', label: 'Customers' },
  { to: '/onboarding', label: 'Onboarding' },
]

export function Layout() {
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
        </nav>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
