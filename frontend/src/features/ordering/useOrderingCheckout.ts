import { useMutation } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { OrderingFlowCheckoutResponse } from '@/shared/api/types'

interface OrderingCheckoutInput {
  customer_whatsapp_number: string
  customer_display_name?: string
  items: { menu_item_id: string; quantity: number }[]
  payment_method: 'online' | 'cod'
}

export function useOrderingCheckout(merchantId: string) {
  return useMutation({
    mutationFn: (input: OrderingCheckoutInput) =>
      apiFetch<OrderingFlowCheckoutResponse>(`/api/v1/ordering-flow/${merchantId}/checkout`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
  })
}
