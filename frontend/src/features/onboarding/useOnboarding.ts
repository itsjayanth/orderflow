import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type {
  BusinessProfileOut,
  OnboardingStatusOut,
  VerticalsSelectionOut,
} from '@/shared/api/types'

// Exported so mutations elsewhere (connecting WhatsApp in Settings, creating
// an item in Catalog) can invalidate this query too -- both can advance
// onboarding_status server-side as a side effect.
export const onboardingStatusQueryKey = ['onboarding', 'status']
const PROFILE_QUERY_KEY = ['onboarding', 'profile']

export function useOnboardingStatus() {
  return useQuery({
    queryKey: onboardingStatusQueryKey,
    queryFn: () => apiFetch<OnboardingStatusOut>('/api/v1/onboarding/status'),
  })
}

export interface SelectVerticalsInput {
  restaurant_enabled: boolean
  appointment_enabled: boolean
}

// VERTICAL_TOGGLE_PLAN.md: multi-select, and callable any number of times --
// this same mutation backs both the onboarding wizard's first step and
// Settings' "Business types" section (adding a vertical after going live).
// No immutability guard on the backend, so no special-casing here either.
export function useSelectVerticals() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: SelectVerticalsInput) =>
      apiFetch<VerticalsSelectionOut>('/api/v1/onboarding/verticals', {
        method: 'PUT',
        body: JSON.stringify(input),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: onboardingStatusQueryKey })
      // Merchant.restaurant_enabled/appointment_enabled are also read off
      // GET /me for dashboard nav (Layout.tsx) -- keep that in sync the
      // moment they're set.
      queryClient.invalidateQueries({ queryKey: ['auth', 'me'] })
    },
  })
}

export function useBusinessProfile() {
  return useQuery({
    queryKey: PROFILE_QUERY_KEY,
    queryFn: () => apiFetch<BusinessProfileOut>('/api/v1/onboarding/profile'),
  })
}

interface UpdateBusinessProfileInput {
  address_line1: string
  address_line2?: string
  city: string
  pincode: string
  business_category: string
  license_no?: string
}

export function useUpdateBusinessProfile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: UpdateBusinessProfileInput) =>
      apiFetch<BusinessProfileOut>('/api/v1/onboarding/profile', {
        method: 'PUT',
        body: JSON.stringify(input),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PROFILE_QUERY_KEY })
      queryClient.invalidateQueries({ queryKey: onboardingStatusQueryKey })
    },
  })
}
