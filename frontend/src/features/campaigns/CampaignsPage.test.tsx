import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/shared/api/client'
import type { CampaignOut } from '@/shared/api/types'

import { CampaignsPage } from './CampaignsPage'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return {
    ...actual,
    apiFetch: vi.fn(),
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

function campaign(overrides: Partial<CampaignOut> = {}): CampaignOut {
  return {
    campaign_id: 'c1',
    name: 'Weekend Promo',
    template_id: 't1',
    audience_filter: { kind: 'all' },
    scheduled_at: null,
    status: 'draft',
    created_by: 'staff-1',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    completed_at: null,
    ...overrides,
  }
}

// CampaignForm (always mounted alongside the table, dialog open or not)
// fires its own useTemplates() GET on mount -- route by path so tests
// don't need to special-case that extra request.
function mockApiByPath(campaigns: CampaignOut[]) {
  mockedApiFetch.mockImplementation((path: string) => {
    if (path.startsWith('/api/v1/campaigns/templates')) return Promise.resolve([])
    if (path === '/api/v1/campaigns') return Promise.resolve(campaigns)
    return Promise.resolve(undefined)
  })
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <CampaignsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('CampaignsPage', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('shows an empty state when there are no campaigns yet', async () => {
    mockApiByPath([])

    renderPage()

    expect(await screen.findByText(/No campaigns yet/)).toBeInTheDocument()
  })

  it('renders each campaign with its name, audience label, and status badge', async () => {
    mockApiByPath([
      campaign({ campaign_id: 'c1', name: 'All customers promo', status: 'draft' }),
      campaign({
        campaign_id: 'c2',
        name: 'Recent orderers',
        status: 'sending',
        audience_filter: { kind: 'ordered_within_days', days: 7 },
      }),
      campaign({
        campaign_id: 'c3',
        name: 'Win-back',
        status: 'completed',
        audience_filter: { kind: 'no_order_within_days', days: 30 },
      }),
    ])

    renderPage()

    expect(await screen.findByText('All customers promo')).toBeInTheDocument()
    expect(screen.getByText('All customers')).toBeInTheDocument()
    expect(screen.getByText('Draft')).toBeInTheDocument()

    expect(screen.getByText('Recent orderers')).toBeInTheDocument()
    expect(screen.getByText('Ordered in last 7d')).toBeInTheDocument()
    expect(screen.getByText('Sending')).toBeInTheDocument()

    expect(screen.getByText('Win-back')).toBeInTheDocument()
    expect(screen.getByText('No order in last 30d')).toBeInTheDocument()
    expect(screen.getByText('Completed')).toBeInTheDocument()
  })

  it('links each campaign name to its detail page', async () => {
    mockApiByPath([campaign({ campaign_id: 'c1', name: 'Weekend Promo' })])

    renderPage()

    const link = await screen.findByRole('link', { name: 'Weekend Promo' })
    expect(link).toHaveAttribute('href', '/campaigns/c1')
  })
})
