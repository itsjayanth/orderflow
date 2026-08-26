import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/shared/api/client'
import type { EmbeddedSignupConfigOut } from '@/shared/api/types'

import { EmbeddedSignupButton } from './EmbeddedSignupButton'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return {
    ...actual,
    apiFetch: vi.fn(),
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

function renderButton() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <EmbeddedSignupButton />
    </QueryClientProvider>,
  )
}

describe('EmbeddedSignupButton', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('shows a not-configured message instead of a button when the server has no Meta app credentials', async () => {
    const config: EmbeddedSignupConfigOut = {
      app_id: '',
      config_id: '',
      graph_api_version: 'v21.0',
      configured: false,
    }
    mockedApiFetch.mockResolvedValue(config)

    renderButton()

    expect(await screen.findByText(/Embedded Signup isn't configured/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Connect WhatsApp' })).not.toBeInTheDocument()
  })

  it('renders an enabled "Connect WhatsApp" button when the server is configured', async () => {
    const config: EmbeddedSignupConfigOut = {
      app_id: 'app-123',
      config_id: 'cfg-1',
      graph_api_version: 'v21.0',
      configured: true,
    }
    mockedApiFetch.mockResolvedValue(config)

    renderButton()

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Connect WhatsApp' })).toBeEnabled(),
    )
  })
})
