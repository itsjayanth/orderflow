import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { CustomerOut } from '@/shared/api/types'
import { toast } from '@/shared/lib/toastStore'

import { customersQueryKey } from './useCustomers'

interface UpdateCustomerInput {
  customer_id: string
  display_name?: string
  default_contact_phone?: string
  email?: string
  is_active?: boolean
}

export function useUpdateCustomer() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ customer_id, ...body }: UpdateCustomerInput) =>
      apiFetch<CustomerOut>(`/api/v1/customers/${customer_id}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: customersQueryKey })
      if (variables.is_active === false) toast('Customer removed.')
      else if (variables.is_active === true) toast('Customer restored.')
      else toast('Customer updated.')
    },
    onError: () => {
      toast.error('Could not save changes. Please try again.')
    },
  })
}
