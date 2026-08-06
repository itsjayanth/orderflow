import { useAuthStore } from '@/features/auth/authStore'
import type { AccessTokenResponse } from '@/shared/api/types'

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const REFRESH_PATH = '/api/v1/auth/refresh'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function rawFetch(path: string, init?: RequestInit): Promise<Response> {
  const accessToken = useAuthStore.getState().accessToken
  return fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...init?.headers,
    },
  })
}

// Coalesces concurrent 401s into a single refresh call rather than firing
// one per failed request.
let refreshInFlight: Promise<boolean> | null = null

async function tryRefresh(): Promise<boolean> {
  refreshInFlight ??= (async () => {
    const response = await rawFetch(REFRESH_PATH, { method: 'POST' })
    if (!response.ok) {
      useAuthStore.getState().setAccessToken(null)
      return false
    }
    const body = (await response.json()) as AccessTokenResponse
    useAuthStore.getState().setAccessToken(body.access_token)
    return true
  })().finally(() => {
    refreshInFlight = null
  })
  return refreshInFlight
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let response = await rawFetch(path, init)

  if (response.status === 401 && path !== REFRESH_PATH) {
    const refreshed = await tryRefresh()
    if (refreshed) {
      response = await rawFetch(path, init)
    }
  }

  if (!response.ok) {
    throw new ApiError(response.status, await response.text())
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}
