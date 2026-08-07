import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { Card } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { cn } from '@/lib/utils'
import type { FulfillmentStatus, OrderOut } from '@/shared/api/types'
import { StatusBadge } from '@/shared/components/StatusBadge'
import { formatOrderNumber } from '@/shared/lib/orderNumber'
import { formatPhoneNumber } from '@/shared/lib/phoneNumber'

import { CreateTestOrderForm } from './CreateTestOrderForm'
import { STATUS_LABELS } from './statusTransitions'
import { useOrders } from './useOrders'

// The full lifecycle, including "cancelled" -- a restaurant owner monitoring
// failed/undelivered orders needs it as a first-class tab too, and it's
// what the dashboard's "Failed" card links to.
const TABS: (FulfillmentStatus | 'all')[] = [
  'all',
  'new',
  'preparing',
  'ready',
  'completed',
  'cancelled',
]

function isFulfillmentStatus(value: string | null): value is FulfillmentStatus {
  return (
    value === 'new' ||
    value === 'preparing' ||
    value === 'ready' ||
    value === 'completed' ||
    value === 'cancelled'
  )
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString()
}

function countByStatus(orders: OrderOut[] | undefined): Record<FulfillmentStatus | 'all', number> {
  const counts: Record<FulfillmentStatus | 'all', number> = {
    all: orders?.length ?? 0,
    new: 0,
    preparing: 0,
    ready: 0,
    completed: 0,
    cancelled: 0,
  }
  for (const order of orders ?? []) {
    if (order.fulfillment_status) counts[order.fulfillment_status] += 1
  }
  return counts
}

export function OrdersPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const statusParam = searchParams.get('status')
  const [tab, setTab] = useState<FulfillmentStatus | 'all'>(
    isFulfillmentStatus(statusParam) ? statusParam : 'all',
  )
  const { data: orders, isLoading } = useOrders()

  function selectTab(next: FulfillmentStatus | 'all') {
    setTab(next)
    setSearchParams(next === 'all' ? {} : { status: next })
  }

  const counts = useMemo(() => countByStatus(orders), [orders])
  const visibleOrders = useMemo(
    () => (tab === 'all' ? orders : orders?.filter((order) => order.fulfillment_status === tab)),
    [orders, tab],
  )

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Orders</h1>
        <p className="text-muted-foreground text-sm">
          Updates automatically as new orders come in.
        </p>
      </div>

      <CreateTestOrderForm />

      <div className="border-border flex flex-wrap gap-1 border-b">
        {TABS.map((status) => (
          <button
            key={status}
            type="button"
            onClick={() => selectTab(status)}
            className={cn(
              'flex items-center gap-2 border-b-2 px-3.5 py-2.5 text-sm font-medium transition-all duration-150',
              tab === status
                ? 'border-primary text-foreground'
                : 'text-muted-foreground hover:text-foreground border-transparent',
            )}
          >
            {status === 'all' ? 'All' : STATUS_LABELS[status]}
            <span
              className={cn(
                'rounded-full px-1.5 py-0.5 text-xs font-semibold',
                tab === status ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground',
              )}
            >
              {counts[status]}
            </span>
          </button>
        ))}
      </div>

      <Card className="overflow-hidden py-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Order</TableHead>
              <TableHead>Customer</TableHead>
              <TableHead>Placed</TableHead>
              <TableHead>Items</TableHead>
              <TableHead>Total</TableHead>
              <TableHead>Payment</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && (
              <TableRow>
                <TableCell colSpan={7} className="text-muted-foreground">
                  Loading…
                </TableCell>
              </TableRow>
            )}
            {!isLoading && visibleOrders?.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="text-muted-foreground">
                  {tab === 'all'
                    ? 'No orders yet.'
                    : `No ${STATUS_LABELS[tab].toLowerCase()} orders.`}
                </TableCell>
              </TableRow>
            )}
            {visibleOrders?.map((order) => (
              <TableRow key={order.order_id}>
                <TableCell>
                  <Link
                    to={`/orders/${order.order_id}`}
                    className="text-primary font-medium hover:underline"
                  >
                    {formatOrderNumber(order.order_number)}
                  </Link>
                </TableCell>
                <TableCell>
                  <p className="font-medium">
                    {order.customer_name ?? formatPhoneNumber(order.customer_whatsapp_number)}
                  </p>
                  {order.customer_name && (
                    <p className="text-muted-foreground text-xs">
                      {formatPhoneNumber(order.customer_whatsapp_number)}
                    </p>
                  )}
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {formatDateTime(order.placed_at)}
                </TableCell>
                <TableCell>{order.items.length}</TableCell>
                <TableCell className="font-medium">
                  {order.currency} {order.total}
                </TableCell>
                <TableCell className="text-muted-foreground">{order.payment_status}</TableCell>
                <TableCell>
                  {order.fulfillment_status ? (
                    <StatusBadge status={order.fulfillment_status} />
                  ) : (
                    '—'
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </div>
  )
}
