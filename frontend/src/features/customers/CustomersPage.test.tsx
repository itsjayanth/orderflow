import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

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

function findCallInit(mock: typeof apiFetchMock, method: string): RequestInit {
  const call = mock.mock.calls.find(
    ([, init]) => (init as RequestInit | undefined)?.method === method,
  )
  expect(call).toBeDefined()
  return call?.[1] as RequestInit
}

// Radix's Tabs selects on `mousedown` (so keyboard/focus activation and
// pointer activation share one code path), not on `click` -- a plain
// fireEvent.click never fires that event, so the tab never actually
// switches. Same category of quirk as OrdersPage.test.tsx's
// DropdownMenuTrigger opening on `pointerdown`.
function clickTab(trigger: HTMLElement) {
  fireEvent.mouseDown(trigger, { button: 0 })
}

// Expanding a row now mounts CustomerDetailCard, which fires its own
// useCustomer (detail+addresses) and useOrders (order history) GET
// requests alongside the list endpoint -- this routes those by path so
// tests that expand a row don't need to special-case them individually.
function mockCustomerDetailAndOrders(customers: CustomerOut[], path: string): unknown | undefined {
  if (/^\/api\/v1\/customers\/[^/?]+$/.test(path)) {
    const id = path.split('/').pop()
    return { ...customers.find((c) => c.customer_id === id), addresses: [] }
  }
  if (path.startsWith('/api/v1/orders')) return []
  return undefined
}

const customers: CustomerOut[] = [
  {
    customer_id: 'c1',
    customer_number: 1,
    whatsapp_number: '+919876543210',
    display_name: 'Asha',
    default_contact_phone: null,
    email: null,
    first_seen_at: daysAgo(10),
    last_order_at: daysAgo(3),
    is_active: true,
    marketing_opt_out: false,
    marketing_opt_out_at: null,
  },
  {
    customer_id: 'c2',
    customer_number: 2,
    whatsapp_number: '+919876543211',
    display_name: null,
    default_contact_phone: null,
    email: null,
    first_seen_at: daysAgo(9),
    last_order_at: null,
    is_active: true,
    marketing_opt_out: false,
    marketing_opt_out_at: null,
  },
  {
    customer_id: 'c3',
    customer_number: 3,
    whatsapp_number: '+919812340000',
    display_name: 'Ravi Kumar',
    default_contact_phone: null,
    email: null,
    first_seen_at: daysAgo(90),
    last_order_at: daysAgo(54),
    is_active: true,
    marketing_opt_out: false,
    marketing_opt_out_at: null,
  },
]

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
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
  beforeEach(() => {
    apiFetchMock.mockReset()
  })

  it('renders customers from the query, falling back to phone number when no name, with the collapsed row showing only ID + name', async () => {
    apiFetchMock.mockResolvedValueOnce(customers)

    renderPage()

    expect(await screen.findByText('Asha')).toBeInTheDocument()
    expect(screen.getByText('Ravi Kumar')).toBeInTheDocument()
    expect(screen.getByText('#0001')).toBeInTheDocument()
    // Customer c2 has no display_name, so its formatted phone number is
    // shown as the name-column fallback.
    expect(screen.getByText('+91 98765 43211')).toBeInTheDocument()
    // The collapsed row is deliberately just Customer ID + Name -- c1's
    // phone number shouldn't appear anywhere until its row is expanded.
    expect(screen.queryByText('+91 98765 43210')).not.toBeInTheDocument()
  })

  it('expands a row to show the full profile table, and collapses on a second click', async () => {
    apiFetchMock.mockImplementation((path: string) => {
      const detail = mockCustomerDetailAndOrders(customers, path)
      if (detail !== undefined) return Promise.resolve(detail)
      return Promise.resolve(customers)
    })

    renderPage()
    await screen.findByText('Asha')

    expect(screen.queryByText('WhatsApp number')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Expand Asha' }))

    // The profile table surfaces everything the collapsed row hides.
    expect(await screen.findByText('WhatsApp number')).toBeInTheDocument()
    expect(screen.getByText('+91 98765 43210')).toBeInTheDocument()
    expect(screen.getByText('Order history')).toBeInTheDocument()
    expect(await screen.findByText('No orders yet.')).toBeInTheDocument()
    expect(screen.getByText('No saved addresses.')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Collapse Asha' }))

    await waitFor(() => expect(screen.queryByText('WhatsApp number')).not.toBeInTheDocument())
  })

  it('shows an Opted out badge only for a customer who has texted STOP', async () => {
    const optedOutCustomers = customers.map((c) =>
      c.customer_id === 'c3' ? { ...c, marketing_opt_out: true } : c,
    )
    apiFetchMock.mockImplementation((path: string) => {
      const detail = mockCustomerDetailAndOrders(optedOutCustomers, path)
      if (detail !== undefined) return Promise.resolve(detail)
      return Promise.resolve(optedOutCustomers)
    })

    renderPage()
    await screen.findByText('Asha')

    fireEvent.click(screen.getByRole('button', { name: 'Expand Asha' }))
    expect(await screen.findByText('WhatsApp number')).toBeInTheDocument()
    expect(screen.queryByText('Opted out')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Collapse Asha' }))

    fireEvent.click(screen.getByRole('button', { name: 'Expand Ravi Kumar' }))
    expect(await screen.findByText('Opted out')).toBeInTheDocument()
  })

  it('expands a row by clicking anywhere on it, not just the chevron', async () => {
    apiFetchMock.mockImplementation((path: string) => {
      const detail = mockCustomerDetailAndOrders(customers, path)
      if (detail !== undefined) return Promise.resolve(detail)
      return Promise.resolve(customers)
    })

    renderPage()
    await screen.findByText('Asha')

    expect(screen.queryByText('WhatsApp number')).not.toBeInTheDocument()

    fireEvent.click(screen.getByText('Asha'))

    expect(await screen.findByText('WhatsApp number')).toBeInTheDocument()
  })

  it('renders an empty state when there are no customers at all', async () => {
    apiFetchMock.mockResolvedValueOnce([])

    renderPage()

    expect(await screen.findByText('No customers yet. Add one to get started.')).toBeInTheDocument()
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
    // c2 has no name, so its formatted phone number is shown as the
    // name-column fallback.
    expect(screen.getByText('+91 98765 43211')).toBeInTheDocument()
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

  it('filters by the last-7-days timeline tab', async () => {
    apiFetchMock.mockResolvedValueOnce(customers)

    renderPage()
    await screen.findByText('Asha')

    clickTab(screen.getByRole('tab', { name: /Last 7 days/ }))

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
    expect(screen.queryByText('No customers yet. Add one to get started.')).not.toBeInTheDocument()
  })

  it('creates a customer via the Add customer sheet', async () => {
    apiFetchMock.mockImplementation((path: string, init?: RequestInit) => {
      if (!init || init.method === undefined) return Promise.resolve([])
      if (init.method === 'POST') return Promise.resolve({ ...customers[0] })
      return Promise.reject(new Error(`unexpected apiFetch call: ${path}`))
    })

    renderPage()
    await screen.findByText('No customers yet. Add one to get started.')

    fireEvent.click(screen.getByRole('button', { name: 'Add customer' }))
    fireEvent.change(screen.getByLabelText('WhatsApp number'), {
      target: { value: '+919876543210' },
    })
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Asha Rao' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save customer' }))

    await waitFor(() =>
      expect(apiFetchMock).toHaveBeenCalledWith(
        '/api/v1/customers',
        expect.objectContaining({ method: 'POST' }),
      ),
    )
    const init = findCallInit(apiFetchMock, 'POST')
    expect(JSON.parse(init.body as string)).toEqual({
      whatsapp_number: '+919876543210',
      display_name: 'Asha Rao',
    })
  })

  it('edits a customer via the expanded row detail card', async () => {
    apiFetchMock.mockImplementation((path: string, init?: RequestInit) => {
      if (init?.method === 'PATCH')
        return Promise.resolve({ ...customers[0], display_name: 'Asha K' })
      if (!init || init.method === undefined) {
        const detail = mockCustomerDetailAndOrders(customers, path)
        if (detail !== undefined) return Promise.resolve(detail)
        return Promise.resolve(customers)
      }
      return Promise.reject(new Error(`unexpected apiFetch call: ${path}`))
    })

    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Expand Asha' }))

    fireEvent.click(await screen.findByRole('button', { name: 'Edit Asha' }))
    const nameInput = await screen.findByLabelText('Name')
    fireEvent.change(nameInput, { target: { value: 'Asha K' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    await waitFor(() =>
      expect(apiFetchMock).toHaveBeenCalledWith(
        '/api/v1/customers/c1',
        expect.objectContaining({ method: 'PATCH' }),
      ),
    )
    const init = findCallInit(apiFetchMock, 'PATCH')
    expect(JSON.parse(init.body as string)).toEqual({ display_name: 'Asha K' })
  })

  it('gates removing a customer behind a confirmation dialog, then removes on confirm', async () => {
    apiFetchMock.mockImplementation((path: string, init?: RequestInit) => {
      if (init?.method === 'PATCH') return Promise.resolve({ ...customers[0], is_active: false })
      if (!init || init.method === undefined) {
        const detail = mockCustomerDetailAndOrders(customers, path)
        if (detail !== undefined) return Promise.resolve(detail)
        return Promise.resolve(customers)
      }
      return Promise.reject(new Error(`unexpected apiFetch call: ${path}`))
    })

    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Expand Asha' }))

    fireEvent.click(await screen.findByRole('button', { name: 'Remove Asha' }))

    // The mutation must not fire yet -- a confirmation dialog opens instead.
    expect(apiFetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/customers/c1'),
      expect.objectContaining({ method: 'PATCH' }),
    )
    expect(await screen.findByRole('alertdialog')).toBeInTheDocument()
    expect(screen.getByText('Remove Asha?')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Remove customer' }))

    await waitFor(() =>
      expect(apiFetchMock).toHaveBeenCalledWith(
        '/api/v1/customers/c1',
        expect.objectContaining({ method: 'PATCH' }),
      ),
    )
    const init = findCallInit(apiFetchMock, 'PATCH')
    expect(JSON.parse(init.body as string)).toEqual({ is_active: false })
  })

  it('does not remove the customer when the confirmation dialog is dismissed', async () => {
    apiFetchMock.mockImplementation((path: string) => {
      const detail = mockCustomerDetailAndOrders(customers, path)
      if (detail !== undefined) return Promise.resolve(detail)
      return Promise.resolve(customers)
    })

    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Expand Asha' }))

    fireEvent.click(await screen.findByRole('button', { name: 'Remove Asha' }))
    expect(await screen.findByRole('alertdialog')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Keep customer' }))

    await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument())
    expect(apiFetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/customers/c1'),
      expect.objectContaining({ method: 'PATCH' }),
    )
  })

  it('toggling "Show removed" requests the include_inactive list', async () => {
    apiFetchMock.mockResolvedValue([])

    renderPage()
    await screen.findByText('No customers yet. Add one to get started.')

    fireEvent.click(screen.getByRole('button', { name: 'Show removed' }))

    await waitFor(() =>
      expect(apiFetchMock).toHaveBeenCalledWith('/api/v1/customers?include_inactive=true'),
    )
  })

  it('selects customers via checkboxes and bulk-removes the active ones behind a confirmation', async () => {
    apiFetchMock.mockImplementation((path: string, init?: RequestInit) => {
      if (!init || init.method === undefined) return Promise.resolve(customers)
      if (init.method === 'PATCH') return Promise.resolve({ ...customers[0], is_active: false })
      return Promise.reject(new Error(`unexpected apiFetch call: ${path}`))
    })

    renderPage()
    await screen.findByText('Asha')

    expect(screen.queryByText('2 selected')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('checkbox', { name: 'Select Asha' }))
    fireEvent.click(screen.getByRole('checkbox', { name: 'Select Ravi Kumar' }))
    expect(screen.getByText('2 selected')).toBeInTheDocument()

    // Both selected customers are active -- only "Remove selected" shows,
    // not "Restore selected".
    expect(screen.queryByRole('button', { name: 'Restore selected' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Remove selected' }))

    expect(await screen.findByRole('alertdialog')).toBeInTheDocument()
    expect(screen.getByText('Remove 2 customers?')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Remove customers' }))

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith(
        '/api/v1/customers/c1',
        expect.objectContaining({ method: 'PATCH' }),
      )
      expect(apiFetchMock).toHaveBeenCalledWith(
        '/api/v1/customers/c3',
        expect.objectContaining({ method: 'PATCH' }),
      )
    })

    // Selection clears once the bulk action fires.
    expect(screen.queryByText('2 selected')).not.toBeInTheDocument()
  })

  it('shows a bulk "Restore selected" action for a mixed active/inactive selection, firing immediately with no confirmation', async () => {
    const mixedCustomers = [customers[0], { ...customers[1], is_active: false }]
    apiFetchMock.mockImplementation((path: string, init?: RequestInit) => {
      if (!init || init.method === undefined) return Promise.resolve(mixedCustomers)
      if (init.method === 'PATCH') return Promise.resolve({ ...mixedCustomers[1], is_active: true })
      return Promise.reject(new Error(`unexpected apiFetch call: ${path}`))
    })

    renderPage()
    // c2 has no display_name, so it renders under its formatted phone number.
    await screen.findByText('Asha')

    fireEvent.click(screen.getByRole('checkbox', { name: 'Select Asha' }))
    fireEvent.click(screen.getByRole('checkbox', { name: 'Select +91 98765 43211' }))

    // Mixed selection -- both bulk actions are offered.
    expect(screen.getByRole('button', { name: 'Restore selected' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Remove selected' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Restore selected' }))

    // Restore is non-destructive -- no confirmation dialog, fires right away.
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    await waitFor(() =>
      expect(apiFetchMock).toHaveBeenCalledWith(
        '/api/v1/customers/c2',
        expect.objectContaining({ method: 'PATCH', body: JSON.stringify({ is_active: true }) }),
      ),
    )
  })

  it('shows pagination controls only once the filtered set exceeds one page', async () => {
    const manyCustomers: CustomerOut[] = Array.from({ length: 20 }, (_, i) => ({
      ...customers[0],
      customer_id: `customer-${i}`,
      customer_number: i + 1,
      display_name: `Customer ${i}`,
    }))
    apiFetchMock.mockResolvedValueOnce(manyCustomers)

    renderPage()

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
