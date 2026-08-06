import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { MenuItem } from '@/shared/api/types'

export const menuItemsQueryKey = ['catalog', 'items'] as const

export function useMenuItems() {
  return useQuery({
    queryKey: menuItemsQueryKey,
    queryFn: () => apiFetch<MenuItem[]>('/api/v1/catalog/items'),
  })
}
