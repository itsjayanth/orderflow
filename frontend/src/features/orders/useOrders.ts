import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { FulfillmentStatus, OrderOut } from '@/shared/api/types'
import type { DateRangeValue } from '@/shared/components/DateRangeFilter'

// Short-interval polling, not a page reload -- the concrete implementation
// of TECH_STACK.md's "order visible within seconds" cache-and-revalidate
// pattern, without websocket infrastructure.
const ORDERS_REFETCH_INTERVAL_MS = 5_000

export type UseOrdersParams = DateRangeValue & {
  fulfillmentStatus?: FulfillmentStatus
  customerId?: string
}

export function useOrders(params: UseOrdersParams = {}) {
  const { fulfillmentStatus, from_date, to_date, customerId } = params
  const search = new URLSearchParams()
  if (fulfillmentStatus) search.set('fulfillment_status', fulfillmentStatus)
  if (from_date) search.set('from_date', from_date)
  if (to_date) search.set('to_date', to_date)
  if (customerId) search.set('customer_id', customerId)
  const query = search.toString()

  return useQuery({
    queryKey: ['orders', { fulfillmentStatus, from_date, to_date, customerId }],
    queryFn: () => apiFetch<OrderOut[]>(`/api/v1/orders${query ? `?${query}` : ''}`),
    refetchInterval: ORDERS_REFETCH_INTERVAL_MS,
    enabled: customerId === undefined || customerId.length > 0,
  })
}
