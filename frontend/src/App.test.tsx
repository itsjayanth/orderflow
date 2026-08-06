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

  it('renders the dashboard nav for an authenticated user at /dashboard', () => {
    const queryClient = new QueryClient()
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/dashboard']}>
          <App />
        </MemoryRouter>
      </QueryClientProvider>,
    )

    expect(screen.getByText('Orderflow')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
  })

  it('redirects an unauthenticated user hitting /dashboard to /login', () => {
    useAuthStore.setState({ accessToken: null, status: 'unauthenticated' })
    const queryClient = new QueryClient()
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/dashboard']}>
          <App />
        </MemoryRouter>
      </QueryClientProvider>,
    )

    expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
  })

  it('renders the public marketing home page at / for an unauthenticated visitor', () => {
    useAuthStore.setState({ accessToken: null, status: 'unauthenticated' })
    const queryClient = new QueryClient()
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/']}>
          <App />
        </MemoryRouter>
      </QueryClientProvider>,
    )

    expect(
      screen.getByRole('heading', {
        name: 'Take orders where your customers already are — WhatsApp.',
      }),
    ).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Log in' })[0]).toHaveAttribute('href', '/login')
    expect(screen.getAllByRole('link', { name: 'Register your restaurant' })[0]).toHaveAttribute(
      'href',
      '/register',
    )
  })
})
