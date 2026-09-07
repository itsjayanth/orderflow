import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { SubscriptionOut } from '@/shared/api/types'

const QUERY_KEY = ['billing', 'subscription']

export function useSubscription() {
  return useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => apiFetch<SubscriptionOut>('/api/v1/billing/subscription'),
  })
}
