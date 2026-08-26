import {
  CheckCircle,
  Clock,
  Flame,
  Inbox,
  type LucideIcon,
  PackageCheck,
  Sparkles,
  XCircle,
} from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useMe } from '@/features/auth/useAuth'
import { useOnboardingStatus } from '@/features/onboarding/useOnboarding'
import { useOrderSummary } from '@/features/orders/useOrderSummary'
import { useOrders } from '@/features/orders/useOrders'
import type { FulfillmentStatus } from '@/shared/api/types'
import { DateRangeFilter, type DateRangeValue } from '@/shared/components/DateRangeFilter'
import { EmptyState } from '@/shared/components/EmptyState'
import { PageHeader } from '@/shared/components/PageHeader'
import { StatusBadge } from '@/shared/components/StatusBadge'
import { formatCurrency } from '@/shared/lib/currency'
import { formatOrderNumber } from '@/shared/lib/orderNumber'
import { formatPhoneNumber } from '@/shared/lib/phoneNumber'

import { DashboardTrendChart } from './DashboardTrendChart'

const STAT_NUMBER_CLASS = 'font-serif font-bold tabular-nums tracking-tight text-foreground'
const STAT_LABEL_CLASS = 'text-muted-foreground text-xs font-semibold tracking-wide uppercase'

// Mirrors StatusActionsMenu's STATUS_ICONS mapping (features/orders/
// StatusActionsMenu.tsx) so the same status reads with the same icon
// everywhere in the app -- kept as a local copy rather than an import
// since that file doesn't currently export it and this phase's change
// surface is meant to stay inside the dashboard feature.
const LIFECYCLE_ICONS: Record<FulfillmentStatus, LucideIcon> = {
  new: Clock,
  processing: Flame,
  ready: CheckCircle,
  completed: PackageCheck,
  cancelled: XCircle,
}

type LifecycleCard = { label: string; status: FulfillmentStatus; count: number; hint: string }

function LifecycleStatCard({
  label,
  status,
  count,
  hint,
  isLoading,
}: LifecycleCard & { isLoading: boolean }) {
  const Icon = LIFECYCLE_ICONS[status]
  return (
    <Link
      to={`/orders?status=${status}`}
      title={hint}
      className="group border-border bg-card hover:border-primary/40 relative overflow-hidden rounded-xl border p-5 shadow-sm transition-all duration-150 hover:shadow-md"
    >
      <div className="flex items-start justify-between">
        <p className={STAT_LABEL_CLASS}>{label}</p>
        <Icon className="text-muted-foreground group-hover:text-primary size-4 transition-colors duration-150" />
      </div>
      {isLoading ? (
        <Skeleton className="mt-3 h-9 w-14" />
      ) : (
        <p className={`${STAT_NUMBER_CLASS} mt-3 text-4xl`}>{count}</p>
      )}
      <p className="text-muted-foreground mt-2 text-xs opacity-0 transition-opacity duration-150 group-hover:opacity-100">
        {hint} · View orders →
      </p>
    </Link>
  )
}

export function DashboardHomePage() {
  const me = useMe()
  const onboarding = useOnboardingStatus()
  const [range, setRange] = useState<DateRangeValue>({})
  const { data: orders, isLoading } = useOrders(range) // full array, no pagination, polls 5s
  const { data: summary, isLoading: isSummaryLoading } = useOrderSummary(range) // polls 5s

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
      label: 'Processing',
      status: 'processing',
      count: summary?.processing_orders ?? 0,
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
      <PageHeader
        title={businessName ? `Welcome back, ${businessName}` : 'Dashboard'}
        description="Here's what's happening today."
        actions={<DateRangeFilter value={range} onChange={setRange} />}
      />

      {onboarding.data && onboarding.data.onboarding_status !== 'live' && (
        <Card className="border-brand-gold/40 bg-brand-gold/10 flex flex-wrap items-center justify-between gap-4 p-5">
          <div className="flex items-center gap-4">
            <div className="bg-brand-gold/25 text-brand-gold-foreground flex size-11 shrink-0 items-center justify-center rounded-full">
              <Sparkles className="size-5" />
            </div>
            <div>
              <p className="font-medium">Finish setting up your restaurant</p>
              <p className="text-muted-foreground text-sm">
                Connect WhatsApp, add your kitchen details, and list a menu item to start taking
                orders.
              </p>
            </div>
          </div>
          <Button asChild size="sm">
            <Link to="/onboarding">Continue setup</Link>
          </Button>
        </Card>
      )}

      {/* Hero revenue card */}
      <div className="from-brand-gold/15 via-brand-gold/5 border-brand-gold/30 relative overflow-hidden rounded-2xl border bg-gradient-to-br to-transparent p-8 shadow-sm">
        <div className="grid gap-8 sm:grid-cols-[2fr_1fr]">
          <div>
            <p className={STAT_LABEL_CLASS}>Total revenue made</p>
            {isSummaryLoading ? (
              <Skeleton className="mt-2 h-14 w-56 sm:h-16 sm:w-72" />
            ) : (
              <p className={`${STAT_NUMBER_CLASS} text-primary mt-1 text-6xl sm:text-7xl`}>
                {formatCurrency(summary?.revenue_generated)}
              </p>
            )}
          </div>
          <div className="border-border/60 flex flex-col justify-center gap-1 border-t pt-4 sm:border-t-0 sm:border-l sm:pt-0 sm:pl-8">
            <p className={STAT_LABEL_CLASS}>Total orders</p>
            {isSummaryLoading ? (
              <Skeleton className="mt-1 h-11 w-20" />
            ) : (
              <p className={`${STAT_NUMBER_CLASS} text-5xl`}>{summary?.total_orders ?? 0}</p>
            )}
          </div>
        </div>
      </div>

      <DashboardTrendChart orders={orders} isLoading={isLoading} />

      <div>
        <h2 className="mb-3 text-lg font-medium">Order lifecycle</h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          {lifecycleCards.map((card) => (
            <LifecycleStatCard key={card.status} {...card} isLoading={isSummaryLoading} />
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
          {isSummaryLoading ? (
            <Skeleton className="mt-3 h-9 w-14" />
          ) : (
            <p className={`${STAT_NUMBER_CLASS} mt-3 text-4xl`}>{summary?.cod_orders ?? 0}</p>
          )}
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
        <Card className="overflow-hidden py-0">
          {isLoading && (
            <div className="divide-y">
              {Array.from({ length: 5 }).map((_, i) => (
                // Transient placeholder rows with no identity of their own -- index keys are fine here.
                <div
                  // biome-ignore lint/suspicious/noArrayIndexKey: skeleton placeholders have no stable identity
                  key={`recent-orders-skeleton-${i}`}
                  className="flex items-center justify-between gap-4 p-4"
                >
                  <div className="space-y-2">
                    <Skeleton className="h-4 w-40" />
                    <Skeleton className="h-3 w-56" />
                  </div>
                  <Skeleton className="h-5 w-20 rounded-full" />
                </div>
              ))}
            </div>
          )}
          {!isLoading && recentOrders.length === 0 && (
            <EmptyState
              icon={Inbox}
              title="No orders yet -- they'll show up here the moment a customer checks out."
            />
          )}
          {!isLoading && recentOrders.length > 0 && (
            <div className="divide-y">
              {recentOrders.map((order) => (
                <Link
                  key={order.order_id}
                  to={`/orders/${order.order_id}`}
                  className="hover:bg-muted/40 flex items-center justify-between gap-4 px-4 py-3 transition-colors duration-150"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium">
                      <span className="text-primary">{formatOrderNumber(order.order_number)}</span>{' '}
                      · {order.currency} {order.total}
                    </p>
                    <p className="text-muted-foreground text-xs">
                      {order.customer_name ?? formatPhoneNumber(order.customer_whatsapp_number)} ·{' '}
                      {new Date(order.placed_at).toLocaleString()}
                    </p>
                  </div>
                  {order.fulfillment_status ? (
                    <StatusBadge status={order.fulfillment_status} />
                  ) : (
                    <span className="text-muted-foreground shrink-0 text-xs">Awaiting payment</span>
                  )}
                </Link>
              ))}
            </div>
          )}
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
