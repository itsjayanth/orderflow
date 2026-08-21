import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { OrderDetailOut } from '@/shared/api/types'

export function useOrder(orderId: string) {
  return useQuery({
    queryKey: ['orders', orderId],
    queryFn: () => apiFetch<OrderDetailOut>(`/api/v1/orders/${orderId}`),
    enabled: !!orderId,
  })
}
