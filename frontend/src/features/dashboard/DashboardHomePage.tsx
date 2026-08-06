import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { useMe } from '@/features/auth/useAuth'
import { useOnboardingStatus } from '@/features/onboarding/useOnboarding'
import { useOrders } from '@/features/orders/useOrders'
import type { FulfillmentStatus } from '@/shared/api/types'
import { StatusBadge } from '@/shared/components/StatusBadge'

function isToday(isoDate: string): boolean {
  const date = new Date(isoDate)
  const now = new Date()
  return (
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  )
}

function StatCard({ label, value, tone }: { label: string; value: number; tone?: 'gold' }) {
  return (
    <Card className="p-5">
      <p className="text-muted-foreground text-sm">{label}</p>
      <p
        className={`mt-1 font-serif text-3xl ${tone === 'gold' ? 'text-brand-gold-foreground' : ''}`}
      >
        {value}
      </p>
    </Card>
  )
}

export function DashboardHomePage() {
  const me = useMe()
  const onboarding = useOnboardingStatus()
  const { data: orders, isLoading } = useOrders()

  const todaysOrders = orders?.filter((o) => isToday(o.placed_at)) ?? []
  const countByStatus = (status: FulfillmentStatus) =>
    orders?.filter((o) => o.fulfillment_status === status).length ?? 0

  const recentOrders = [...(orders ?? [])]
    .sort((a, b) => new Date(b.placed_at).getTime() - new Date(a.placed_at).getTime())
    .slice(0, 5)

  const businessName = me.data?.merchant.business_name

  return (
    <div className="space-y-8">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">
          {businessName ? `Welcome back, ${businessName}` : 'Dashboard'}
        </h1>
        <p className="text-muted-foreground text-sm">Here's what's happening today.</p>
      </div>

      {onboarding.data && onboarding.data.onboarding_status !== 'live' && (
        <Card className="border-brand-gold/40 bg-brand-gold/10 flex flex-wrap items-center justify-between gap-4 p-5">
          <div>
            <p className="font-medium">Finish setting up your restaurant</p>
            <p className="text-muted-foreground text-sm">
              Connect WhatsApp, add your kitchen details, and list a menu item to start taking
              orders.
            </p>
          </div>
          <Button asChild size="sm">
            <Link to="/onboarding">Continue setup</Link>
          </Button>
        </Card>
      )}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="Today's orders" value={todaysOrders.length} />
        <StatCard label="New" value={countByStatus('new')} tone="gold" />
        <StatCard label="Preparing" value={countByStatus('preparing')} />
        <StatCard label="Ready" value={countByStatus('ready')} />
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium">Recent orders</h2>
          <Link to="/orders" className="text-primary text-sm font-medium hover:underline">
            View all
          </Link>
        </div>

        <Card className="divide-y overflow-hidden py-0">
          {isLoading && <p className="text-muted-foreground p-5 text-sm">Loading…</p>}
          {!isLoading && recentOrders.length === 0 && (
            <p className="text-muted-foreground p-5 text-sm">
              No orders yet -- they'll show up here the moment a customer checks out.
            </p>
          )}
          {recentOrders.map((order) => (
            <Link
              key={order.order_id}
              to={`/orders/${order.order_id}`}
              className="hover:bg-muted/40 flex items-center justify-between gap-4 p-4 transition-colors duration-150"
            >
              <div>
                <p className="text-sm font-medium">
                  {order.currency} {order.total}
                </p>
                <p className="text-muted-foreground text-xs">
                  {new Date(order.placed_at).toLocaleString()}
                </p>
              </div>
              {order.fulfillment_status && <StatusBadge status={order.fulfillment_status} />}
            </Link>
          ))}
        </Card>
      </div>

      <div className="text-muted-foreground flex flex-wrap gap-x-6 gap-y-2 text-sm">
        <Link to="/catalog" className="hover:text-foreground hover:underline">
          Manage catalog
        </Link>
        <Link to="/customers" className="hover:text-foreground hover:underline">
          View customers
        </Link>
        <Link to="/settings" className="hover:text-foreground hover:underline">
          Payment &amp; WhatsApp settings
        </Link>
      </div>
    </div>
  )
}
