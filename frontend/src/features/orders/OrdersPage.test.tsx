import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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
  order_number: 7,
  customer_id: '22222222-2222-2222-2222-222222222222',
  customer_number: 3,
  customer_name: 'Asha Rao',
  customer_whatsapp_number: '919876543210',
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

function renderPage(orders: OrderOut[], initialEntries: string[] = ['/orders']) {
  // CreateTestOrderForm also queries the catalog; route each call by path
  // rather than relying on call order, since both fire on mount.
  mockedApiFetch.mockImplementation((path: string) => {
    if (path.startsWith('/api/v1/orders')) return Promise.resolve(orders)
    if (path.startsWith('/api/v1/catalog/items')) return Promise.resolve([])
    return Promise.reject(new Error(`unexpected apiFetch call: ${path}`))
  })

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>
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
    renderPage([sampleOrder])

    expect(await screen.findByText('INR 349.00')).toBeInTheDocument()
    // "New" also matches the filter button, so scope to the table.
    expect(within(screen.getByRole('table')).getByText('New')).toBeInTheDocument()
    expect(screen.getByText('Asha Rao')).toBeInTheDocument()
    expect(screen.getByText('+91 98765 43210')).toBeInTheDocument()
  })

  it('falls back to a formatted phone number when the customer has no display name', async () => {
    renderPage([{ ...sampleOrder, customer_name: null }])

    expect(await screen.findByText('INR 349.00')).toBeInTheDocument()
    expect(screen.getByText('+91 98765 43210')).toBeInTheDocument()
  })

  it('filters by order ID or customer ID via the search input', async () => {
    const otherOrder: OrderOut = {
      ...sampleOrder,
      order_id: '99999999-9999-9999-9999-999999999999',
      order_number: 12,
      customer_number: 9,
      customer_name: 'Ravi Kumar',
    }
    renderPage([sampleOrder, otherOrder])
    await screen.findByText('Asha Rao')
    expect(screen.getByText('Ravi Kumar')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Search orders'), { target: { value: '#0007' } })
    expect(screen.getByText('Asha Rao')).toBeInTheDocument()
    expect(screen.queryByText('Ravi Kumar')).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Search orders'), { target: { value: '#0009' } })
    expect(screen.queryByText('Asha Rao')).not.toBeInTheDocument()
    expect(screen.getByText('Ravi Kumar')).toBeInTheDocument()
  })

  it('shows an empty state when there are no orders', async () => {
    renderPage([])

    expect(await screen.findByText('No orders yet.')).toBeInTheDocument()
  })

  it('re-fetches orders with date-range params when a preset is selected', async () => {
    renderPage([sampleOrder])

    await screen.findByText('INR 349.00')
    mockedApiFetch.mockClear()

    fireEvent.click(screen.getByRole('button', { name: 'Last 30 days' }))

    await waitFor(() => {
      const ordersCall = mockedApiFetch.mock.calls.find(([path]) =>
        (path as string).startsWith('/api/v1/orders?'),
      )
      expect(ordersCall).toBeDefined()
      const [ordersPath] = ordersCall as [string]
      expect(ordersPath).toContain('from_date=')
      expect(ordersPath).toContain('to_date=')
    })
  })

  it('combines the date-range filter with the existing status filter in the URL', async () => {
    // sampleOrder is "new", so under the "preparing" tab the table renders
    // its empty state -- wait on that instead of the order row.
    renderPage([sampleOrder], ['/orders?status=preparing'])

    await screen.findByText('No preparing orders.')
    mockedApiFetch.mockClear()

    fireEvent.click(screen.getByRole('button', { name: 'Today' }))

    await waitFor(() => {
      const ordersCall = mockedApiFetch.mock.calls.find(([path]) =>
        (path as string).startsWith('/api/v1/orders?'),
      )
      expect(ordersCall).toBeDefined()
      const [ordersPath] = ordersCall as [string]
      expect(ordersPath).toContain('from_date=')
      expect(ordersPath).toContain('to_date=')
    })

    // The status tab (URL-driven, filtered client-side) is untouched by
    // picking a date preset -- both filters compose independently.
    expect(screen.getByRole('button', { name: /Preparing/ })).toHaveClass('border-primary')
  })
})
