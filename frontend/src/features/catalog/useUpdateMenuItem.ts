import { useMutation, useQueryClient } from '@tanstack/react-query'

import { onboardingStatusQueryKey } from '@/features/onboarding/useOnboarding'
import { apiFetch } from '@/shared/api/client'
import type { MenuItem } from '@/shared/api/types'

import { menuItemsQueryKey } from './useMenuItems'

interface UpdateMenuItemInput {
  menu_item_id: string
  category?: string
  name?: string
  price?: string
  is_available?: boolean
  image_url?: string
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
      queryClient.invalidateQueries({ queryKey: onboardingStatusQueryKey })
    },
  })
}
