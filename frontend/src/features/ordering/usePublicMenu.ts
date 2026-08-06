import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { PublicMenuOut } from '@/shared/api/types'

export function usePublicMenu(merchantId: string) {
  return useQuery({
    queryKey: ['ordering-flow', merchantId, 'menu'],
    queryFn: () => apiFetch<PublicMenuOut>(`/api/v1/ordering-flow/${merchantId}/menu`),
    enabled: !!merchantId,
    retry: false,
  })
}
