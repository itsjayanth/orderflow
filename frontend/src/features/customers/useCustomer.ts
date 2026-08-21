import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { CustomerWithAddressesOut } from '@/shared/api/types'

// Single-customer detail fetch (adds `addresses`, which the list endpoint
// doesn't include) -- lazy, only queried once a Customers row is expanded.
// Query key shares the 'customers' prefix with useCustomers/useCreate/
// useUpdateCustomer's invalidation, so edits refresh this automatically.
export function useCustomer(customerId: string) {
  return useQuery({
    queryKey: ['customers', customerId],
    queryFn: () => apiFetch<CustomerWithAddressesOut>(`/api/v1/customers/${customerId}`),
    enabled: !!customerId,
  })
}
