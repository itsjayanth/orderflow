import { useMutation, useQueryClient } from '@tanstack/react-query'

import { ApiError, apiFetch } from '@/shared/api/client'
import type { AppointmentOut } from '@/shared/api/types'
import { toast } from '@/shared/lib/toastStore'

interface RescheduleAppointmentInput {
  appointmentId: string
  appointmentDate: string // "YYYY-MM-DD"
  startTime: string // "HH:MM:SS"
}

// Backend returns 409 {"detail": "slot_no_longer_available"} when the
// overlap check (appointments/adapters/repository.py's
// _assert_no_overlap) rejects the new time -- surfaced here so the
// calendar drag-and-drop handler can tell "conflict, revert the drag" apart
// from any other failure.
export function isSlotConflictError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 409
}

export function useRescheduleAppointment() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ appointmentId, appointmentDate, startTime }: RescheduleAppointmentInput) =>
      apiFetch<AppointmentOut>(`/api/v1/appointments/${appointmentId}/reschedule`, {
        method: 'PATCH',
        body: JSON.stringify({ appointment_date: appointmentDate, start_time: startTime }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      toast('Appointment rescheduled.')
    },
    onError: (error) => {
      toast.error(
        isSlotConflictError(error)
          ? 'That time is no longer available. Pick another slot.'
          : 'Could not reschedule. Please try again.',
      )
    },
  })
}
