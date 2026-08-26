import { useMutation, useQueryClient } from '@tanstack/react-query'

import { onboardingStatusQueryKey } from '@/features/onboarding/useOnboarding'
import { apiFetch } from '@/shared/api/client'
import type { Item } from '@/shared/api/types'

import { itemsQueryKey } from './useItems'

interface UpdateItemInput {
  item_id: string
  category?: string
  name?: string
  price?: string
  is_available?: boolean
  image_url?: string
}

export function useUpdateItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ item_id, ...body }: UpdateItemInput) =>
      apiFetch<Item>(`/api/v1/catalog/items/${item_id}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: itemsQueryKey })
      queryClient.invalidateQueries({ queryKey: onboardingStatusQueryKey })
    },
  })
}
