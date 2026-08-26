import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/shared/api/client'
import type { OnboardingStatusOut, WhatsAppSettingsOut } from '@/shared/api/types'

import { OnboardingPage } from './OnboardingPage'
import { useOnboardingWizardStore } from './onboardingWizardStore'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return {
    ...actual,
    apiFetch: vi.fn(),
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <OnboardingPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function statusResponse(overrides: Partial<OnboardingStatusOut> = {}): OnboardingStatusOut {
  return {
    onboarding_status: 'registered',
    whatsapp_connected: false,
    profile_completed: false,
    has_available_item: false,
    ...overrides,
  }
}

describe('OnboardingPage', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
    useOnboardingWizardStore.setState({ currentStep: 0 })
  })

  it('shows the Connect WhatsApp step for a freshly registered merchant', async () => {
    mockedApiFetch.mockResolvedValueOnce(statusResponse())

    renderPage()

    expect(await screen.findByLabelText('Phone number ID')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /connect & continue/i })).toBeInTheDocument()
  })

  it('submitting the WhatsApp form calls the update mutation with the right payload', async () => {
    mockedApiFetch.mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/v1/onboarding/status') return Promise.resolve(statusResponse())
      if (path === '/api/v1/onboarding/whatsapp' && init?.method === 'PUT') {
        return Promise.resolve<WhatsAppSettingsOut>({
          phone_number_id: '1234567890',
          display_phone_number: null,
          access_token_set: true,
          connection_status: 'connected',
        })
      }
      return Promise.reject(new Error(`Unexpected apiFetch call: ${path}`))
    })

    renderPage()
    await screen.findByLabelText('Phone number ID')

    fireEvent.change(screen.getByLabelText('Phone number ID'), { target: { value: '1234567890' } })
    fireEvent.change(screen.getByLabelText('Access token'), { target: { value: 'dummy-token' } })
    fireEvent.click(screen.getByRole('button', { name: /connect & continue/i }))

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith('/api/v1/onboarding/whatsapp', {
        method: 'PUT',
        body: JSON.stringify({
          phone_number_id: '1234567890',
          access_token: 'dummy-token',
          display_phone_number: '',
        }),
      }),
    )
  })

  it('shows a business category selector on the Business details step', async () => {
    mockedApiFetch.mockImplementation((path: string) => {
      if (path === '/api/v1/onboarding/status') {
        return Promise.resolve(
          statusResponse({ onboarding_status: 'whatsapp_verified', whatsapp_connected: true }),
        )
      }
      if (path === '/api/v1/onboarding/profile') {
        return Promise.resolve({
          address_line1: null,
          address_line2: null,
          city: null,
          pincode: null,
          business_category: null,
          license_no: null,
        })
      }
      return Promise.reject(new Error(`Unexpected apiFetch call: ${path}`))
    })

    renderPage()

    expect(await screen.findByText('Business details')).toBeInTheDocument()
    expect(screen.getByText('Select a category…')).toBeInTheDocument()
  })

  it('shows the live confirmation once onboarding_status is live', async () => {
    mockedApiFetch.mockResolvedValueOnce(
      statusResponse({
        onboarding_status: 'live',
        whatsapp_connected: true,
        profile_completed: true,
        has_available_item: true,
      }),
    )

    renderPage()

    expect(await screen.findByText("You're live!")).toBeInTheDocument()
  })
})
