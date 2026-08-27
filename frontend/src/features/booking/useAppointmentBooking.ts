import { useMutation } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { AppointmentFlowBookingResponse } from '@/shared/api/types'

interface AppointmentBookingInput {
  customer_whatsapp_number: string
  customer_display_name?: string
  name: string
  email: string
  appointment_date: string
  appointment_time: string
  notes?: string
}

export function useAppointmentBooking(merchantId: string) {
  return useMutation({
    mutationFn: (input: AppointmentBookingInput) =>
      apiFetch<AppointmentFlowBookingResponse>(`/api/v1/appointment-flow/${merchantId}/book`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
  })
}
