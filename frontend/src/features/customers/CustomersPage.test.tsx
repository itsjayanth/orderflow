import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { CustomerOut } from '@/shared/api/types'

import { CustomersPage } from './CustomersPage'

const { apiFetchMock } = vi.hoisted(() => ({ apiFetchMock: vi.fn() }))

vi.mock('@/shared/api/client', () => ({
  apiFetch: apiFetchMock,
}))

// Offsets from "now" (real time, not faked) so the timeline filter's
// "last N days" windows are exercised without needing to fake system time,
// which conflicts with React Query's/RTL's own timers.
function daysAgo(days: number): string {
  return new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString()
}

const customers: CustomerOut[] = [
  {
    customer_id: 'c1',
    customer_number: 1,
    whatsapp_number: '+919876543210',
    display_name: 'Asha',
    first_seen_at: daysAgo(10),
    last_order_at: daysAgo(3),
  },
  {
    customer_id: 'c2',
    customer_number: 2,
    whatsapp_number: '+919876543211',
    display_name: null,
    first_seen_at: daysAgo(9),
    last_order_at: null,
  },
  {
    customer_id: 'c3',
    customer_number: 3,
    whatsapp_number: '+919812340000',
    display_name: 'Ravi Kumar',
    first_seen_at: daysAgo(90),
    last_order_at: daysAgo(54),
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

  it('renders an empty state when there are no customers at all', async () => {
    apiFetchMock.mockResolvedValueOnce([])

    renderPage()

    expect(await screen.findByText('No customers yet.')).toBeInTheDocument()
  })

  it('filters by name via the search input', async () => {
    apiFetchMock.mockResolvedValueOnce(customers)

    renderPage()
    await screen.findByText('Asha')

    fireEvent.change(screen.getByLabelText('Search customers'), { target: { value: 'ravi' } })

    expect(screen.getByText('Ravi Kumar')).toBeInTheDocument()
    expect(screen.queryByText('Asha')).not.toBeInTheDocument()
  })

  it('filters by phone digits via the search input, ignoring formatting', async () => {
    apiFetchMock.mockResolvedValueOnce(customers)

    renderPage()
    await screen.findByText('Asha')

    fireEvent.change(screen.getByLabelText('Search customers'), {
      target: { value: '+91 98765 432' },
    })

    expect(screen.getByText('Asha')).toBeInTheDocument()
    // c2 has no name, so its formatted phone number appears twice: once as
    // the name-column fallback, once in the phone column.
    expect(screen.getAllByText('+91 98765 43211')).toHaveLength(2)
    expect(screen.queryByText('Ravi Kumar')).not.toBeInTheDocument()
  })

  it('filters by customer ID via the search input', async () => {
    apiFetchMock.mockResolvedValueOnce(customers)

    renderPage()
    await screen.findByText('Asha')

    fireEvent.change(screen.getByLabelText('Search customers'), { target: { value: '#0003' } })

    expect(screen.getByText('Ravi Kumar')).toBeInTheDocument()
    expect(screen.queryByText('Asha')).not.toBeInTheDocument()
  })

  it('filters by the last-7-days timeline preset', async () => {
    apiFetchMock.mockResolvedValueOnce(customers)

    renderPage()
    await screen.findByText('Asha')

    fireEvent.click(screen.getByRole('button', { name: 'Last 7 days' }))

    expect(screen.getByText('Asha')).toBeInTheDocument()
    expect(screen.queryByText('Ravi Kumar')).not.toBeInTheDocument()
    // c2 has never ordered, so it's excluded from any timeline window.
    expect(screen.queryByText('+91 98765 43211')).not.toBeInTheDocument()
  })

  it('shows a distinct empty state when a search/filter yields no matches', async () => {
    apiFetchMock.mockResolvedValueOnce(customers)

    renderPage()
    await screen.findByText('Asha')

    fireEvent.change(screen.getByLabelText('Search customers'), {
      target: { value: 'nonexistent' },
    })

    expect(await screen.findByText('No customers match your search or filter.')).toBeInTheDocument()
    expect(screen.queryByText('No customers yet.')).not.toBeInTheDocument()
  })
})
