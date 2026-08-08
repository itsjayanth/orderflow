import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { OrderSummaryOut } from '@/shared/api/types'
import type { DateRangeValue } from '@/shared/components/DateRangeFilter'

const SUMMARY_REFETCH_INTERVAL_MS = 5_000

export function useOrderSummary(range: DateRangeValue = {}) {
  const { from_date, to_date } = range
  const search = new URLSearchParams()
  if (from_date) search.set('from_date', from_date)
  if (to_date) search.set('to_date', to_date)
  const query = search.toString()

  return useQuery({
    queryKey: ['orders', 'summary', { from_date, to_date }],
    queryFn: () => apiFetch<OrderSummaryOut>(`/api/v1/orders/summary${query ? `?${query}` : ''}`),
    refetchInterval: SUMMARY_REFETCH_INTERVAL_MS,
  })
}
