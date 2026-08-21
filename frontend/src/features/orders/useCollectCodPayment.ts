import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { OrderOut } from '@/shared/api/types'
import { toast } from '@/shared/lib/toastStore'

export function useCollectCodPayment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (orderId: string) =>
      apiFetch<OrderOut>(`/api/v1/orders/${orderId}/collect-cod-payment`, {
        method: 'POST',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] })
      toast('Payment marked as collected.')
    },
    onError: () => {
      toast.error('Could not mark payment collected. Please try again.')
    },
  })
}
