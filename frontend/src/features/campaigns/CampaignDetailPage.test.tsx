import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/shared/api/client'
import type { CampaignDetailOut } from '@/shared/api/types'

import { CampaignDetailPage } from './CampaignDetailPage'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return {
    ...actual,
    apiFetch: vi.fn(),
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

function detail(overrides: Partial<CampaignDetailOut> = {}): CampaignDetailOut {
  return {
    campaign_id: 'c1',
    name: 'Weekend Promo',
    template_id: 't1',
    audience_filter: { kind: 'all' },
    scheduled_at: null,
    status: 'sending',
    created_by: 'staff-1',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    completed_at: null,
    recipient_counts: {
      pending: 3,
      sent: 2,
      failed: 0,
      skipped_opted_out: 1,
      skipped_no_number: 0,
    },
    ...overrides,
  }
}

function renderPage(campaignId = 'c1') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/campaigns/${campaignId}`]}>
        <Routes>
          <Route path="/campaigns/:campaignId" element={<CampaignDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('CampaignDetailPage', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('renders recipient counts and the status badge', async () => {
    mockedApiFetch.mockResolvedValue(detail())

    renderPage()

    expect(await screen.findByText('Weekend Promo')).toBeInTheDocument()
    expect(screen.getByText('Sending')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument() // sent
    expect(screen.getByText('3')).toBeInTheDocument() // pending
    expect(screen.getByText('1')).toBeInTheDocument() // skipped_opted_out
  })

  it('shows a Cancel button for a scheduled or sending campaign, not for draft/completed/failed', async () => {
    mockedApiFetch.mockResolvedValue(detail({ status: 'sending' }))
    renderPage()
    expect(await screen.findByRole('button', { name: /cancel campaign/i })).toBeInTheDocument()
  })

  it('hides the Cancel button once a campaign is completed', async () => {
    mockedApiFetch.mockResolvedValue(detail({ status: 'completed' }))
    renderPage()
    await screen.findByText('Weekend Promo')
    expect(screen.queryByRole('button', { name: /cancel campaign/i })).not.toBeInTheDocument()
  })

  it('clicking Cancel calls the cancel endpoint', async () => {
    mockedApiFetch.mockResolvedValue(detail({ status: 'scheduled' }))

    renderPage()
    const cancelButton = await screen.findByRole('button', { name: /cancel campaign/i })
    fireEvent.click(cancelButton)

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith('/api/v1/campaigns/c1/cancel', {
        method: 'POST',
      }),
    )
  })
})
