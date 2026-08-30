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

  // ConnectWhatsAppButton (embedded signup) collapses the manual-entry
  // form behind an "Advanced: connect manually" accordion whenever
  // VITE_META_APP_ID/VITE_META_ES_CONFIG_ID are configured -- open it
  // first so these tests, which exercise the manual fallback path, work
  // regardless of whether this env has Meta configured.
  async function openManualEntryIfCollapsed() {
    await screen.findByText('Connect WhatsApp, add your business details', { exact: false })
    const advancedToggle = screen.queryByRole('button', { name: /advanced: connect manually/i })
    if (advancedToggle && advancedToggle.getAttribute('data-state') !== 'open') {
      fireEvent.click(advancedToggle)
    }
    return screen.findByLabelText('Phone number ID')
  }

  it('shows the Connect WhatsApp step for a freshly registered merchant', async () => {
    mockedApiFetch.mockResolvedValueOnce(statusResponse())

    renderPage()

    expect(await openManualEntryIfCollapsed()).toBeInTheDocument()
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
    await openManualEntryIfCollapsed()

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

  it('shows the live confirmation once onboarding_status is live, skipping the optional FAQ step', async () => {
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
    // Reaching "live" never gates on, or stops at, the FAQ step.
    expect(screen.queryByLabelText('Question')).not.toBeInTheDocument()
  })

  it('shows the optional FAQ step when the server is at catalog_ready', async () => {
    mockedApiFetch.mockImplementation((path: string) => {
      if (path === '/api/v1/onboarding/status') {
        return Promise.resolve(
          statusResponse({
            onboarding_status: 'catalog_ready',
            whatsapp_connected: true,
            profile_completed: true,
            has_available_item: true,
          }),
        )
      }
      if (path === '/api/v1/faq/items') return Promise.resolve([])
      return Promise.reject(new Error(`Unexpected apiFetch call: ${path}`))
    })

    renderPage()

    expect(await screen.findByLabelText('Question')).toBeInTheDocument()
    expect(screen.getByLabelText('Answer')).toBeInTheDocument()
    expect(screen.getByText(/entirely optional/i)).toBeInTheDocument()
    expect(screen.getByText(/Where are you located\?/)).toBeInTheDocument()
  })

  it('submitting the FAQ step form calls the create mutation with parsed keywords', async () => {
    mockedApiFetch.mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/v1/onboarding/status') {
        return Promise.resolve(
          statusResponse({
            onboarding_status: 'catalog_ready',
            whatsapp_connected: true,
            profile_completed: true,
            has_available_item: true,
          }),
        )
      }
      if (path === '/api/v1/faq/items' && !init) return Promise.resolve([])
      if (path === '/api/v1/faq/items' && init?.method === 'POST') {
        return Promise.resolve({
          faq_item_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
          question_text: 'Where are you located?',
          answer_text: "We're at 12 MG Road, Bengaluru.",
          keywords: ['location', 'address'],
          is_active: true,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        })
      }
      return Promise.reject(new Error(`Unexpected apiFetch call: ${path}`))
    })

    renderPage()
    await screen.findByLabelText('Question')

    fireEvent.change(screen.getByLabelText('Question'), {
      target: { value: 'Where are you located?' },
    })
    fireEvent.change(screen.getByLabelText('Answer'), {
      target: { value: "We're at 12 MG Road, Bengaluru." },
    })
    fireEvent.change(screen.getByLabelText('Keywords (comma-separated, optional)'), {
      target: { value: 'location, address' },
    })
    fireEvent.click(screen.getByRole('button', { name: /add another/i }))

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith('/api/v1/faq/items', {
        method: 'POST',
        body: JSON.stringify({
          question_text: 'Where are you located?',
          answer_text: "We're at 12 MG Road, Bengaluru.",
          keywords: ['location', 'address'],
        }),
      }),
    )
  })
})
