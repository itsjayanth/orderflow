import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { OrderSummaryOut } from '@/shared/api/types'

const SUMMARY_REFETCH_INTERVAL_MS = 5_000

export function useOrderSummary() {
  return useQuery({
    queryKey: ['orders', 'summary'],
    queryFn: () => apiFetch<OrderSummaryOut>('/api/v1/orders/summary'),
    refetchInterval: SUMMARY_REFETCH_INTERVAL_MS,
  })
}
