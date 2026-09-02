import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { AppointmentFlowServiceOut } from '@/shared/api/types'

export function useAppointmentServices(merchantId: string) {
  return useQuery({
    queryKey: ['appointment-flow', merchantId, 'services'],
    queryFn: () =>
      apiFetch<AppointmentFlowServiceOut[]>(`/api/v1/appointment-flow/${merchantId}/services`),
    enabled: !!merchantId,
    retry: false,
  })
}
