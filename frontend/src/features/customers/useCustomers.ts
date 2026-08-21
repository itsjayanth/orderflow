import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { CustomerOut } from '@/shared/api/types'

export const customersQueryKey = ['customers'] as const

export function useCustomers(includeInactive = false) {
  return useQuery({
    queryKey: [...customersQueryKey, { includeInactive }] as const,
    queryFn: () =>
      apiFetch<CustomerOut[]>(
        `/api/v1/customers${includeInactive ? '?include_inactive=true' : ''}`,
      ),
  })
}
