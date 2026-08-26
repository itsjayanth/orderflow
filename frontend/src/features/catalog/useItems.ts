import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { Item } from '@/shared/api/types'

export const itemsQueryKey = ['catalog', 'items'] as const

export function useItems() {
  return useQuery({
    queryKey: itemsQueryKey,
    queryFn: () => apiFetch<Item[]>('/api/v1/catalog/items'),
  })
}
