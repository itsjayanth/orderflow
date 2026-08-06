import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { MenuItem } from '@/shared/api/types'

import { menuItemsQueryKey } from './useMenuItems'

interface CreateMenuItemInput {
  category: string
  name: string
  price: string
}

export function useCreateMenuItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateMenuItemInput) =>
      apiFetch<MenuItem>('/api/v1/catalog/items', {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: menuItemsQueryKey })
    },
  })
}
