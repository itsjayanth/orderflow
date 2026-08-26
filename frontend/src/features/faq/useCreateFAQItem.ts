import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { FAQItemOut } from '@/shared/api/types'

import { faqItemsQueryKey } from './useFAQItems'

interface CreateFAQItemInput {
  question_text: string
  answer_text: string
  keywords: string[]
}

export function useCreateFAQItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateFAQItemInput) =>
      apiFetch<FAQItemOut>('/api/v1/faq/items', {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: faqItemsQueryKey })
    },
  })
}
