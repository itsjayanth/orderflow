import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { AudienceFilter, CampaignDetailOut, CampaignOut } from '@/shared/api/types'

export const campaignsQueryKey = ['campaigns'] as const

// Same cache-and-revalidate rationale as useOrders.ts's 5s poll -- "visible
// progress within seconds" applied to campaign send progress instead of
// order status.
const CAMPAIGN_DETAIL_REFETCH_INTERVAL_MS = 5_000

export function useCampaigns() {
  return useQuery({
    queryKey: campaignsQueryKey,
    queryFn: () => apiFetch<CampaignOut[]>('/api/v1/campaigns'),
  })
}

export function useCampaign(campaignId: string) {
  return useQuery({
    queryKey: [...campaignsQueryKey, campaignId],
    queryFn: () => apiFetch<CampaignDetailOut>(`/api/v1/campaigns/${campaignId}`),
    enabled: !!campaignId,
    // Only worth polling while a send is actually in progress -- a
    // draft/completed/failed campaign's detail never changes on its own.
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'scheduled' || status === 'sending'
        ? CAMPAIGN_DETAIL_REFETCH_INTERVAL_MS
        : false
    },
  })
}

interface CreateCampaignInput {
  name: string
  template_id: string
  audience_filter: AudienceFilter
  scheduled_at?: string
}

export function useCreateCampaign() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateCampaignInput) =>
      apiFetch<CampaignOut>('/api/v1/campaigns', {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: campaignsQueryKey })
    },
  })
}

export function useScheduleCampaign() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (campaignId: string) =>
      apiFetch<CampaignOut>(`/api/v1/campaigns/${campaignId}/schedule`, { method: 'POST' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: campaignsQueryKey })
    },
  })
}

export function useCancelCampaign() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (campaignId: string) =>
      apiFetch<CampaignOut>(`/api/v1/campaigns/${campaignId}/cancel`, { method: 'POST' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: campaignsQueryKey })
    },
  })
}
