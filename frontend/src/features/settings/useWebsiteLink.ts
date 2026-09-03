import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { Merchant, WebsiteLinkClickStatsOut } from '@/shared/api/types'

// `enabled` lets callers skip the request entirely when there's no website
// link set yet -- nothing to have been clicked, so no point fetching.
export function useWebsiteLinkClickStats(days = 7, enabled = true) {
  return useQuery({
    queryKey: ['settings', 'website-link', 'clicks', days],
    queryFn: () =>
      apiFetch<WebsiteLinkClickStatsOut>(`/api/v1/auth/website-link/clicks?days=${days}`),
    enabled,
  })
}

interface UpdateWebsiteLinkInput {
  website_url: string | null
}

export function useUpdateWebsiteLink() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: UpdateWebsiteLinkInput) =>
      apiFetch<Merchant>('/api/v1/auth/website-link', {
        method: 'PUT',
        body: JSON.stringify(input),
      }),
    onSuccess: () => {
      // Merchant.website_url is read off GET /me elsewhere (this section
      // itself, and any future WhatsApp-menu preview) -- keep that in sync
      // immediately, same pattern as useSelectVerticals.
      queryClient.invalidateQueries({ queryKey: ['auth', 'me'] })
      queryClient.invalidateQueries({ queryKey: ['settings', 'website-link'] })
    },
  })
}
