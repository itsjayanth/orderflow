import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/shared/api/client'
import type { OrderingFlowCheckoutResponse, PublicMenuOut } from '@/shared/api/types'

import { OrderingPage } from './OrderingPage'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return {
    ...actual,
    apiFetch: vi.fn(),
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const merchantId = '11111111-1111-1111-1111-111111111111'

const sampleMenu: PublicMenuOut = {
  business_name: 'Test Kitchen',
  items: [
    {
      menu_item_id: '22222222-2222-2222-2222-222222222222',
      category: 'Mains',
      name: 'Butter Chicken',
      price: '349.00',
    },
  ],
  merchant_whatsapp_number: '+91 90000 00000',
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/order/${merchantId}`]}>
        <Routes>
          <Route path="/order/:merchantId" element={<OrderingPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('OrderingPage', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('renders the menu and business name', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleMenu)

    renderPage()

    expect(await screen.findByText('Test Kitchen')).toBeInTheDocument()
    expect(screen.getByText('Butter Chicken')).toBeInTheDocument()
  })

  it('shows a not-found message for an unknown restaurant', async () => {
    mockedApiFetch.mockRejectedValueOnce(new Error('not found'))

    renderPage()

    expect(await screen.findByText('Restaurant not found.')).toBeInTheDocument()
  })

  it('adds an item to the cart and submits checkout', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleMenu)
    const checkoutResponse: OrderingFlowCheckoutResponse = {
      order_id: '33333333-3333-3333-3333-333333333333',
      payment_status: 'awaiting_payment',
      fulfillment_status: null,
      total: '349.00',
      payment_link_url: 'https://dummy-checkout.orderflow.local/pay/abc',
    }
    mockedApiFetch.mockResolvedValueOnce(checkoutResponse)

    renderPage()
    await screen.findByText('Butter Chicken')

    fireEvent.click(screen.getByRole('button', { name: '+' }))
    expect(await screen.findByText('Total: INR 349.00')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Your WhatsApp number'), {
      target: { value: '9876543210' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Place order' }))

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        `/api/v1/ordering-flow/${merchantId}/checkout`,
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"customer_whatsapp_number":"919876543210"'),
        }),
      ),
    )
    expect(await screen.findByText('Order confirmed!')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Complete payment' })).toHaveAttribute(
      'href',
      checkoutResponse.payment_link_url,
    )
    expect(screen.getByRole('link', { name: 'Return to WhatsApp chat' })).toHaveAttribute(
      'href',
      'https://wa.me/919000000000',
    )
  })
})
