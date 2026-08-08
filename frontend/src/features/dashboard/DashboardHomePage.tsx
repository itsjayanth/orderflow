import { useState } from 'react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { useMe } from '@/features/auth/useAuth'
import { useOnboardingStatus } from '@/features/onboarding/useOnboarding'
import { useOrderSummary } from '@/features/orders/useOrderSummary'
import { useOrders } from '@/features/orders/useOrders'
import type { FulfillmentStatus } from '@/shared/api/types'
import { DateRangeFilter, type DateRangeValue } from '@/shared/components/DateRangeFilter'
import { StatusBadge } from '@/shared/components/StatusBadge'
import { formatOrderNumber } from '@/shared/lib/orderNumber'
import { formatPhoneNumber } from '@/shared/lib/phoneNumber'

function formatCurrency(value: string | undefined, currency = 'INR'): string {
  const amount = Number(value ?? 0)
  const formatted = new Intl.NumberFormat('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount)
  return `${currency} ${formatted}`
}

// One consistent numeric scale used everywhere on the page -- the hero
// revenue figure is the largest step up from this base, everything else
// (lifecycle cards, COD card) shares it, rather than each card picking its
// own size/weight ad hoc.
const STAT_NUMBER_CLASS = 'font-serif font-bold tabular-nums tracking-tight text-foreground'
const STAT_LABEL_CLASS = 'text-muted-foreground text-xs font-semibold tracking-wide uppercase'

type LifecycleCard = {
  label: string
  status: FulfillmentStatus
  count: number
  hint: string
}

function LifecycleStatCard({ label, status, count, hint }: LifecycleCard) {
  return (
    <Link
      to={`/orders?status=${status}`}
      title={hint}
      className="group border-border bg-card hover:border-primary/40 relative overflow-hidden rounded-xl border p-5 shadow-sm transition-all duration-150 hover:shadow-md"
    >
      <div className="flex items-start justify-between">
        <p className={STAT_LABEL_CLASS}>{label}</p>
        <StatusBadge status={status} />
      </div>
      <p className={`${STAT_NUMBER_CLASS} mt-3 text-4xl`}>{count}</p>
      <p className="text-muted-foreground mt-2 text-xs opacity-0 transition-opacity duration-150 group-hover:opacity-100">
        {hint} · View orders →
      </p>
    </Link>
  )
}

function isToday(isoDate: string): boolean {
  const date = new Date(isoDate)
  const now = new Date()
  return (
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  )
}

export function DashboardHomePage() {
  const me = useMe()
  const onboarding = useOnboardingStatus()
  const [range, setRange] = useState<DateRangeValue>({})
  const { data: orders, isLoading } = useOrders(range)
  const { data: summary } = useOrderSummary(range)

  const todaysOrders = orders?.filter((o) => isToday(o.placed_at)) ?? []
  const recentOrders = [...(orders ?? [])]
    .sort((a, b) => new Date(b.placed_at).getTime() - new Date(a.placed_at).getTime())
    .slice(0, 5)

  const businessName = me.data?.merchant.business_name

  const lifecycleCards: LifecycleCard[] = [
    {
      label: 'New',
      status: 'new',
      count: summary?.new_orders ?? 0,
      hint: 'Just placed, not yet started',
    },
    {
      label: 'Preparing',
      status: 'preparing',
      count: summary?.preparing_orders ?? 0,
      hint: 'In the kitchen right now',
    },
    {
      label: 'Ready',
      status: 'ready',
      count: summary?.ready_orders ?? 0,
      hint: 'Waiting for pickup/delivery',
    },
    {
      label: 'Delivered',
      status: 'completed',
      count: summary?.completed_orders ?? 0,
      hint: 'Successfully completed',
    },
    {
      label: 'Failed',
      status: 'cancelled',
      count: summary?.cancelled_orders ?? 0,
      hint: 'Cancelled before completion',
    },
  ]

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold">
            {businessName ? `Welcome back, ${businessName}` : 'Dashboard'}
          </h1>
          <p className="text-muted-foreground text-sm">Here's what's happening today.</p>
        </div>
        <DateRangeFilter value={range} onChange={setRange} />
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

      {/* Hero revenue card -- the number the owner actually cares about,
          given more visual weight than any operational stat below it. */}
      <div className="from-brand-gold/15 via-brand-gold/5 border-brand-gold/30 relative overflow-hidden rounded-2xl border bg-gradient-to-br to-transparent p-8 shadow-sm">
        <div className="grid gap-8 sm:grid-cols-[2fr_1fr]">
          <div>
            <p className={STAT_LABEL_CLASS}>Total revenue generated</p>
            <p className={`${STAT_NUMBER_CLASS} text-primary mt-1 text-6xl sm:text-7xl`}>
              {formatCurrency(summary?.revenue_generated)}
            </p>
            <p className="text-muted-foreground mt-2 text-sm">
              Across {summary?.total_orders ?? 0} orders (excludes cancelled)
            </p>
          </div>
          <div className="border-border/60 flex flex-col justify-center gap-1 border-t pt-4 sm:border-t-0 sm:border-l sm:pt-0 sm:pl-8">
            <p className={STAT_LABEL_CLASS}>Amount collected</p>
            <p className={`${STAT_NUMBER_CLASS} text-3xl`}>
              {formatCurrency(summary?.amount_collected)}
            </p>
            <p className={`${STAT_LABEL_CLASS} mt-3`}>Today's orders</p>
            <p className={`${STAT_NUMBER_CLASS} text-3xl`}>{todaysOrders.length}</p>
          </div>
        </div>
      </div>

      <div>
        <h2 className="mb-3 text-lg font-medium">Order lifecycle</h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          {lifecycleCards.map((card) => (
            <LifecycleStatCard key={card.status} {...card} />
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <Link
          to="/orders"
          title="Orders paid by cash/UPI on pickup or delivery"
          className="group border-border bg-card hover:border-primary/40 rounded-xl border p-5 shadow-sm transition-all duration-150 hover:shadow-md"
        >
          <p className={STAT_LABEL_CLASS}>COD orders</p>
          <p className={`${STAT_NUMBER_CLASS} mt-3 text-4xl`}>{summary?.cod_orders ?? 0}</p>
          <p className="text-muted-foreground mt-2 text-xs opacity-0 transition-opacity duration-150 group-hover:opacity-100">
            View all orders →
          </p>
        </Link>
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
                  {formatOrderNumber(order.order_number)} · {order.currency} {order.total}
                </p>
                <p className="text-muted-foreground text-xs">
                  {order.customer_name ?? formatPhoneNumber(order.customer_whatsapp_number)} ·{' '}
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
