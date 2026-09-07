import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAuthStore } from '@/features/auth/authStore'
import { apiFetch } from '@/shared/api/client'
import type { MeResponse, PlanOut, SubscriptionCheckoutOut } from '@/shared/api/types'

import { PricingPage } from './PricingPage'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return {
    ...actual,
    apiFetch: vi.fn(),
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const plans: PlanOut[] = [
  {
    plan_id: 'starter-monthly',
    tier: 'starter',
    billing_interval: 'monthly',
    display_name: 'Starter',
    price_inr: '0.00',
    order_cap: 50,
    whatsapp_flow_enabled: false,
    branding_required: true,
  },
  {
    plan_id: 'growth-monthly',
    tier: 'growth',
    billing_interval: 'monthly',
    display_name: 'Growth',
    price_inr: '999.00',
    order_cap: 500,
    whatsapp_flow_enabled: true,
    branding_required: false,
  },
  {
    plan_id: 'pro-monthly',
    tier: 'pro',
    billing_interval: 'monthly',
    display_name: 'Pro',
    price_inr: '2499.00',
    order_cap: null,
    whatsapp_flow_enabled: true,
    branding_required: false,
  },
  {
    plan_id: 'starter-annual',
    tier: 'starter',
    billing_interval: 'annual',
    display_name: 'Starter',
    price_inr: '0.00',
    order_cap: 50,
    whatsapp_flow_enabled: false,
    branding_required: true,
  },
  {
    plan_id: 'growth-annual',
    tier: 'growth',
    billing_interval: 'annual',
    display_name: 'Growth',
    price_inr: '9990.00',
    order_cap: 500,
    whatsapp_flow_enabled: true,
    branding_required: false,
  },
  {
    plan_id: 'pro-annual',
    tier: 'pro',
    billing_interval: 'annual',
    display_name: 'Pro',
    price_inr: '24990.00',
    order_cap: null,
    whatsapp_flow_enabled: true,
    branding_required: false,
  },
]

function meResponse(): MeResponse {
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
      restaurant_enabled: true,
      appointment_enabled: false,
      website_url: null,
    },
  }
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/pricing']}>
        <PricingPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('PricingPage', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
    useAuthStore.setState({ accessToken: null, status: 'idle' })
  })

  it('renders three tiers with monthly pricing by default when logged out', async () => {
    mockedApiFetch.mockImplementation((path: string) => {
      if (path === '/api/v1/billing/plans') return Promise.resolve(plans)
      return Promise.reject(new Error(`unexpected apiFetch call: ${path}`))
    })

    renderPage()

    expect(await screen.findByText('Starter')).toBeInTheDocument()
    expect(screen.getByText('Growth')).toBeInTheDocument()
    expect(screen.getByText('Pro')).toBeInTheDocument()
    expect(screen.getByText('INR 999 / month')).toBeInTheDocument()
    expect(screen.queryByText('INR 9,990 / year')).not.toBeInTheDocument()
  })

  it('switches to annual pricing when the toggle is clicked', async () => {
    mockedApiFetch.mockImplementation((path: string) => {
      if (path === '/api/v1/billing/plans') return Promise.resolve(plans)
      return Promise.reject(new Error(`unexpected apiFetch call: ${path}`))
    })

    renderPage()
    await screen.findByText('Growth')

    fireEvent.click(screen.getByRole('button', { name: 'Annual' }))

    expect(await screen.findByText('INR 9,990 / year')).toBeInTheDocument()
    expect(screen.queryByText('INR 999 / month')).not.toBeInTheDocument()
  })

  it('shows "Get started" links to /register when logged out, not a Subscribe button', async () => {
    mockedApiFetch.mockImplementation((path: string) => {
      if (path === '/api/v1/billing/plans') return Promise.resolve(plans)
      return Promise.reject(new Error(`unexpected apiFetch call: ${path}`))
    })

    renderPage()
    await screen.findByText('Growth')

    expect(screen.queryByRole('button', { name: 'Subscribe' })).not.toBeInTheDocument()
    const registerLinks = screen.getAllByRole('link', { name: 'Get started' })
    expect(registerLinks.length).toBeGreaterThan(0)
    for (const link of registerLinks) {
      expect(link).toHaveAttribute('href', '/register')
    }
  })

  it('shows Subscribe buttons and starts checkout when authenticated', async () => {
    useAuthStore.setState({ accessToken: 'test-token', status: 'authenticated' })
    const checkoutResponse: SubscriptionCheckoutOut = {
      provider_subscription_id: 'sub_123',
      checkout_url: 'https://dummy-checkout.orderflow.local/subscribe/sub_123',
    }
    mockedApiFetch.mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/v1/billing/plans') return Promise.resolve(plans)
      if (path === '/api/v1/auth/me') return Promise.resolve(meResponse())
      if (path === '/api/v1/billing/subscribe' && init?.method === 'POST') {
        return Promise.resolve(checkoutResponse)
      }
      return Promise.reject(new Error(`unexpected apiFetch call: ${path}`))
    })

    renderPage()
    await screen.findByText('Growth')

    const subscribeButtons = await screen.findAllByRole('button', { name: 'Subscribe' })
    expect(subscribeButtons.length).toBe(3)
    fireEvent.click(subscribeButtons[1])

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        '/api/v1/billing/subscribe',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ plan_id: 'growth-monthly' }),
        }),
      ),
    )
  })
})
