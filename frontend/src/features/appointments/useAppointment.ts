import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { AppointmentOut } from '@/shared/api/types'

export function useAppointment(appointmentId: string) {
  return useQuery({
    queryKey: ['appointments', appointmentId],
    queryFn: () => apiFetch<AppointmentOut>(`/api/v1/appointments/${appointmentId}`),
    enabled: !!appointmentId,
  })
}
