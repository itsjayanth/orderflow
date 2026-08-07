import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { CustomerOut } from '@/shared/api/types'

import { CustomersPage } from './CustomersPage'

const { apiFetchMock } = vi.hoisted(() => ({ apiFetchMock: vi.fn() }))

vi.mock('@/shared/api/client', () => ({
  apiFetch: apiFetchMock,
}))

const customers: CustomerOut[] = [
  {
    customer_id: 'c1',
    whatsapp_number: '+919876543210',
    display_name: 'Asha',
    first_seen_at: '2026-08-01T10:00:00Z',
    last_order_at: '2026-08-05T12:30:00Z',
  },
  {
    customer_id: 'c2',
    whatsapp_number: '+919876543211',
    display_name: null,
    first_seen_at: '2026-08-02T10:00:00Z',
    last_order_at: null,
  },
]

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <CustomersPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('CustomersPage', () => {
  it('renders customers from the query, falling back to phone number when no name', async () => {
    apiFetchMock.mockResolvedValueOnce(customers)

    renderPage()

    expect(await screen.findByText('Asha')).toBeInTheDocument()
    // Customer c2 has no display_name, so its formatted phone number
    // appears twice: once as the name-column fallback, once in the phone
    // column.
    expect(screen.getAllByText('+91 98765 43211')).toHaveLength(2)
    expect(screen.getAllByText('+91 98765 43210')).toHaveLength(1)
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('renders an empty state when there are no customers', async () => {
    apiFetchMock.mockResolvedValueOnce([])

    renderPage()

    expect(await screen.findByText('No customers yet.')).toBeInTheDocument()
  })
})
