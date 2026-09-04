import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/shared/api/client'
import type { MessageTemplateOut } from '@/shared/api/types'

import { TemplatesPage } from './TemplatesPage'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return {
    ...actual,
    apiFetch: vi.fn(),
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

function template(overrides: Partial<MessageTemplateOut> = {}): MessageTemplateOut {
  return {
    template_id: '11111111-1111-1111-1111-111111111111',
    name: 'order_promo',
    category: 'MARKETING',
    language_code: 'en_US',
    header_type: 'NONE',
    header_text: null,
    header_media_handle: null,
    header_filename: null,
    body_text: 'Hi there, check out today deals!',
    body_variable_count: 0,
    footer_text: null,
    buttons: [],
    meta_template_id: 'META_1',
    meta_approval_status: 'pending',
    meta_rejection_reason: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <TemplatesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('TemplatesPage', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('shows an empty state when there are no templates yet', async () => {
    mockedApiFetch.mockResolvedValueOnce([])

    renderPage()

    expect(await screen.findByText(/No templates yet/)).toBeInTheDocument()
  })

  it('renders a status badge per template, including a rejection-reason tooltip trigger', async () => {
    mockedApiFetch.mockResolvedValueOnce([
      template({ template_id: 't1', name: 'promo_pending', meta_approval_status: 'pending' }),
      template({ template_id: 't2', name: 'promo_approved', meta_approval_status: 'approved' }),
      template({
        template_id: 't3',
        name: 'promo_rejected',
        meta_approval_status: 'rejected',
        meta_rejection_reason: 'INVALID_FORMAT',
      }),
    ])

    renderPage()

    expect(await screen.findByText('promo_pending')).toBeInTheDocument()
    expect(screen.getByText('Pending review')).toBeInTheDocument()
    expect(screen.getByText('Approved')).toBeInTheDocument()
    expect(screen.getByText('Rejected')).toBeInTheDocument()
  })

  it('submitting the new-template form calls the create mutation with the right payload', async () => {
    mockedApiFetch.mockResolvedValueOnce([])
    mockedApiFetch.mockResolvedValueOnce(template())

    renderPage()
    await screen.findByText(/No templates yet/)

    fireEvent.change(screen.getByLabelText('Template name'), {
      target: { value: 'Order Promo' },
    })
    fireEvent.change(screen.getByLabelText('Body'), {
      target: { value: 'Hi there, check out today deals!' },
    })
    fireEvent.click(screen.getByRole('button', { name: /submit for approval/i }))

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith('/api/v1/campaigns/templates', {
        method: 'POST',
        body: JSON.stringify({
          name: 'Order Promo',
          category: 'MARKETING',
          header_type: 'NONE',
          header_text: undefined,
          header_media_base64: undefined,
          header_media_content_type: undefined,
          header_filename: undefined,
          body_text: 'Hi there, check out today deals!',
          footer_text: undefined,
          buttons: [],
        }),
      }),
    )
  })

  it('rejects a body with non-sequential variables before submitting', async () => {
    mockedApiFetch.mockResolvedValueOnce([])

    renderPage()
    await screen.findByText(/No templates yet/)

    fireEvent.change(screen.getByLabelText('Template name'), { target: { value: 'Promo' } })
    fireEvent.change(screen.getByLabelText('Body'), {
      target: { value: 'Hi {{1}}, {{3}}% off' },
    })
    fireEvent.click(screen.getByRole('button', { name: /submit for approval/i }))

    expect(
      await screen.findByText(/Variables must be \{\{1\}\}, \{\{2\}\}, \.\.\. in order/),
    ).toBeInTheDocument()
    // Only the initial list GET fired -- the invalid submission never
    // reached the create mutation.
    expect(mockedApiFetch).toHaveBeenCalledTimes(1)
  })

  it('deleting a template calls the delete mutation', async () => {
    mockedApiFetch.mockResolvedValueOnce([template({ template_id: 't1', name: 'order_promo' })])
    mockedApiFetch.mockResolvedValueOnce(undefined)

    renderPage()
    await screen.findByText('order_promo')

    fireEvent.click(screen.getByLabelText('Delete order_promo'))

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith('/api/v1/campaigns/templates/t1', {
        method: 'DELETE',
      }),
    )
  })
})
