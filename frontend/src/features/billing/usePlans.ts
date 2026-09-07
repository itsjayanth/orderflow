import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { PlanOut } from '@/shared/api/types'

const QUERY_KEY = ['billing', 'plans']

// Public endpoint -- no auth required, safe to call from a logged-out
// marketing page (PricingPage.tsx). apiFetch attaches the auth header
// automatically when a session exists, but the backend doesn't need it here.
export function usePlans() {
  return useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => apiFetch<PlanOut[]>('/api/v1/billing/plans'),
  })
}
