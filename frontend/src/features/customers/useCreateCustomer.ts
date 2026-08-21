import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { CustomerOut } from '@/shared/api/types'
import { toast } from '@/shared/lib/toastStore'

import { customersQueryKey } from './useCustomers'

interface CreateCustomerInput {
  whatsapp_number: string
  display_name?: string
  default_contact_phone?: string
  email?: string
}

export function useCreateCustomer() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateCustomerInput) =>
      apiFetch<CustomerOut>('/api/v1/customers', {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: customersQueryKey })
      toast('Customer added.')
    },
  })
}
