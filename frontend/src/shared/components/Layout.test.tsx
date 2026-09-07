import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAuthStore } from '@/features/auth/authStore'
import { apiFetch } from '@/shared/api/client'
import type { MeResponse, SubscriptionOut } from '@/shared/api/types'
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
      website_url: null,
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

function subscriptionResponse(
  status: SubscriptionOut['status'],
  trialEndsAt: string | null = null,
): SubscriptionOut {
  return {
    merchant_id: '11111111-1111-1111-1111-111111111111',
    plan: {
      plan_id: 'growth-monthly',
      tier: 'growth',
      billing_interval: 'monthly',
      display_name: 'Growth',
      price_inr: '999.00',
      order_cap: 500,
      whatsapp_flow_enabled: true,
      branding_required: false,
    },
    status,
    trial_ends_at: trialEndsAt,
    current_period_start: null,
    current_period_end: null,
    past_due_since: null,
    cancel_at_period_end: false,
    orders_used_this_cycle: 5,
    order_cap: 500,
  }
}

// Layout now fires /api/v1/auth/me (nav items) and /api/v1/billing/subscription
// (TrialBanner) concurrently on mount -- routing by path rather than call
// order avoids a race between the two queries deciding which gets which
// canned response.
function mockRoutes(
  me: MeResponse,
  subscription: SubscriptionOut = subscriptionResponse('active'),
) {
  mockedApiFetch.mockImplementation((path: string) => {
    if (path === '/api/v1/auth/me') return Promise.resolve(me)
    if (path === '/api/v1/billing/subscription') return Promise.resolve(subscription)
    return Promise.reject(new Error(`unexpected apiFetch call: ${path}`))
  })
}

describe('Layout nav', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
    useAuthStore.setState({ accessToken: 'test-token', status: 'authenticated' })
  })

  it('shows Orders + Catalog, never Appointments/Services, for a restaurant-only merchant', async () => {
    mockRoutes(meResponse(true, false))

    renderLayout()

    expect(await screen.findByRole('link', { name: /orders/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /catalog/i })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /appointments/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /services/i })).not.toBeInTheDocument()
  })

  it('shows Appointments + Services, never Orders/Catalog, for an appointment-only merchant', async () => {
    mockRoutes(meResponse(false, true))

    renderLayout()

    expect(await screen.findByRole('link', { name: /appointments/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /services/i })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /orders/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /catalog/i })).not.toBeInTheDocument()
  })

  it('shows all four -- Orders, Catalog, Appointments, Services -- when both verticals are enabled', async () => {
    mockRoutes(meResponse(true, true))

    renderLayout()

    expect(await screen.findByRole('link', { name: /orders/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /catalog/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /appointments/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /services/i })).toBeInTheDocument()
  })

  it('shows neither vertical-specific tab before a vertical is chosen', async () => {
    mockRoutes(meResponse(false, false))

    renderLayout()

    await screen.findByText('Dashboard content')
    expect(screen.queryByRole('link', { name: /orders/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /catalog/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /appointments/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /services/i })).not.toBeInTheDocument()
  })
})

describe('Layout trial banner', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
    useAuthStore.setState({ accessToken: 'test-token', status: 'authenticated' })
  })

  it('shows a trial countdown banner when the subscription is trialing', async () => {
    const trialEndsAt = new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString()
    mockRoutes(meResponse(true, false), subscriptionResponse('trialing', trialEndsAt))

    renderLayout()

    expect(await screen.findByText(/3 days left in your Growth trial/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Upgrade now' })).toHaveAttribute(
      'href',
      '/settings/billing',
    )
  })

  it('shows an expired-trial banner once the subscription has lapsed to Starter limits', async () => {
    mockRoutes(meResponse(true, false), subscriptionResponse('expired'))

    renderLayout()

    expect(
      await screen.findByText(/Your trial has ended -- you're on Starter limits/),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'View plans' })).toHaveAttribute(
      'href',
      '/settings/billing',
    )
  })

  it('shows no banner for an active subscription', async () => {
    mockRoutes(meResponse(true, false), subscriptionResponse('active'))

    renderLayout()

    await screen.findByText('Dashboard content')
    expect(screen.queryByText(/trial/i)).not.toBeInTheDocument()
  })

  it('dismisses the banner for the rest of the session when the close button is clicked', async () => {
    const trialEndsAt = new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString()
    mockRoutes(meResponse(true, false), subscriptionResponse('trialing', trialEndsAt))

    renderLayout()

    const dismiss = await screen.findByRole('button', { name: 'Dismiss' })
    fireEvent.click(dismiss)

    expect(screen.queryByText(/days left in your Growth trial/)).not.toBeInTheDocument()
  })
})
