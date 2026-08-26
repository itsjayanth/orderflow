import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { FAQItemOut } from '@/shared/api/types'

export const faqItemsQueryKey = ['faq', 'items'] as const

export function useFAQItems() {
  return useQuery({
    queryKey: faqItemsQueryKey,
    queryFn: () => apiFetch<FAQItemOut[]>('/api/v1/faq/items'),
  })
}
