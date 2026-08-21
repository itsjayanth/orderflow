import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { OrderOut } from '@/shared/api/types'
import { toast } from '@/shared/lib/toastStore'

interface UpdateOrderDetailsInput {
  orderId: string
  contactPhone?: string
  notes?: string
}

export function useUpdateOrderDetails() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ orderId, contactPhone, notes }: UpdateOrderDetailsInput) =>
      apiFetch<OrderOut>(`/api/v1/orders/${orderId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          ...(contactPhone !== undefined ? { contact_phone: contactPhone } : {}),
          ...(notes !== undefined ? { notes } : {}),
        }),
      }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['orders'] })
      toast(variables.notes !== undefined ? 'Note saved.' : 'Contact number saved.')
    },
    onError: (_err, variables) => {
      toast.error(
        variables.notes !== undefined
          ? 'Could not save note. Please try again.'
          : 'Could not save contact number. Please try again.',
      )
    },
  })
}
