import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { onboardingStatusQueryKey } from '@/features/onboarding/useOnboarding'
import { apiFetch } from '@/shared/api/client'
import type {
  EmbeddedSignupConfigOut,
  WhatsAppFlowSetupResult,
  WhatsAppSettingsOut,
  WhatsAppTestMessageResult,
} from '@/shared/api/types'

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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEY })
      // Connecting WhatsApp can advance onboarding_status server-side
      // (ARCHITECTURE.md Section 5).
      queryClient.invalidateQueries({ queryKey: onboardingStatusQueryKey })
    },
  })
}

export function useSendTestWhatsAppMessage() {
  return useMutation({
    mutationFn: (to: string) =>
      apiFetch<WhatsAppTestMessageResult>('/api/v1/onboarding/whatsapp/test-message', {
        method: 'POST',
        body: JSON.stringify({ to }),
      }),
  })
}

export function useEmbeddedSignupConfig() {
  return useQuery({
    queryKey: ['settings', 'whatsapp', 'embedded-signup', 'config'],
    queryFn: () =>
      apiFetch<EmbeddedSignupConfigOut>('/api/v1/onboarding/whatsapp/embedded-signup/config'),
  })
}

interface CompleteEmbeddedSignupInput {
  code: string
  waba_id: string
  phone_number_id: string
}

export function useCompleteEmbeddedSignup() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: CompleteEmbeddedSignupInput) =>
      apiFetch<WhatsAppSettingsOut>('/api/v1/onboarding/whatsapp/embedded-signup/complete', {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEY })
      queryClient.invalidateQueries({ queryKey: onboardingStatusQueryKey })
    },
  })
}

export function useSetupWhatsAppFlow() {
  return useMutation({
    mutationFn: (metaWabaId: string) =>
      apiFetch<WhatsAppFlowSetupResult>('/api/v1/onboarding/whatsapp/flow-setup', {
        method: 'POST',
        body: JSON.stringify({
          meta_waba_id: metaWabaId,
          // Never user-facing -- same env var api/client.ts's API_BASE_URL reads.
          backend_base_url: import.meta.env.VITE_API_URL ?? 'http://localhost:8000',
        }),
      }),
  })
}
