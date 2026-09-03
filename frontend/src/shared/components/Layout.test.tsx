import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAuthStore } from '@/features/auth/authStore'
import { apiFetch } from '@/shared/api/client'
import type { MeResponse } from '@/shared/api/types'
import { ThemeProvider } from '@/shared/theme/ThemeProvider'

import { Layout } from './Layout'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return {
    ...actual,
    apiFetch: vi.fn(),
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

function meResponse(restaurantEnabled: boolean, appointmentEnabled: boolean): MeResponse {
  return {
    staff_user: {
      staff_user_id: '00000000-0000-0000-0000-000000000000',
      name: 'Jane Owner',
      email_or_phone: 'owner@example.com',
      role: 'owner',
      last_login_at: null,
    },
    merchant: {
      merchant_id: '11111111-1111-1111-1111-111111111111',
      business_name: 'Test Business',
      onboarding_status: 'live',
      restaurant_enabled: restaurantEnabled,
      appointment_enabled: appointmentEnabled,
    },
  }
}

function renderLayout() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <MemoryRouter initialEntries={['/dashboard']}>
          <Routes>
            <Route element={<Layout />}>
              <Route path="dashboard" element={<div>Dashboard content</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  )
}

describe('Layout nav', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
    useAuthStore.setState({ accessToken: 'test-token', status: 'authenticated' })
  })

  it('shows Orders + Catalog, never Appointments/Services, for a restaurant-only merchant', async () => {
    mockedApiFetch.mockResolvedValueOnce(meResponse(true, false))

    renderLayout()

    expect(await screen.findByRole('link', { name: /orders/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /catalog/i })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /appointments/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /services/i })).not.toBeInTheDocument()
  })

  it('shows Appointments + Services, never Orders/Catalog, for an appointment-only merchant', async () => {
    mockedApiFetch.mockResolvedValueOnce(meResponse(false, true))

    renderLayout()

    expect(await screen.findByRole('link', { name: /appointments/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /services/i })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /orders/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /catalog/i })).not.toBeInTheDocument()
  })

  it('shows all four -- Orders, Catalog, Appointments, Services -- when both verticals are enabled', async () => {
    mockedApiFetch.mockResolvedValueOnce(meResponse(true, true))

    renderLayout()

    expect(await screen.findByRole('link', { name: /orders/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /catalog/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /appointments/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /services/i })).toBeInTheDocument()
  })

  it('shows neither vertical-specific tab before a vertical is chosen', async () => {
    mockedApiFetch.mockResolvedValueOnce(meResponse(false, false))

    renderLayout()

    await screen.findByText('Dashboard content')
    expect(screen.queryByRole('link', { name: /orders/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /catalog/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /appointments/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /services/i })).not.toBeInTheDocument()
  })
})
