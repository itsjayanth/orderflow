import { create } from 'zustand'

type AuthStatus = 'idle' | 'authenticated' | 'unauthenticated'

// Access token lives in memory only (not localStorage, to limit XSS blast
// radius per TECH_STACK.md) — the refresh token is an httpOnly cookie the
// browser sends automatically, never visible to JS. A page reload starts
// 'idle' and resolves via useAuthBootstrap's silent /auth/refresh call.
interface AuthState {
  accessToken: string | null
  status: AuthStatus
  setAccessToken: (token: string | null) => void
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  status: 'idle',
  setAccessToken: (accessToken) =>
    set({ accessToken, status: accessToken ? 'authenticated' : 'unauthenticated' }),
}))
