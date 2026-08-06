import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'

interface HealthResponse {
  status: string
}

export function useHealthCheck() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => apiFetch<HealthResponse>('/health'),
    retry: 1,
  })
}
