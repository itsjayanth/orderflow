import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { PaymentSettingsOut } from '@/shared/api/types'

const QUERY_KEY = ['settings', 'payments']

export function usePaymentSettings() {
  return useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => apiFetch<PaymentSettingsOut>('/api/v1/payments/settings'),
  })
}

interface UpdatePaymentSettingsInput {
  razorpay_key_id: string
  razorpay_key_secret: string
}

export function useUpdatePaymentSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: UpdatePaymentSettingsInput) =>
      apiFetch<PaymentSettingsOut>('/api/v1/payments/settings', {
        method: 'PUT',
        body: JSON.stringify(input),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEY }),
  })
}
