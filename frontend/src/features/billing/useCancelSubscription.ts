import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { SubscriptionOut } from '@/shared/api/types'

const QUERY_KEY = ['billing', 'subscription']

export function useCancelSubscription() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch<SubscriptionOut>('/api/v1/billing/cancel', { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEY }),
  })
}
