import { ChevronLeft } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { Card } from '@/components/ui/card'
import { formatOrderNumber } from '@/shared/lib/orderNumber'

import { OrderDetailCard } from './OrderDetailCard'
import { useOrder } from './useOrder'

export function OrderDetailPage() {
  const { orderId } = useParams<{ orderId: string }>()
  const { data: order, isLoading } = useOrder(orderId ?? '')

  if (isLoading) {
    return <p className="text-muted-foreground text-sm">Loading…</p>
  }

  if (!order) {
    return <p className="text-muted-foreground text-sm">Order not found.</p>
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          to="/orders"
          className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-sm transition-colors duration-150"
        >
          <ChevronLeft className="size-4" />
          Back to orders
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">
          Order {formatOrderNumber(order.order_number)}
        </h1>
      </div>

      <Card className="p-5">
        <OrderDetailCard order={order} />
      </Card>
    </div>
  )
}
