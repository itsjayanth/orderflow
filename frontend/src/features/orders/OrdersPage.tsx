import { useState } from 'react'
import { Link } from 'react-router-dom'

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
import type { FulfillmentStatus } from '@/shared/api/types'
import { StatusBadge } from '@/shared/components/StatusBadge'

import { CreateTestOrderForm } from './CreateTestOrderForm'
import { STATUS_LABELS } from './statusTransitions'
import { useOrders } from './useOrders'

const FILTERS: (FulfillmentStatus | 'all')[] = ['all', 'new', 'preparing', 'ready', 'completed']

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString()
}

export function OrdersPage() {
  const [filter, setFilter] = useState<FulfillmentStatus | 'all'>('all')
  const { data: orders, isLoading } = useOrders(filter === 'all' ? undefined : filter)

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Orders</h1>
        <p className="text-muted-foreground text-sm">
          Updates automatically as new orders come in.
        </p>
      </div>

      <CreateTestOrderForm />

      <div className="flex flex-wrap gap-2">
        {FILTERS.map((status) => (
          <button
            key={status}
            type="button"
            onClick={() => setFilter(status)}
            className={cn(
              'rounded-full border px-3.5 py-1.5 text-sm font-medium transition-all duration-150',
              filter === status
                ? 'bg-primary text-primary-foreground border-primary shadow-sm'
                : 'text-muted-foreground hover:text-foreground hover:bg-accent border-border',
            )}
          >
            {status === 'all' ? 'All' : STATUS_LABELS[status]}
          </button>
        ))}
      </div>

      <Card className="overflow-hidden py-0">
        <Table>
          <TableHeader>
            <TableRow>
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
                <TableCell colSpan={5} className="text-muted-foreground">
                  Loading…
                </TableCell>
              </TableRow>
            )}
            {!isLoading && orders?.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="text-muted-foreground">
                  No orders yet.
                </TableCell>
              </TableRow>
            )}
            {orders?.map((order) => (
              <TableRow key={order.order_id}>
                <TableCell>
                  <Link
                    to={`/orders/${order.order_id}`}
                    className="text-primary font-medium hover:underline"
                  >
                    {formatDateTime(order.placed_at)}
                  </Link>
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
