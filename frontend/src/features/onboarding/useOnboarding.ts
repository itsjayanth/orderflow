import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { KitchenProfileOut, OnboardingStatusOut } from '@/shared/api/types'

// Exported so mutations elsewhere (connecting WhatsApp in Settings, creating
// a menu item in Catalog) can invalidate this query too -- both can advance
// onboarding_status server-side as a side effect.
export const onboardingStatusQueryKey = ['onboarding', 'status']
const PROFILE_QUERY_KEY = ['onboarding', 'profile']

export function useOnboardingStatus() {
  return useQuery({
    queryKey: onboardingStatusQueryKey,
    queryFn: () => apiFetch<OnboardingStatusOut>('/api/v1/onboarding/status'),
  })
}

export function useKitchenProfile() {
  return useQuery({
    queryKey: PROFILE_QUERY_KEY,
    queryFn: () => apiFetch<KitchenProfileOut>('/api/v1/onboarding/profile'),
  })
}

interface UpdateKitchenProfileInput {
  address_line1: string
  address_line2?: string
  city: string
  pincode: string
  cuisine_type: string
  fssai_license_no?: string
}

export function useUpdateKitchenProfile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: UpdateKitchenProfileInput) =>
      apiFetch<KitchenProfileOut>('/api/v1/onboarding/profile', {
        method: 'PUT',
        body: JSON.stringify(input),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PROFILE_QUERY_KEY })
      queryClient.invalidateQueries({ queryKey: onboardingStatusQueryKey })
    },
  })
}
