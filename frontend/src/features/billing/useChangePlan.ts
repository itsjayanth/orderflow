import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { SubscriptionOut } from '@/shared/api/types'

const QUERY_KEY = ['billing', 'subscription']

interface ChangePlanInput {
  plan_id: string
}

export function useChangePlan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: ChangePlanInput) =>
      apiFetch<SubscriptionOut>('/api/v1/billing/change-plan', {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEY }),
  })
}
