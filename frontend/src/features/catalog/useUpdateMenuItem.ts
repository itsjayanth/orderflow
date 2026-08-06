import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { MenuItem } from '@/shared/api/types'

import { menuItemsQueryKey } from './useMenuItems'

interface UpdateMenuItemInput {
  menu_item_id: string
  category?: string
  name?: string
  price?: string
  is_available?: boolean
}

export function useUpdateMenuItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ menu_item_id, ...body }: UpdateMenuItemInput) =>
      apiFetch<MenuItem>(`/api/v1/catalog/items/${menu_item_id}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: menuItemsQueryKey })
    },
  })
}
