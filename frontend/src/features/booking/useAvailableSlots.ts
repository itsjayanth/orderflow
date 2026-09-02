import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { AppointmentFlowSlotOut } from '@/shared/api/types'

// service_id omitted (not just empty-string) when no service is selected --
// the backend falls back to the day's default slot_duration_minutes in that
// case rather than a specific service's duration (appointment_flow.domain.
// availability.get_available_slots / resolve_duration_minutes).
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
  })
}
