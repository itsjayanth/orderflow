import { useMutation, useQueryClient } from '@tanstack/react-query'

import { onboardingStatusQueryKey } from '@/features/onboarding/useOnboarding'
import { apiFetch } from '@/shared/api/client'
import type { MenuItem } from '@/shared/api/types'

import { menuItemsQueryKey } from './useMenuItems'

interface CreateMenuItemInput {
  category: string
  name: string
  price: string
  image_url?: string
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
      // A new item is available by default, which can flip onboarding_status
      // to catalog_ready/live server-side (ARCHITECTURE.md Section 5).
      queryClient.invalidateQueries({ queryKey: onboardingStatusQueryKey })
    },
  })
}
