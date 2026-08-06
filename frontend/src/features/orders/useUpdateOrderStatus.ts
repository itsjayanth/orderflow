import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { FulfillmentStatus, OrderOut } from '@/shared/api/types'

interface UpdateOrderStatusInput {
  orderId: string
  toStatus: FulfillmentStatus
}

export function useUpdateOrderStatus() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ orderId, toStatus }: UpdateOrderStatusInput) =>
      apiFetch<OrderOut>(`/api/v1/orders/${orderId}/fulfillment-status`, {
        method: 'PATCH',
        body: JSON.stringify({ to_status: toStatus }),
      }),
    onMutate: async ({ orderId, toStatus }) => {
      await queryClient.cancelQueries({ queryKey: ['orders'] })

      const previousQueries = queryClient.getQueriesData<OrderOut[] | OrderOut>({
        queryKey: ['orders'],
      })

      queryClient.setQueriesData<OrderOut[] | OrderOut>({ queryKey: ['orders'] }, (old) => {
        if (!old) return old
        if (Array.isArray(old)) {
          return old.map((order) =>
            order.order_id === orderId ? { ...order, fulfillment_status: toStatus } : order,
          )
        }
        return old.order_id === orderId ? { ...old, fulfillment_status: toStatus } : old
      })

      return { previousQueries }
    },
    onError: (_err, _vars, context) => {
      if (!context) return
      for (const [queryKey, data] of context.previousQueries) {
        queryClient.setQueryData(queryKey, data)
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] })
    },
  })
}
