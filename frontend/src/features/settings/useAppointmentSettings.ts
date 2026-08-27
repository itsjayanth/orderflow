import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { AppointmentSettingsOut } from '@/shared/api/types'

const QUERY_KEY = ['appointment-settings']

export function useAppointmentSettings() {
  return useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => apiFetch<AppointmentSettingsOut>('/api/v1/auth/appointment-settings'),
  })
}

export function useUpdateAppointmentSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (enabled: boolean) =>
      apiFetch<AppointmentSettingsOut>('/api/v1/auth/appointment-settings', {
        method: 'PATCH',
        body: JSON.stringify({ enabled }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEY }),
  })
}
