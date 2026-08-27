import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { AppointmentOut, AppointmentStatus } from '@/shared/api/types'
import type { DateRangeValue } from '@/shared/components/DateRangeFilter'

// Short-interval polling, not a page reload -- same "visible within
// seconds" pattern as orders/useOrders.ts, without websocket
// infrastructure.
const APPOINTMENTS_REFETCH_INTERVAL_MS = 5_000

export type UseAppointmentsParams = DateRangeValue & {
  status?: AppointmentStatus
  customerId?: string
}

export function useAppointments(params: UseAppointmentsParams = {}) {
  const { status, from_date, to_date, customerId } = params
  const search = new URLSearchParams()
  if (status) search.set('status', status)
  if (from_date) search.set('from_date', from_date)
  if (to_date) search.set('to_date', to_date)
  if (customerId) search.set('customer_id', customerId)
  const query = search.toString()

  return useQuery({
    queryKey: ['appointments', { status, from_date, to_date, customerId }],
    queryFn: () => apiFetch<AppointmentOut[]>(`/api/v1/appointments${query ? `?${query}` : ''}`),
    refetchInterval: APPOINTMENTS_REFETCH_INTERVAL_MS,
    enabled: customerId === undefined || customerId.length > 0,
  })
}
