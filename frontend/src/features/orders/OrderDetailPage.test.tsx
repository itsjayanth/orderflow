import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/shared/api/client'
import type { CustomerWithAddressesOut, OrderOut } from '@/shared/api/types'

import { OrderDetailPage } from './OrderDetailPage'

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
  order_number: 42,
  customer_id: '22222222-2222-2222-2222-222222222222',
  customer_name: 'Asha',
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

const sampleCustomer: CustomerWithAddressesOut = {
  customer_id: '22222222-2222-2222-2222-222222222222',
  whatsapp_number: '+919876543210',
  display_name: 'Asha',
  first_seen_at: '2026-01-01T00:00:00Z',
  last_order_at: null,
  addresses: [],
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/orders/${sampleOrder.order_id}`]}>
        <Routes>
          <Route path="/orders/:orderId" element={<OrderDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('OrderDetailPage', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('renders order items, customer, and only legal next-status actions', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleOrder)
    mockedApiFetch.mockResolvedValueOnce(sampleCustomer)

    renderPage()

    expect(await screen.findByText('Butter Chicken')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Order #0042' })).toBeInTheDocument()
    expect(await screen.findByText('Asha', { exact: false })).toBeInTheDocument()
    // "new" -> only "preparing" and "cancelled" are legal.
    expect(screen.getByRole('button', { name: 'Mark Preparing' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Mark Cancelled' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Mark Ready' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Mark Completed' })).not.toBeInTheDocument()
  })

  it('rolls back the optimistic status update when the mutation fails', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleOrder)
    mockedApiFetch.mockResolvedValueOnce(sampleCustomer)
    // A manually-controlled promise so the test can observe the optimistic
    // state before deciding when the mutation fails, instead of racing a
    // real (near-instant) rejection against waitFor's poll interval.
    let rejectMutation!: (err: unknown) => void
    mockedApiFetch.mockReturnValueOnce(
      new Promise((_resolve, reject) => {
        rejectMutation = reject
      }),
    )

    renderPage()
    await screen.findByText('Butter Chicken')
    expect(screen.getByText('Status: New')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Mark Preparing' }))

    // Optimistic update applies before the mutation settles.
    await waitFor(() => expect(screen.getByText('Status: Preparing')).toBeInTheDocument())

    rejectMutation(new ApiError(409, 'illegal transition'))

    // Then rolls back once the mutation rejects.
    await waitFor(() => expect(screen.getByText('Status: New')).toBeInTheDocument())
    expect(screen.getByText(/failed to update status/i)).toBeInTheDocument()
  })
})
