import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/shared/api/client'
import type { OrderDetailOut } from '@/shared/api/types'

import { OrderDetailPage } from './OrderDetailPage'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return {
    ...actual,
    apiFetch: vi.fn(),
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const sampleOrder: OrderDetailOut = {
  order_id: '11111111-1111-1111-1111-111111111111',
  order_number: 42,
  customer_id: '22222222-2222-2222-2222-222222222222',
  customer_number: 3,
  customer_name: 'Asha',
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
  delivery_address: null,
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

    renderPage()

    expect(await screen.findByText('Butter Chicken')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Order #0042' })).toBeInTheDocument()
    expect(screen.getByText('Asha', { exact: false })).toBeInTheDocument()
    // "new" -> only "preparing" and "cancelled" are legal.
    expect(screen.getByRole('button', { name: 'Mark Preparing' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Mark Cancelled' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Mark Ready' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Mark Completed' })).not.toBeInTheDocument()
    // Everything about the order renders as rows of one profile table,
    // the same convention as the Customers tab's expanded detail card.
    expect(screen.getByText('Fulfillment')).toBeInTheDocument()
    expect(screen.getByText('Pickup')).toBeInTheDocument()
    expect(screen.getByText('Placed')).toBeInTheDocument()
    expect(screen.getByText('Total')).toBeInTheDocument()
    // The item's line total and the order total happen to share the same
    // value in this fixture, so both the item row and the Total row show
    // "INR 349.00" -- assert there are (at least) two, rather than picking
    // one and getting an ambiguous-match failure.
    expect(screen.getAllByText('INR 349.00').length).toBeGreaterThanOrEqual(2)
  })

  it('shows the delivery address for a delivery order, and nothing for pickup', async () => {
    mockedApiFetch.mockResolvedValueOnce({
      ...sampleOrder,
      order_type: 'delivery',
      delivery_address: {
        address_id: '55555555-5555-5555-5555-555555555555',
        label: 'Home',
        line1: '12 MG Road',
        line2: null,
        landmark: null,
        city: 'Bengaluru',
        pincode: '560001',
        geo_lat: null,
        geo_long: null,
        is_default: true,
        created_at: '2026-01-01T00:00:00Z',
      },
    })

    renderPage()

    expect(await screen.findByText(/12 MG Road/)).toBeInTheDocument()
    expect(screen.getByText(/Bengaluru 560001/)).toBeInTheDocument()
  })

  it('does not show a delivery address section for a pickup order', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleOrder)

    renderPage()
    await screen.findByText('Butter Chicken')

    expect(screen.queryByText('Delivery address')).not.toBeInTheDocument()
  })

  it('edits and saves the contact number', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleOrder)
    mockedApiFetch.mockResolvedValueOnce({ ...sampleOrder, contact_phone: '+919876500000' })

    renderPage()
    await screen.findByText('Butter Chicken')

    fireEvent.click(screen.getByText(/Contact:/))
    fireEvent.change(screen.getByLabelText('Contact number'), {
      target: { value: '+919876500000' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        `/api/v1/orders/${sampleOrder.order_id}`,
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ contact_phone: '+919876500000' }),
        }),
      ),
    )
  })

  it('edits and saves a note', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleOrder)
    mockedApiFetch.mockResolvedValueOnce({ ...sampleOrder, notes: 'No onion' })

    renderPage()
    await screen.findByText('Butter Chicken')

    fireEvent.click(screen.getByText(/Add a note/))
    fireEvent.change(screen.getByLabelText('Order notes'), { target: { value: 'No onion' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        `/api/v1/orders/${sampleOrder.order_id}`,
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ notes: 'No onion' }),
        }),
      ),
    )
  })

  it('shows a "Mark payment collected" action for a COD order pending collection, and calls the endpoint', async () => {
    const codOrder: OrderDetailOut = {
      ...sampleOrder,
      payment_method: 'cod',
      payment_status: 'cod_pending',
    }
    mockedApiFetch.mockResolvedValueOnce(codOrder)
    mockedApiFetch.mockResolvedValueOnce({ ...codOrder, payment_status: 'cod_collected' })

    renderPage()
    await screen.findByText('Butter Chicken')

    expect(screen.getByText('COD — pending')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Mark payment collected/ }))

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        `/api/v1/orders/${sampleOrder.order_id}/collect-cod-payment`,
        expect.objectContaining({ method: 'POST' }),
      ),
    )
  })

  it('rolls back the optimistic status update when the mutation fails', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleOrder)
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
    expect(screen.getByText('New')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Mark Preparing' }))

    // Optimistic update applies before the mutation settles.
    await waitFor(() => expect(screen.getByText('Preparing')).toBeInTheDocument())

    rejectMutation(new ApiError(409, 'illegal transition'))

    // Then rolls back once the mutation rejects.
    await waitFor(() => expect(screen.getByText('New')).toBeInTheDocument())
    expect(screen.getByText(/failed to update status/i)).toBeInTheDocument()
  })
})
