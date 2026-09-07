import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAuthStore } from '@/features/auth/authStore'
import { apiFetch } from '@/shared/api/client'
import type { PlanOut, SubscriptionOut } from '@/shared/api/types'

import { BillingSettingsPage } from './BillingSettingsPage'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return {
    ...actual,
    apiFetch: vi.fn(),
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const growthPlan: PlanOut = {
  plan_id: 'growth-monthly',
  tier: 'growth',
  billing_interval: 'monthly',
  display_name: 'Growth',
  price_inr: '999.00',
  order_cap: 500,
  whatsapp_flow_enabled: true,
  branding_required: false,
}

const proPlan: PlanOut = {
  plan_id: 'pro-monthly',
  tier: 'pro',
  billing_interval: 'monthly',
  display_name: 'Pro',
  price_inr: '2499.00',
  order_cap: null,
  whatsapp_flow_enabled: true,
  branding_required: false,
}

function trialingSubscription(): SubscriptionOut {
  return {
    merchant_id: '11111111-1111-1111-1111-111111111111',
    plan: growthPlan,
    status: 'trialing',
    trial_ends_at: new Date(Date.now() + 5 * 24 * 60 * 60 * 1000).toISOString(),
    current_period_start: null,
    current_period_end: null,
    past_due_since: null,
    cancel_at_period_end: false,
    orders_used_this_cycle: 12,
    order_cap: 500,
  }
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <BillingSettingsPage />
    </QueryClientProvider>,
  )
}

describe('BillingSettingsPage', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
    useAuthStore.setState({ accessToken: 'test-token', status: 'authenticated' })
  })

  it('shows the current plan, status, trial countdown, and usage', async () => {
    mockedApiFetch.mockImplementation((path: string) => {
      if (path === '/api/v1/billing/subscription') return Promise.resolve(trialingSubscription())
      if (path === '/api/v1/billing/plans') return Promise.resolve([growthPlan, proPlan])
      return Promise.reject(new Error(`unexpected apiFetch call: ${path}`))
    })

    renderPage()

    expect(await screen.findByText('Growth plan')).toBeInTheDocument()
    expect(screen.getByText('Free trial')).toBeInTheDocument()
    expect(screen.getByText(/5 days left in your free trial/)).toBeInTheDocument()
    expect(screen.getByText(/12 orders used of 500/)).toBeInTheDocument()
  })

  it('opens the plan picker and calls change-plan when a different plan is picked', async () => {
    const activeSub: SubscriptionOut = { ...trialingSubscription(), status: 'active' }
    mockedApiFetch.mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/v1/billing/subscription') return Promise.resolve(activeSub)
      if (path === '/api/v1/billing/plans') return Promise.resolve([growthPlan, proPlan])
      if (path === '/api/v1/billing/change-plan' && init?.method === 'POST') {
        return Promise.resolve({ ...activeSub, plan: proPlan })
      }
      return Promise.reject(new Error(`unexpected apiFetch call: ${path}`))
    })

    renderPage()
    await screen.findByText('Growth plan')

    fireEvent.click(screen.getByRole('button', { name: 'Upgrade / downgrade' }))
    const proOption = await screen.findByRole('button', { name: /Pro.*INR 2499.00/ })
    fireEvent.click(proOption)

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        '/api/v1/billing/change-plan',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ plan_id: 'pro-monthly' }),
        }),
      ),
    )
  })

  it('cancels the subscription after confirming the alert dialog', async () => {
    const activeSub: SubscriptionOut = { ...trialingSubscription(), status: 'active' }
    mockedApiFetch.mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/v1/billing/subscription') return Promise.resolve(activeSub)
      if (path === '/api/v1/billing/plans') return Promise.resolve([growthPlan, proPlan])
      if (path === '/api/v1/billing/cancel' && init?.method === 'POST') {
        return Promise.resolve({ ...activeSub, status: 'canceled' })
      }
      return Promise.reject(new Error(`unexpected apiFetch call: ${path}`))
    })

    renderPage()
    await screen.findByText('Growth plan')

    fireEvent.click(screen.getByRole('button', { name: 'Cancel subscription' }))
    const dialog = await screen.findByRole('alertdialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel subscription' }))

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith('/api/v1/billing/cancel', { method: 'POST' }),
    )
  })
})
