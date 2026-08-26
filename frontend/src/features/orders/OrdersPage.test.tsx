import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/shared/api/client'
import type { OrderDetailOut, OrderOut } from '@/shared/api/types'

import { OrdersPage } from './OrdersPage'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return {
    ...actual,
    apiFetch: vi.fn(),
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

// Radix's DropdownMenuTrigger opens on `pointerdown`, not `click` -- a
// plain fireEvent.click never fires that event, so the menu stays closed.
function openStatusMenu(trigger: HTMLElement) {
  fireEvent.pointerDown(trigger, { button: 0 })
}

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
  contact_phone: null,
  notes: null,
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
      item_id: '44444444-4444-4444-4444-444444444444',
      name_snapshot: 'Butter Chicken',
      price_snapshot: '349.00',
      quantity: 1,
      line_total: '349.00',
    },
  ],
}

const sampleOrderDetail: OrderDetailOut = { ...sampleOrder, delivery_address: null }

function renderPage(orders: OrderOut[], initialEntries: string[] = ['/orders']) {
  // CreateTestOrderForm also queries the catalog, and expanding a row fetches
  // that single order's detail -- route each call by path/method rather than
  // relying on call order, since several of these can fire close together.
  mockedApiFetch.mockImplementation((path: string) => {
    if (/^\/api\/v1\/orders\/[^/]+$/.test(path)) return Promise.resolve(sampleOrderDetail)
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

  it('renders orders with a lean, monitoring-focused set of columns', async () => {
    renderPage([sampleOrder])

    expect(await screen.findByText('Asha Rao')).toBeInTheDocument()
    const table = screen.getByRole('table')
    // Item count is shown; price/total and customer id/phone are not.
    expect(within(table).getByText('1')).toBeInTheDocument()
    expect(within(table).queryByText('INR 349.00')).not.toBeInTheDocument()
    expect(within(table).queryByText('#0003')).not.toBeInTheDocument()
    expect(within(table).queryByText('+91 98765 43210')).not.toBeInTheDocument()
    // Status is the inline, actionable dropdown -- not its own "Action" column.
    expect(screen.getByRole('button', { name: 'Change status for order #0007' })).toHaveTextContent(
      'New',
    )
    expect(screen.queryByText('Action')).not.toBeInTheDocument()
  })

  it('falls back to a formatted phone number when the customer has no display name', async () => {
    renderPage([{ ...sampleOrder, customer_name: null }])

    expect(await screen.findByText('+91 98765 43210')).toBeInTheDocument()
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

  it('changes status directly from the collapsed row via the status dropdown, with no expansion needed', async () => {
    renderPage([sampleOrder])
    await screen.findByText('Asha Rao')

    // Never expanded -- the detail card's content must not be present.
    expect(screen.queryByText('Butter Chicken')).not.toBeInTheDocument()

    openStatusMenu(screen.getByRole('button', { name: 'Change status for order #0007' }))
    fireEvent.click(screen.getByRole('menuitem', { name: 'Mark Preparing' }))

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        `/api/v1/orders/${sampleOrder.order_id}/fulfillment-status`,
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ to_status: 'preparing' }),
        }),
      ),
    )
  })

  it('only offers legal next statuses in the status dropdown', async () => {
    renderPage([sampleOrder])
    openStatusMenu(await screen.findByRole('button', { name: 'Change status for order #0007' }))

    // "new" -> only "preparing" and "cancelled" are legal next statuses
    // (current status is shown in the label, not as a selectable item).
    const menuItemLabels = screen.getAllByRole('menuitem').map((item) => item.textContent)
    expect(menuItemLabels).toEqual(['Mark Preparing', 'Mark Cancelled'])
  })

  it('expands a row via the chevron button to show the full order detail card, and collapses on a second click', async () => {
    renderPage([sampleOrder])
    const expandButton = await screen.findByRole('button', { name: 'Expand order #0007' })

    expect(screen.queryByText('Butter Chicken')).not.toBeInTheDocument()

    fireEvent.click(expandButton)

    expect(await screen.findByText('Butter Chicken')).toBeInTheDocument()
    // The expanded card no longer shows its own "Mark {status}" buttons --
    // that action lives in the row-level status dropdown now.
    expect(screen.queryByRole('button', { name: 'Mark Preparing' })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Collapse order #0007' }))

    await waitFor(() => expect(screen.queryByText('Butter Chicken')).not.toBeInTheDocument())
  })

  it('expands a row by clicking anywhere on it, not just the chevron', async () => {
    renderPage([sampleOrder])
    await screen.findByText('Asha Rao')

    expect(screen.queryByText('Butter Chicken')).not.toBeInTheDocument()

    fireEvent.click(screen.getByText('Asha Rao'))

    expect(await screen.findByText('Butter Chicken')).toBeInTheDocument()
  })

  it('advances an order to its next status from the row-level status dropdown while a row is expanded', async () => {
    renderPage([sampleOrder])
    fireEvent.click(await screen.findByRole('button', { name: 'Expand order #0007' }))
    await screen.findByText('Butter Chicken')

    openStatusMenu(screen.getByRole('button', { name: 'Change status for order #0007' }))
    fireEvent.click(screen.getByRole('menuitem', { name: 'Mark Preparing' }))

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        `/api/v1/orders/${sampleOrder.order_id}/fulfillment-status`,
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ to_status: 'preparing' }),
        }),
      ),
    )
  })

  it('shows an empty state when there are no orders', async () => {
    renderPage([])

    expect(await screen.findByText('No orders yet.')).toBeInTheDocument()
  })

  it('re-fetches orders with date-range params when a preset is selected', async () => {
    renderPage([sampleOrder])

    await screen.findByText('Asha Rao')
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
    expect(screen.getByRole('tab', { name: /Preparing/ })).toHaveAttribute('aria-selected', 'true')
  })

  it('selects orders via checkboxes and shows a bulk-action bar with the shared legal next status', async () => {
    const otherOrder: OrderOut = {
      ...sampleOrder,
      order_id: '99999999-9999-9999-9999-999999999999',
      order_number: 12,
      customer_number: 9,
      customer_name: 'Ravi Kumar',
    }
    renderPage([sampleOrder, otherOrder])
    await screen.findByText('Asha Rao')

    expect(screen.queryByText('2 selected')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('checkbox', { name: 'Select order #0007' }))
    expect(screen.getByText('1 selected')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('checkbox', { name: 'Select order #0012' }))
    expect(screen.getByText('2 selected')).toBeInTheDocument()

    // Both orders are "new" -> shared legal next statuses are Preparing/Cancelled.
    const markPreparing = screen.getByRole('button', { name: 'Mark Preparing' })
    fireEvent.click(markPreparing)

    await waitFor(() => {
      expect(mockedApiFetch).toHaveBeenCalledWith(
        `/api/v1/orders/${sampleOrder.order_id}/fulfillment-status`,
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ to_status: 'preparing' }),
        }),
      )
      expect(mockedApiFetch).toHaveBeenCalledWith(
        `/api/v1/orders/${otherOrder.order_id}/fulfillment-status`,
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ to_status: 'preparing' }),
        }),
      )
    })

    // Selection clears once the bulk action fires.
    expect(screen.queryByText('2 selected')).not.toBeInTheDocument()
  })

  it('gates the cancel transition behind a confirmation dialog, both single-row and bulk', async () => {
    renderPage([sampleOrder])
    await screen.findByText('Asha Rao')

    openStatusMenu(screen.getByRole('button', { name: 'Change status for order #0007' }))
    fireEvent.click(screen.getByRole('menuitem', { name: 'Mark Cancelled' }))

    // The mutation must not fire yet -- a confirmation dialog opens instead.
    expect(mockedApiFetch).not.toHaveBeenCalledWith(
      expect.stringContaining('/fulfillment-status'),
      expect.anything(),
    )
    expect(await screen.findByRole('alertdialog')).toBeInTheDocument()
    expect(screen.getByText('Cancel order #0007?')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Cancel order' }))

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        `/api/v1/orders/${sampleOrder.order_id}/fulfillment-status`,
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ to_status: 'cancelled' }),
        }),
      ),
    )
  })

  it('shows pagination controls only once the filtered set exceeds one page', async () => {
    const manyOrders: OrderOut[] = Array.from({ length: 20 }, (_, i) => ({
      ...sampleOrder,
      order_id: `order-${i}`,
      order_number: i + 1,
      customer_number: i + 1,
      customer_name: `Customer ${i}`,
    }))
    renderPage(manyOrders)

    await screen.findByText('Customer 0')
    expect(screen.getByText('Page 1 of 2')).toBeInTheDocument()
    // Only the first page (15 rows) renders.
    expect(screen.queryByText('Customer 14')).toBeInTheDocument()
    expect(screen.queryByText('Customer 15')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Go to next page' }))

    expect(await screen.findByText('Customer 15')).toBeInTheDocument()
    expect(screen.queryByText('Customer 0')).not.toBeInTheDocument()
  })
})
