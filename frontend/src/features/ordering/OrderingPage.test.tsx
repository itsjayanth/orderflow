import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/shared/api/client'
import type {
  OrderingFlowCheckoutResponse,
  OrderingFlowCustomerLookupOut,
  PublicMenuOut,
} from '@/shared/api/types'

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
      image_url: 'https://example.com/butter-chicken.jpg',
    },
  ],
  merchant_whatsapp_number: '+91 90000 00000',
}

const multiCategoryMenu: PublicMenuOut = {
  business_name: 'Test Kitchen',
  items: [
    {
      menu_item_id: '22222222-2222-2222-2222-222222222222',
      category: 'Mains',
      name: 'Butter Chicken',
      price: '349.00',
      image_url: null,
    },
    {
      menu_item_id: '44444444-4444-4444-4444-444444444444',
      category: 'Desserts',
      name: 'Gulab Jamun',
      price: '99.00',
      image_url: null,
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

  it('shows the item photo when image_url is set', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleMenu)

    renderPage()
    await screen.findByText('Butter Chicken')

    expect(screen.getByRole('img', { name: 'Butter Chicken' })).toHaveAttribute(
      'src',
      'https://example.com/butter-chicken.jpg',
    )
  })

  it('falls back to an initial-letter tile when image_url is not set', async () => {
    mockedApiFetch.mockResolvedValueOnce(multiCategoryMenu)

    renderPage()
    await screen.findByText('Butter Chicken')

    // Neither item in multiCategoryMenu has image_url set -- falls back to
    // an initial-letter tile rather than a broken <img>.
    expect(screen.queryByRole('img', { name: 'Butter Chicken' })).not.toBeInTheDocument()
    expect(screen.queryByRole('img', { name: 'Gulab Jamun' })).not.toBeInTheDocument()
  })

  it('shows a not-found message for an unknown restaurant', async () => {
    mockedApiFetch.mockRejectedValueOnce(new Error('not found'))

    renderPage()

    expect(await screen.findByText('Restaurant not found.')).toBeInTheDocument()
  })

  it('groups menu items into category sections with headers', async () => {
    mockedApiFetch.mockResolvedValueOnce(multiCategoryMenu)

    renderPage()

    expect(await screen.findByText('Butter Chicken')).toBeInTheDocument()
    expect(screen.getByText('Gulab Jamun')).toBeInTheDocument()
    // Section headers, plus quick-nav pills, both render the category name.
    expect(screen.getAllByText('Mains').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Desserts').length).toBeGreaterThan(0)
  })

  it('adds an item to the cart and submits checkout with the required name and pickup order type', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleMenu)
    const checkoutResponse: OrderingFlowCheckoutResponse = {
      order_id: '33333333-3333-3333-3333-333333333333',
      order_number: 12,
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
    fireEvent.change(screen.getByLabelText('Your name'), {
      target: { value: 'Asha' },
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
    const checkoutCall = mockedApiFetch.mock.calls.find(
      ([path]) => path === `/api/v1/ordering-flow/${merchantId}/checkout`,
    )
    const requestBody = JSON.parse((checkoutCall?.[1]?.body as string) ?? '{}')
    expect(requestBody.customer_display_name).toBe('Asha')
    expect(requestBody.order_type).toBe('pickup')
    expect(requestBody.delivery_address).toBeUndefined()

    expect(await screen.findByText('Order #0012 confirmed!')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Complete payment' })).toHaveAttribute(
      'href',
      checkoutResponse.payment_link_url,
    )
    expect(screen.getByRole('link', { name: 'Return to WhatsApp chat' })).toHaveAttribute(
      'href',
      'https://wa.me/919000000000',
    )
  })

  it('shows a validation error when the name is left blank', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleMenu)

    renderPage()
    await screen.findByText('Butter Chicken')

    fireEvent.click(screen.getByRole('button', { name: '+' }))
    await screen.findByText('Total: INR 349.00')

    fireEvent.change(screen.getByLabelText('Your WhatsApp number'), {
      target: { value: '9876543210' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Place order' }))

    expect(await screen.findByText('Please enter your name')).toBeInTheDocument()
    expect(mockedApiFetch).not.toHaveBeenCalledWith(
      `/api/v1/ordering-flow/${merchantId}/checkout`,
      expect.anything(),
    )
  })

  it('requires and submits a delivery address when delivery is selected', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleMenu)
    const checkoutResponse: OrderingFlowCheckoutResponse = {
      order_id: '33333333-3333-3333-3333-333333333333',
      order_number: 7,
      payment_status: 'cod_pending',
      fulfillment_status: 'new',
      total: '349.00',
      payment_link_url: null,
    }
    mockedApiFetch.mockResolvedValueOnce(checkoutResponse)

    renderPage()
    await screen.findByText('Butter Chicken')

    fireEvent.click(screen.getByRole('button', { name: '+' }))
    await screen.findByText('Total: INR 349.00')

    fireEvent.change(screen.getByLabelText('Your WhatsApp number'), {
      target: { value: '9876543210' },
    })
    fireEvent.change(screen.getByLabelText('Your name'), { target: { value: 'Asha' } })
    fireEvent.click(screen.getByRole('button', { name: 'Delivery' }))

    // Submitting without address fields surfaces validation errors instead
    // of silently falling back to pickup.
    fireEvent.click(screen.getByRole('button', { name: 'Place order' }))
    expect(await screen.findAllByText('Required for delivery')).toHaveLength(3)
    expect(mockedApiFetch).not.toHaveBeenCalledWith(
      `/api/v1/ordering-flow/${merchantId}/checkout`,
      expect.anything(),
    )

    fireEvent.change(screen.getByLabelText('Address line 1'), {
      target: { value: '221B Baker Street' },
    })
    fireEvent.change(screen.getByLabelText('City'), { target: { value: 'Bengaluru' } })
    fireEvent.change(screen.getByLabelText('Pincode'), { target: { value: '560001' } })
    fireEvent.click(screen.getByRole('button', { name: 'Place order' }))

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        `/api/v1/ordering-flow/${merchantId}/checkout`,
        expect.anything(),
      ),
    )
    const checkoutCall = mockedApiFetch.mock.calls.find(
      ([path]) => path === `/api/v1/ordering-flow/${merchantId}/checkout`,
    )
    const requestBody = JSON.parse((checkoutCall?.[1]?.body as string) ?? '{}')
    expect(requestBody.order_type).toBe('delivery')
    expect(requestBody.delivery_address).toEqual({
      line1: '221B Baker Street',
      line2: undefined,
      landmark: undefined,
      city: 'Bengaluru',
      pincode: '560001',
    })
  })

  it('prefills name and address for a returning customer once the phone number is entered', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleMenu)
    const lookupResponse: OrderingFlowCustomerLookupOut = {
      display_name: 'Priya',
      address: {
        line1: '12 MG Road',
        line2: null,
        landmark: 'Opposite the mall',
        city: 'Bengaluru',
        pincode: '560025',
      },
    }
    mockedApiFetch.mockResolvedValueOnce(lookupResponse)

    renderPage()
    await screen.findByText('Butter Chicken')

    fireEvent.click(screen.getByRole('button', { name: '+' }))
    await screen.findByText('Total: INR 349.00')

    const phoneInput = screen.getByLabelText('Your WhatsApp number')
    fireEvent.change(phoneInput, { target: { value: '9876543210' } })
    fireEvent.blur(phoneInput)

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        `/api/v1/ordering-flow/${merchantId}/customer-lookup?whatsapp_number=919876543210`,
      ),
    )

    expect(await screen.findByDisplayValue('Priya')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Delivery' }))
    expect(await screen.findByDisplayValue('12 MG Road')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Opposite the mall')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Bengaluru')).toBeInTheDocument()
    expect(screen.getByDisplayValue('560025')).toBeInTheDocument()
  })

  it('does not error the page when customer-lookup finds no existing customer', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleMenu)
    mockedApiFetch.mockRejectedValueOnce(new Error('not found'))

    renderPage()
    await screen.findByText('Butter Chicken')

    fireEvent.click(screen.getByRole('button', { name: '+' }))
    await screen.findByText('Total: INR 349.00')

    const phoneInput = screen.getByLabelText('Your WhatsApp number')
    fireEvent.change(phoneInput, { target: { value: '9876543210' } })
    fireEvent.blur(phoneInput)

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        `/api/v1/ordering-flow/${merchantId}/customer-lookup?whatsapp_number=919876543210`,
      ),
    )

    expect(screen.getByLabelText('Your name')).toHaveValue('')
    expect(screen.queryByText('Restaurant not found.')).not.toBeInTheDocument()
  })
})
