import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/shared/api/client'
import type { OrderOut } from '@/shared/api/types'

import { OrdersPage } from './OrdersPage'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return {
    ...actual,
    apiFetch: vi.fn(),
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const sampleOrder: OrderOut = {
  order_id: '11111111-1111-1111-1111-111111111111',
  customer_id: '22222222-2222-2222-2222-222222222222',
  order_type: 'pickup',
  payment_method: 'online',
  payment_status: 'paid',
  fulfillment_status: 'new',
  subtotal: '349.00',
  total: '349.00',
  currency: 'INR',
  placed_at: '2026-01-01T12:00:00Z',
  paid_at: '2026-01-01T12:00:00Z',
  ready_at: null,
  completed_at: null,
  items: [
    {
      order_item_id: '33333333-3333-3333-3333-333333333333',
      menu_item_id: '44444444-4444-4444-4444-444444444444',
      name_snapshot: 'Butter Chicken',
      price_snapshot: '349.00',
      quantity: 1,
      line_total: '349.00',
    },
  ],
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <OrdersPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('OrdersPage', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('renders orders from the list query', async () => {
    mockedApiFetch.mockResolvedValueOnce([sampleOrder])

    renderPage()

    expect(await screen.findByText('INR 349.00')).toBeInTheDocument()
    // "New" also matches the filter button, so scope to the table.
    expect(within(screen.getByRole('table')).getByText('New')).toBeInTheDocument()
  })

  it('shows an empty state when there are no orders', async () => {
    mockedApiFetch.mockResolvedValueOnce([])

    renderPage()

    expect(await screen.findByText('No orders yet.')).toBeInTheDocument()
  })
})
