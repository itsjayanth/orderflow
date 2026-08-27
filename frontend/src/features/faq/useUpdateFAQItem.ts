import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { FAQItemOut } from '@/shared/api/types'

import { faqItemsQueryKey } from './useFAQItems'

interface UpdateFAQItemInput {
  faq_item_id: string
  question_text?: string
  answer_text?: string
  keywords?: string[]
  is_active?: boolean
}

export function useUpdateFAQItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ faq_item_id, ...body }: UpdateFAQItemInput) =>
      apiFetch<FAQItemOut>(`/api/v1/faq/items/${faq_item_id}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: faqItemsQueryKey })
    },
  })
}
