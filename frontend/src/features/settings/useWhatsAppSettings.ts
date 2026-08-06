import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { WhatsAppSettingsOut } from '@/shared/api/types'

const QUERY_KEY = ['settings', 'whatsapp']

export function useWhatsAppSettings() {
  return useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => apiFetch<WhatsAppSettingsOut>('/api/v1/onboarding/whatsapp'),
  })
}

interface UpdateWhatsAppSettingsInput {
  phone_number_id: string
  access_token: string
  display_phone_number?: string
}

export function useUpdateWhatsAppSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: UpdateWhatsAppSettingsInput) =>
      apiFetch<WhatsAppSettingsOut>('/api/v1/onboarding/whatsapp', {
        method: 'PUT',
        body: JSON.stringify(input),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEY }),
  })
}
