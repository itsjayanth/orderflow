import { useState } from 'react'
import { Link } from 'react-router-dom'

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { FulfillmentStatus } from '@/shared/api/types'

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
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">Orders</h1>
        <p className="text-muted-foreground text-sm">
          Updates automatically as new orders come in.
        </p>
      </div>

      <div className="flex gap-2">
        {FILTERS.map((status) => (
          <button
            key={status}
            type="button"
            onClick={() => setFilter(status)}
            className={`rounded-md border px-3 py-1 text-sm ${
              filter === status
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            {status === 'all' ? 'All' : STATUS_LABELS[status]}
          </button>
        ))}
      </div>

      <div className="rounded-md border">
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
                  <Link to={`/orders/${order.order_id}`} className="hover:underline">
                    {formatDateTime(order.placed_at)}
                  </Link>
                </TableCell>
                <TableCell>{order.items.length}</TableCell>
                <TableCell>
                  {order.currency} {order.total}
                </TableCell>
                <TableCell>{order.payment_status}</TableCell>
                <TableCell>
                  {order.fulfillment_status ? STATUS_LABELS[order.fulfillment_status] : '—'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
