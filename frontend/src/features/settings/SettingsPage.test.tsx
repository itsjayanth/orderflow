import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/shared/api/client'
import type {
  NotificationTemplateOut,
  PaymentSettingsOut,
  WhatsAppSettingsOut,
} from '@/shared/api/types'

import { SettingsPage } from './SettingsPage'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return {
    ...actual,
    apiFetch: vi.fn(),
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const paymentSettings: PaymentSettingsOut = {
  razorpay_key_id: null,
  razorpay_key_secret_set: false,
  using_real_gateway: false,
}

const whatsappSettings: WhatsAppSettingsOut = {
  phone_number_id: null,
  display_phone_number: null,
  access_token_set: false,
  connection_status: 'pending',
}

const defaultTemplates: NotificationTemplateOut[] = [
  {
    notification_kind: 'order_confirmed',
    template_name: '',
    language_code: 'en',
    body: "Order confirmed! We'll let you know when it's ready.",
    is_active: false,
    is_configured: false,
  },
  {
    notification_kind: 'order_ready',
    template_name: '',
    language_code: 'en',
    body: 'Your order is ready!',
    is_active: false,
    is_configured: false,
  },
  {
    notification_kind: 'order_completed',
    template_name: '',
    language_code: 'en',
    body: 'Your order is complete. Enjoy your meal!',
    is_active: false,
    is_configured: false,
  },
]

function mockRoutes(templates: NotificationTemplateOut[] = defaultTemplates) {
  mockedApiFetch.mockImplementation((path: string) => {
    if (path === '/api/v1/payments/settings') return Promise.resolve(paymentSettings)
    if (path === '/api/v1/onboarding/whatsapp') return Promise.resolve(whatsappSettings)
    if (path === '/api/v1/notifications/templates') return Promise.resolve(templates)
    return Promise.reject(new Error(`unexpected apiFetch call: ${path}`))
  })
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <SettingsPage />
    </QueryClientProvider>,
  )
}

describe('SettingsPage templates section', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('shows all three notification kinds defaulting to "Using default"', async () => {
    mockRoutes()

    renderPage()

    expect(await screen.findByText('Order confirmed')).toBeInTheDocument()
    expect(screen.getByText('Order ready')).toBeInTheDocument()
    expect(screen.getByText('Order completed')).toBeInTheDocument()
    expect(screen.getAllByText('Using default')).toHaveLength(3)
  })

  it('saving a template calls the update endpoint with the right payload', async () => {
    mockRoutes()
    const updated: NotificationTemplateOut = {
      ...defaultTemplates[0],
      template_name: 'confirmed_v1',
      is_active: true,
      is_configured: true,
    }
    mockedApiFetch.mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/v1/payments/settings') return Promise.resolve(paymentSettings)
      if (path === '/api/v1/onboarding/whatsapp') return Promise.resolve(whatsappSettings)
      if (path === '/api/v1/notifications/templates') return Promise.resolve(defaultTemplates)
      if (path === '/api/v1/notifications/templates/order_confirmed' && init?.method === 'PUT') {
        return Promise.resolve(updated)
      }
      return Promise.reject(new Error(`unexpected apiFetch call: ${path}`))
    })

    renderPage()
    await screen.findByText('Order confirmed')

    // "order_confirmed" is the first of the three template rows.
    fireEvent.change(screen.getAllByLabelText('Template name')[0], {
      target: { value: 'confirmed_v1' },
    })
    fireEvent.click(screen.getAllByLabelText(/use this template/i)[0])
    fireEvent.click(screen.getAllByRole('button', { name: 'Save' })[0])

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        '/api/v1/notifications/templates/order_confirmed',
        expect.objectContaining({ method: 'PUT' }),
      ),
    )
    const call = mockedApiFetch.mock.calls.find(
      ([path]) => path === '/api/v1/notifications/templates/order_confirmed',
    )
    if (!call) throw new Error('expected PUT call not found')
    const body = JSON.parse((call[1] as RequestInit).body as string)
    expect(body).toEqual({
      template_name: 'confirmed_v1',
      language_code: 'en',
      body: "Order confirmed! We'll let you know when it's ready.",
      is_active: true,
    })
  })
})
