import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { AppointmentAvailabilitySettingsOut } from '@/shared/api/types'

const QUERY_KEY = ['appointment-availability-settings']

export function useAppointmentAvailability() {
  return useQuery({
    queryKey: QUERY_KEY,
    queryFn: () =>
      apiFetch<AppointmentAvailabilitySettingsOut>('/api/v1/auth/appointment-availability'),
  })
}

export function useUpdateAppointmentAvailability() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: AppointmentAvailabilitySettingsOut) =>
      apiFetch<AppointmentAvailabilitySettingsOut>('/api/v1/auth/appointment-availability', {
        method: 'PUT',
        body: JSON.stringify(body),
      }),
    onSuccess: (data) => queryClient.setQueryData(QUERY_KEY, data),
  })
}
