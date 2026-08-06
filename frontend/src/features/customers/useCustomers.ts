import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { CustomerOut } from '@/shared/api/types'

export function useCustomers() {
  return useQuery({
    queryKey: ['customers'],
    queryFn: () => apiFetch<CustomerOut[]>('/api/v1/customers'),
  })
}
