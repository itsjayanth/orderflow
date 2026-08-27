import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { AppointmentFlowInfoOut } from '@/shared/api/types'

export function useBookingInfo(merchantId: string) {
  return useQuery({
    queryKey: ['appointment-flow', merchantId, 'info'],
    queryFn: () => apiFetch<AppointmentFlowInfoOut>(`/api/v1/appointment-flow/${merchantId}/info`),
    enabled: !!merchantId,
    retry: false,
  })
}
