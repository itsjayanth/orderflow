import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'

import { App } from './App'
import { useAuthStore } from './features/auth/authStore'

describe('App', () => {
  beforeEach(() => {
    useAuthStore.setState({ accessToken: 'test-token', status: 'authenticated' })
  })

  it('renders the dashboard nav for an authenticated user', () => {
    const queryClient = new QueryClient()
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <App />
        </MemoryRouter>
      </QueryClientProvider>,
    )

    expect(screen.getByText('Orderflow')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
  })

  it('redirects an unauthenticated user to /login', () => {
    useAuthStore.setState({ accessToken: null, status: 'unauthenticated' })
    const queryClient = new QueryClient()
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <App />
        </MemoryRouter>
      </QueryClientProvider>,
    )

    expect(screen.getByRole('heading', { name: 'Log in to Orderflow' })).toBeInTheDocument()
  })
})
