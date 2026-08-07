import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { apiFetch } from '@/shared/api/client'
import type { CustomerWithAddressesOut, FulfillmentStatus } from '@/shared/api/types'
import { formatOrderNumber } from '@/shared/lib/orderNumber'
import { formatPhoneNumber } from '@/shared/lib/phoneNumber'

import { legalNextStatuses, STATUS_LABELS } from './statusTransitions'
import { useOrder } from './useOrder'
import { useUpdateOrderStatus } from './useUpdateOrderStatus'

export function OrderDetailPage() {
  const { orderId } = useParams<{ orderId: string }>()
  const { data: order, isLoading } = useOrder(orderId ?? '')
  const updateStatus = useUpdateOrderStatus()

  const customer = useQuery({
    queryKey: ['customers', order?.customer_id],
    queryFn: () => apiFetch<CustomerWithAddressesOut>(`/api/v1/customers/${order?.customer_id}`),
    enabled: !!order,
  })

  if (isLoading) {
    return <p className="text-muted-foreground text-sm">Loading…</p>
  }

  if (!order) {
    return <p className="text-muted-foreground text-sm">Order not found.</p>
  }

  const nextStatuses = order.fulfillment_status ? legalNextStatuses(order.fulfillment_status) : []

  return (
    <div className="space-y-6">
      <div>
        <Link to="/orders" className="text-muted-foreground text-sm hover:underline">
          ← Back to orders
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">
          Order {formatOrderNumber(order.order_number)}
        </h1>
        <p className="text-muted-foreground text-sm">
          {customer.data
            ? (customer.data.display_name ?? formatPhoneNumber(customer.data.whatsapp_number))
            : '—'}{' '}
          · {new Date(order.placed_at).toLocaleString()}
        </p>
      </div>

      <Card className="flex flex-wrap items-center gap-3 p-4">
        <span className="text-sm font-medium">
          Status: {order.fulfillment_status ? STATUS_LABELS[order.fulfillment_status] : '—'}
        </span>
        {nextStatuses.map((status) => (
          <Button
            key={status}
            size="sm"
            variant={status === 'cancelled' ? 'outline' : 'default'}
            disabled={updateStatus.isPending}
            onClick={() =>
              updateStatus.mutate({
                orderId: order.order_id,
                toStatus: status as FulfillmentStatus,
              })
            }
          >
            Mark {STATUS_LABELS[status]}
          </Button>
        ))}
      </Card>

      {updateStatus.isError && (
        <p className="text-destructive text-sm">Failed to update status. Please try again.</p>
      )}

      <Card className="overflow-hidden py-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Item</TableHead>
              <TableHead>Quantity</TableHead>
              <TableHead>Price</TableHead>
              <TableHead>Line total</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {order.items.map((item) => (
              <TableRow key={item.order_item_id}>
                <TableCell className="font-medium">{item.name_snapshot}</TableCell>
                <TableCell>{item.quantity}</TableCell>
                <TableCell>{item.price_snapshot}</TableCell>
                <TableCell>{item.line_total}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      <p className="text-right text-lg font-semibold">
        Total: {order.currency} {order.total}
      </p>
    </div>
  )
}
