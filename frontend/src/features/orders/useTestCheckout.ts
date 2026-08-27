import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { TestCheckoutResponse } from '@/shared/api/types'

interface TestCheckoutInput {
  customer_whatsapp_number: string
  customer_display_name?: string
  items: { item_id: string; quantity: number }[]
  payment_method: 'online' | 'cod'
}

export function useTestCheckout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: TestCheckoutInput) =>
      apiFetch<TestCheckoutResponse>('/api/v1/payments/test-checkout', {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['orders'] }),
  })
}
