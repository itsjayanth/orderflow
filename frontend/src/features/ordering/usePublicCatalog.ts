import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { PublicCatalogOut } from '@/shared/api/types'

export function usePublicCatalog(merchantId: string) {
  return useQuery({
    queryKey: ['ordering-flow', merchantId, 'catalog'],
    queryFn: () => apiFetch<PublicCatalogOut>(`/api/v1/ordering-flow/${merchantId}/catalog`),
    enabled: !!merchantId,
    retry: false,
  })
}
