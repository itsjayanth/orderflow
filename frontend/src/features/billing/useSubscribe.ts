import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { SubscriptionCheckoutOut } from '@/shared/api/types'

const QUERY_KEY = ['billing', 'subscription']

interface SubscribeInput {
  plan_id: string
}

export function useSubscribe() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: SubscribeInput) =>
      apiFetch<SubscriptionCheckoutOut>('/api/v1/billing/subscribe', {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEY }),
  })
}
