import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { AppointmentServiceSettingsOut } from '@/shared/api/types'

const QUERY_KEY = ['appointment-services']

export function useAppointmentServices() {
  return useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => apiFetch<AppointmentServiceSettingsOut[]>('/api/v1/auth/appointment-services'),
  })
}

interface CreateAppointmentServiceInput {
  name: string
  duration_minutes: number
  price?: string | null
}

export function useCreateAppointmentService() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: CreateAppointmentServiceInput) =>
      apiFetch<AppointmentServiceSettingsOut>('/api/v1/auth/appointment-services', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEY }),
  })
}

interface UpdateAppointmentServiceInput {
  serviceId: string
  name?: string
  duration_minutes?: number
  price?: string | null
  is_active?: boolean
}

export function useUpdateAppointmentService() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ serviceId, ...body }: UpdateAppointmentServiceInput) =>
      apiFetch<AppointmentServiceSettingsOut>(`/api/v1/auth/appointment-services/${serviceId}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEY }),
  })
}

export function useDeleteAppointmentService() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (serviceId: string) =>
      apiFetch<void>(`/api/v1/auth/appointment-services/${serviceId}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEY }),
  })
}
