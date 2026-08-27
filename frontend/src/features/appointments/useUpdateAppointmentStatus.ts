import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { AppointmentOut, AppointmentStatus } from '@/shared/api/types'
import { toast } from '@/shared/lib/toastStore'

import { STATUS_LABELS } from './statusTransitions'

interface UpdateAppointmentStatusInput {
  appointmentId: string
  toStatus: AppointmentStatus
}

export function useUpdateAppointmentStatus() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ appointmentId, toStatus }: UpdateAppointmentStatusInput) =>
      apiFetch<AppointmentOut>(`/api/v1/appointments/${appointmentId}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ to_status: toStatus }),
      }),
    onMutate: async ({ appointmentId, toStatus }) => {
      await queryClient.cancelQueries({ queryKey: ['appointments'] })

      const previousQueries = queryClient.getQueriesData<AppointmentOut[] | AppointmentOut>({
        queryKey: ['appointments'],
      })

      queryClient.setQueriesData<AppointmentOut[] | AppointmentOut>(
        { queryKey: ['appointments'] },
        (old) => {
          if (!old) return old
          if (Array.isArray(old)) {
            return old.map((appointment) =>
              appointment.appointment_id === appointmentId
                ? { ...appointment, status: toStatus }
                : appointment,
            )
          }
          return old.appointment_id === appointmentId ? { ...old, status: toStatus } : old
        },
      )

      return { previousQueries }
    },
    onError: (_err, _vars, context) => {
      if (!context) return
      for (const [queryKey, data] of context.previousQueries) {
        queryClient.setQueryData(queryKey, data)
      }
      toast.error('Could not update appointment status. Please try again.')
    },
    onSuccess: (_data, { toStatus }) => {
      toast(`Appointment marked ${STATUS_LABELS[toStatus]}.`)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
    },
  })
}
