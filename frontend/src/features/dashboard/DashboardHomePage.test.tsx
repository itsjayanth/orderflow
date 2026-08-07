import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAuthStore } from '@/features/auth/authStore'
import { apiFetch } from '@/shared/api/client'
import type { MeResponse, OnboardingStatusOut, OrderOut, OrderSummaryOut } from '@/shared/api/types'

import { DashboardHomePage } from './DashboardHomePage'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return {
    ...actual,
    apiFetch: vi.fn(),
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const meResponse: MeResponse = {
  staff_user: {
    staff_user_id: '00000000-0000-0000-0000-000000000000',
    name: 'Jane Owner',
    email_or_phone: 'owner@example.com',
    role: 'owner',
    last_login_at: null,
  },
  merchant: {
    merchant_id: '11111111-1111-1111-1111-111111111111',
    business_name: 'Test Kitchen',
    onboarding_status: 'live',
  },
}

const sampleOrder: OrderOut = {
  order_id: '22222222-2222-2222-2222-222222222222',
  order_number: 3,
  customer_id: '33333333-3333-3333-3333-333333333333',
  customer_name: 'Asha Rao',
  customer_whatsapp_number: '919876543210',
  order_type: 'pickup',
  payment_method: 'online',
  payment_status: 'paid',
  fulfillment_status: 'new',
  subtotal: '349.00',
  total: '349.00',
  currency: 'INR',
  placed_at: new Date().toISOString(),
  paid_at: null,
  ready_at: null,
  completed_at: null,
  items: [],
}

const sampleSummary: OrderSummaryOut = {
  total_orders: 1,
  revenue_generated: '349.00',
  amount_collected: '349.00',
  cod_orders: 0,
  new_orders: 1,
  preparing_orders: 0,
  ready_orders: 0,
  completed_orders: 0,
  cancelled_orders: 0,
}

function mockRoutes(overrides: {
  onboardingStatus?: OnboardingStatusOut['onboarding_status']
  orders?: OrderOut[]
  summary?: OrderSummaryOut
}) {
  const onboardingStatus = overrides.onboardingStatus ?? 'live'
  const orders = overrides.orders ?? [sampleOrder]
  const summary = overrides.summary ?? sampleSummary
  mockedApiFetch.mockImplementation((path: string) => {
    if (path === '/api/v1/auth/me') return Promise.resolve(meResponse)
    if (path === '/api/v1/onboarding/status') {
      return Promise.resolve<OnboardingStatusOut>({
        onboarding_status: onboardingStatus,
        whatsapp_connected: true,
        profile_completed: true,
        has_available_menu_item: true,
      })
    }
    // Must come before the generic /api/v1/orders prefix check below.
    if (path === '/api/v1/orders/summary') return Promise.resolve(summary)
    if (path.startsWith('/api/v1/orders')) return Promise.resolve(orders)
    return Promise.reject(new Error(`unexpected apiFetch call: ${path}`))
  })
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <DashboardHomePage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('DashboardHomePage', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
    useAuthStore.setState({ accessToken: 'test-token', status: 'authenticated' })
  })

  it('welcomes the merchant by business name and shows order stats', async () => {
    mockRoutes({})

    renderPage()

    expect(await screen.findByText('Welcome back, Test Kitchen')).toBeInTheDocument()
    expect(screen.getByText("Today's orders")).toBeInTheDocument()
    // "INR 349.00" appears both in the revenue hero card (formatted from
    // the summary) and in the recent-orders row (raw order.total) -- assert
    // presence, not uniqueness.
    expect(screen.getAllByText('INR 349.00').length).toBeGreaterThan(0)
    expect(screen.getByText(/Asha Rao/)).toBeInTheDocument()
  })

  it('shows a setup nudge when onboarding is not yet live', async () => {
    mockRoutes({ onboardingStatus: 'profile_completed', orders: [] })

    renderPage()

    expect(await screen.findByText('Finish setting up your restaurant')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Continue setup' })).toHaveAttribute(
      'href',
      '/onboarding',
    )
  })

  it('does not show the setup nudge once live', async () => {
    mockRoutes({ onboardingStatus: 'live' })

    renderPage()

    await screen.findByText('Welcome back, Test Kitchen')
    expect(screen.queryByText('Finish setting up your restaurant')).not.toBeInTheDocument()
  })

  it('shows an empty state when there are no orders yet', async () => {
    mockRoutes({ orders: [] })

    renderPage()

    expect(
      await screen.findByText(
        "No orders yet -- they'll show up here the moment a customer checks out.",
      ),
    ).toBeInTheDocument()
  })
})
