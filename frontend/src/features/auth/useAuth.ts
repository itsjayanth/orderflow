import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'

import { apiFetch } from '@/shared/api/client'
import type { AccessTokenResponse, MeResponse } from '@/shared/api/types'

import { useAuthStore } from './authStore'

interface LoginInput {
  email_or_phone: string
  password: string
}

interface RegisterInput {
  business_name: string
  owner_name: string
  owner_contact: string
  password: string
}

export function useLogin() {
  const setAccessToken = useAuthStore((s) => s.setAccessToken)
  return useMutation({
    mutationFn: (input: LoginInput) =>
      apiFetch<AccessTokenResponse>('/api/v1/auth/login', {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    onSuccess: (data) => setAccessToken(data.access_token),
  })
}

export function useRegister() {
  const setAccessToken = useAuthStore((s) => s.setAccessToken)
  return useMutation({
    mutationFn: (input: RegisterInput) =>
      apiFetch<AccessTokenResponse>('/api/v1/auth/register', {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    onSuccess: (data) => setAccessToken(data.access_token),
  })
}

export function useLogout() {
  const setAccessToken = useAuthStore((s) => s.setAccessToken)
  return useMutation({
    mutationFn: () => apiFetch<void>('/api/v1/auth/logout', { method: 'POST' }),
    onSuccess: () => setAccessToken(null),
  })
}

export function useMe() {
  const status = useAuthStore((s) => s.status)
  return useQuery({
    queryKey: ['auth', 'me'],
    queryFn: () => apiFetch<MeResponse>('/api/v1/auth/me'),
    enabled: status === 'authenticated',
  })
}

// Resolves auth state on first load by attempting a silent refresh against
// the httpOnly cookie — the access token itself never survives a reload.
export function useAuthBootstrap() {
  const status = useAuthStore((s) => s.status)
  const setAccessToken = useAuthStore((s) => s.setAccessToken)

  useEffect(() => {
    if (status !== 'idle') return
    apiFetch<AccessTokenResponse>('/api/v1/auth/refresh', { method: 'POST' })
      .then((body) => setAccessToken(body.access_token))
      .catch(() => setAccessToken(null))
  }, [status, setAccessToken])
}
