import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { FulfillmentStatus, OrderOut } from '@/shared/api/types'

// Short-interval polling, not a page reload -- the concrete implementation
// of TECH_STACK.md's "order visible within seconds" cache-and-revalidate
// pattern, without websocket infrastructure.
const ORDERS_REFETCH_INTERVAL_MS = 5_000

export function useOrders(fulfillmentStatus?: FulfillmentStatus) {
  return useQuery({
    queryKey: ['orders', { fulfillmentStatus }],
    queryFn: () =>
      apiFetch<OrderOut[]>(
        `/api/v1/orders${fulfillmentStatus ? `?fulfillment_status=${fulfillmentStatus}` : ''}`,
      ),
    refetchInterval: ORDERS_REFETCH_INTERVAL_MS,
  })
}
