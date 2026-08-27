import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { AppointmentOut } from '@/shared/api/types'
import { toast } from '@/shared/lib/toastStore'

interface UpdateAppointmentDetailsInput {
  appointmentId: string
  notes?: string | null
}

export function useUpdateAppointmentDetails() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ appointmentId, notes }: UpdateAppointmentDetailsInput) =>
      apiFetch<AppointmentOut>(`/api/v1/appointments/${appointmentId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          ...(notes !== undefined ? { notes } : {}),
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      toast('Note saved.')
    },
    onError: () => {
      toast.error('Could not save note. Please try again.')
    },
  })
}
