import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/shared/api/client'
import type { EmbeddedSignupResult, WhatsAppSettingsOut } from '@/shared/api/types'

import type { FacebookLoginResponse } from './useFacebookSdk'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return {
    ...actual,
    apiFetch: vi.fn(),
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const pendingSettings: WhatsAppSettingsOut = {
  phone_number_id: null,
  display_phone_number: null,
  access_token_set: false,
  connection_status: 'pending',
}

async function renderButton() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const onSaved = vi.fn()
  // Dynamic import (not a static one at the top of this file) so
  // ConnectWhatsAppButton's module-level VITE_META_APP_ID/
  // VITE_META_ES_CONFIG_ID reads happen after vi.stubEnv() + vi.resetModules()
  // in each describe block's beforeEach below -- a static import would
  // freeze those at whatever the very first test run's env was.
  const { ConnectWhatsAppButton } = await import('./ConnectWhatsAppButton')
  render(
    <QueryClientProvider client={queryClient}>
      <ConnectWhatsAppButton data={pendingSettings} onSaved={onSaved} />
    </QueryClientProvider>,
  )
  return { onSaved }
}

function dispatchEmbeddedSignupMessage(payload: object) {
  window.dispatchEvent(
    new MessageEvent('message', {
      origin: 'https://www.facebook.com',
      data: JSON.stringify({ type: 'WA_EMBEDDED_SIGNUP', ...payload }),
    }),
  )
}

describe('ConnectWhatsAppButton without Meta configured (VITE_META_APP_ID unset)', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
    // Explicitly unset rather than relying on the ambient env being empty --
    // frontend/.env has real values for local dev once Meta is configured,
    // which this describe block deliberately tests the absence of.
    vi.stubEnv('VITE_META_APP_ID', '')
    vi.stubEnv('VITE_META_ES_CONFIG_ID', '')
    vi.resetModules()
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('shows only the manual-entry form, open by default', async () => {
    await renderButton()

    expect(
      screen.queryByRole('button', { name: /connect your whatsapp business account/i }),
    ).not.toBeInTheDocument()
    expect(screen.getByLabelText('Phone number ID')).toBeInTheDocument()
  })
})

describe('ConnectWhatsAppButton with Meta configured', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
    vi.stubEnv('VITE_META_APP_ID', 'test-meta-app-id')
    vi.stubEnv('VITE_META_ES_CONFIG_ID', 'test-es-config-id')
    vi.resetModules()
    delete (window as { FB?: unknown }).FB
  })

  afterEach(() => {
    vi.unstubAllEnvs()
    delete (window as { FB?: unknown }).FB
  })

  it('shows the connect button and hides the manual form by default', async () => {
    await renderButton()

    expect(
      screen.getByRole('button', { name: /connect your whatsapp business account/i }),
    ).toBeInTheDocument()
    expect(screen.queryByLabelText('Phone number ID')).not.toBeInTheDocument()
  })

  it('clicking connect calls FB.login with the Embedded Signup v4 shape, then forwards the popup code + session data to the backend', async () => {
    let loginCallback: ((response: FacebookLoginResponse) => void) | undefined
    const fbLogin = vi.fn((callback: (response: FacebookLoginResponse) => void) => {
      loginCallback = callback
    })
    ;(window as { FB?: unknown }).FB = { init: vi.fn(), login: fbLogin }

    mockedApiFetch.mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/v1/onboarding/whatsapp/embedded-signup' && init?.method === 'POST') {
        const result: EmbeddedSignupResult = {
          status: 'connected',
          message: 'WhatsApp connected.',
          phone_number_id: 'PHONE_1',
          display_phone_number: '+91 90000 00000',
          connection_status: 'connected',
          pending_steps: [],
        }
        return Promise.resolve(result)
      }
      return Promise.reject(new Error(`Unexpected apiFetch call: ${path}`))
    })

    const { onSaved } = await renderButton()

    fireEvent.click(screen.getByRole('button', { name: /connect your whatsapp business account/i }))

    expect(fbLogin).toHaveBeenCalledWith(expect.any(Function), {
      config_id: 'test-es-config-id',
      response_type: 'code',
      override_default_response_type: true,
      extras: { setup: {} },
    })

    // Meta's popup posts the WABA/phone_number_id session data via
    // `message` before FB.login's own callback later fires with the code.
    dispatchEmbeddedSignupMessage({
      event: 'FINISH',
      data: { waba_id: 'WABA_1', phone_number_id: 'PHONE_1', business_id: 'BIZ_1' },
    })
    loginCallback?.({ authResponse: { code: 'auth-code' } })

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith('/api/v1/onboarding/whatsapp/embedded-signup', {
        method: 'POST',
        body: JSON.stringify({
          code: 'auth-code',
          waba_id: 'WABA_1',
          phone_number_id: 'PHONE_1',
          business_id: 'BIZ_1',
          event: 'FINISH',
          backend_base_url: 'http://localhost:8000',
        }),
      }),
    )
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
  })

  it('ignores a message event from a non-Facebook origin', async () => {
    ;(window as { FB?: unknown }).FB = { init: vi.fn(), login: vi.fn() }
    await renderButton()

    window.dispatchEvent(
      new MessageEvent('message', {
        origin: 'https://evilfacebook.com',
        data: JSON.stringify({
          type: 'WA_EMBEDDED_SIGNUP',
          event: 'FINISH',
          data: { waba_id: 'ATTACKER_WABA' },
        }),
      }),
    )

    // No assertion target beyond "doesn't throw / doesn't call apiFetch" --
    // there's no session state to observe directly from outside the hook.
    expect(mockedApiFetch).not.toHaveBeenCalled()
  })

  it('closing the popup without a code (CANCEL) does not call the backend', async () => {
    let loginCallback: ((response: FacebookLoginResponse) => void) | undefined
    const fbLogin = vi.fn((callback: (response: FacebookLoginResponse) => void) => {
      loginCallback = callback
    })
    ;(window as { FB?: unknown }).FB = { init: vi.fn(), login: fbLogin }

    await renderButton()
    fireEvent.click(screen.getByRole('button', { name: /connect your whatsapp business account/i }))
    loginCallback?.({ status: 'user_cancelled' })

    expect(mockedApiFetch).not.toHaveBeenCalled()
  })
})
