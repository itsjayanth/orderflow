import { TrendingUp } from 'lucide-react'
import { useMemo } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  type TooltipContentProps,
  XAxis,
  YAxis,
} from 'recharts'

import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { OrderOut } from '@/shared/api/types'
import { EmptyState } from '@/shared/components/EmptyState'
import { formatCompactCurrency, formatCurrency } from '@/shared/lib/currency'

interface DailyPoint {
  dateKey: string
  label: string
  orderCount: number
  /** Sum of `order.total` for orders whose fulfillment_status isn't
   * "cancelled" -- deliberately mirrors the backend's own
   * `revenue_generated` definition (backend/src/orders/adapters/
   * repository.py's `get_summary`) so this chart's totals, summed across
   * the visible range, land on the exact same number as the hero card
   * just above it rather than a plausible-looking but different figure. */
  revenue: number
}

function localDateKey(iso: string): string {
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function buildDailySeries(orders: OrderOut[]): DailyPoint[] {
  const buckets = new Map<string, { date: Date; orderCount: number; revenue: number }>()
  for (const order of orders) {
    const key = localDateKey(order.placed_at)
    const revenueContribution = order.fulfillment_status !== 'cancelled' ? Number(order.total) : 0
    const existing = buckets.get(key)
    if (existing) {
      existing.orderCount += 1
      existing.revenue += revenueContribution
    } else {
      buckets.set(key, {
        date: new Date(order.placed_at),
        orderCount: 1,
        revenue: revenueContribution,
      })
    }
  }
  return [...buckets.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([dateKey, value]) => ({
      dateKey,
      label: value.date.toLocaleDateString('en-IN', { month: 'short', day: 'numeric' }),
      orderCount: value.orderCount,
      revenue: value.revenue,
    }))
}

function ChartTooltip({ active, payload }: TooltipContentProps) {
  if (!active || !payload?.length) return null
  const point = payload[0]?.payload as DailyPoint | undefined
  if (!point) return null
  return (
    <div className="bg-popover text-popover-foreground border-border rounded-lg border px-3 py-2 text-xs shadow-md">
      <p className="font-medium">{point.label}</p>
      <p className="text-muted-foreground mt-1">{formatCurrency(point.revenue)}</p>
      <p className="text-muted-foreground">
        {point.orderCount} order{point.orderCount === 1 ? '' : 's'}
      </p>
    </div>
  )
}

/** Client-derived daily trend -- there's no backend time-series endpoint,
 * so this buckets the already-fetched `orders` array (same data
 * `recentOrders` is sliced from on the dashboard) by local calendar day. */
export function DashboardTrendChart({
  orders,
  isLoading,
}: {
  orders: OrderOut[] | undefined
  isLoading: boolean
}) {
  const series = useMemo(() => buildDailySeries(orders ?? []), [orders])
  const hasEnoughData = series.length >= 2

  return (
    <Card className="p-6">
      <div className="mb-4">
        <h2 className="text-lg font-medium">Revenue trend</h2>
        <p className="text-muted-foreground text-sm">
          Daily revenue for the selected range -- adds up to the total above.
        </p>
      </div>

      {isLoading && <Skeleton className="h-48 w-full" />}

      {!isLoading && !hasEnoughData && (
        <EmptyState
          icon={TrendingUp}
          title="Not enough data yet"
          description="Once orders span a few different days, a trend line will show up here."
          className="border-none py-8"
        />
      )}

      {!isLoading && hasEnoughData && (
        <div className="h-48 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={series} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
              <defs>
                <linearGradient id="dashboardRevenueFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="var(--chart-1)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }}
                tickLine={false}
                axisLine={false}
                width={56}
                tickFormatter={(value: number) => formatCompactCurrency(value)}
              />
              <Tooltip content={ChartTooltip} />
              <Area
                type="monotone"
                dataKey="revenue"
                stroke="var(--chart-1)"
                strokeWidth={2}
                fill="url(#dashboardRevenueFill)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  )
}
