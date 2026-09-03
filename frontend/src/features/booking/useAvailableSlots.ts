import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { AppointmentFlowSlotOut } from '@/shared/api/types'

// service_id omitted (not just empty-string) when no service is selected --
// the backend falls back to the day's default slot_duration_minutes in that
// case rather than a specific service's duration (appointment_flow.domain.
// availability.get_available_slots / resolve_duration_minutes).
//
// Short-interval polling, same cache-and-revalidate convention
// frontend/src/features/orders/useOrders.ts uses -- a customer can sit on
// the "choose a time" step for a while, and this is what makes an
// elapsed slot (Task 1) or a merchant's just-changed hours (Task 3)
// disappear from the list without the customer needing to refresh the
// page themselves. The backend re-validates on submit regardless (see
// appointment_flow.domain.booking.perform_booking), so this polling is a
// UX nicety, not the safety mechanism.
const AVAILABLE_SLOTS_REFETCH_INTERVAL_MS = 30_000

export function useAvailableSlots(merchantId: string, date: string, serviceId?: string) {
  const params = new URLSearchParams({ date })
  if (serviceId) params.set('service_id', serviceId)

  return useQuery({
    queryKey: ['appointment-flow', merchantId, 'availability', date, serviceId ?? null],
    queryFn: () =>
      apiFetch<AppointmentFlowSlotOut[]>(
        `/api/v1/appointment-flow/${merchantId}/availability?${params.toString()}`,
      ),
    enabled: !!merchantId && !!date,
    retry: false,
    refetchInterval: AVAILABLE_SLOTS_REFETCH_INTERVAL_MS,
  })
}
