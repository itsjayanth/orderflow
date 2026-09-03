import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/shared/api/client'
import type { AppointmentOut } from '@/shared/api/types'

import { AppointmentsPage } from './AppointmentsPage'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return {
    ...actual,
    apiFetch: vi.fn(),
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

// Radix's DropdownMenuTrigger opens on `pointerdown`, not `click`.
function openStatusMenu(trigger: HTMLElement) {
  fireEvent.pointerDown(trigger, { button: 0 })
}

// customer_name deliberately left null -- the "Customer" column then falls
// back to the formatted phone number, so it never collides with the
// separate "Name" column (the name given at booking time, which can
// legitimately differ from the WhatsApp profile name).
const sampleAppointment: AppointmentOut = {
  appointment_id: '11111111-1111-1111-1111-111111111111',
  appointment_number: 7,
  customer_id: '22222222-2222-2222-2222-222222222222',
  customer_number: 3,
  customer_whatsapp_number: '919876543210',
  customer_name: null,
  name: 'Asha Rao',
  email: 'asha@example.com',
  appointment_date: '2026-09-01',
  start_time: '14:30:00',
  end_time: '15:00:00',
  service_id: null,
  staff_id: null,
  created_via: 'browser',
  payment_status: 'not_required',
  notes: null,
  status: 'requested',
  requested_at: '2026-08-26T12:00:00Z',
  confirmed_at: null,
  completed_at: null,
  cancelled_at: null,
  status_events: [],
}

function renderPage(appointments: AppointmentOut[], initialEntries: string[] = ['/appointments']) {
  mockedApiFetch.mockImplementation((path: string) => {
    if (path.startsWith('/api/v1/appointments')) return Promise.resolve(appointments)
    return Promise.reject(new Error(`unexpected apiFetch call: ${path}`))
  })

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>
        <Routes>
          <Route path="/appointments" element={<AppointmentsPage />} />
          <Route path="/appointments/:appointmentId" element={<p>Appointment detail page</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('AppointmentsPage', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('renders appointments with date, time, name, email, and status', async () => {
    renderPage([sampleAppointment])

    expect(await screen.findByText('Asha Rao')).toBeInTheDocument()
    expect(screen.getByText('asha@example.com')).toBeInTheDocument()
    expect(screen.getByText('#0007')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Change status for appointment #0007' }),
    ).toHaveTextContent('Requested')
  })

  it('shows an empty state when there are no appointments', async () => {
    renderPage([])

    expect(await screen.findByText('No appointments yet.')).toBeInTheDocument()
  })

  it('filters appointments by status tab', async () => {
    const confirmedAppointment: AppointmentOut = {
      ...sampleAppointment,
      appointment_id: '99999999-9999-9999-9999-999999999999',
      appointment_number: 9,
      name: 'Ravi Kumar',
      status: 'confirmed',
    }
    renderPage([sampleAppointment, confirmedAppointment])

    await screen.findByText('Asha Rao')
    expect(screen.getByText('Ravi Kumar')).toBeInTheDocument()

    // Radix's Tabs Trigger selects on `mousedown`, not `click`.
    fireEvent.mouseDown(screen.getByRole('tab', { name: /Confirmed/ }), { button: 0 })

    expect(screen.queryByText('Asha Rao')).not.toBeInTheDocument()
    expect(screen.getByText('Ravi Kumar')).toBeInTheDocument()
  })

  it('only offers legal next statuses in the status dropdown', async () => {
    renderPage([sampleAppointment])
    openStatusMenu(
      await screen.findByRole('button', { name: 'Change status for appointment #0007' }),
    )

    const menuItemLabels = screen.getAllByRole('menuitem').map((item) => item.textContent)
    expect(menuItemLabels).toEqual(['Mark Confirmed', 'Mark Cancelled'])
  })

  it('changes status directly from the row via the status dropdown', async () => {
    renderPage([sampleAppointment])
    await screen.findByText('Asha Rao')

    openStatusMenu(screen.getByRole('button', { name: 'Change status for appointment #0007' }))
    fireEvent.click(screen.getByRole('menuitem', { name: 'Mark Confirmed' }))

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        `/api/v1/appointments/${sampleAppointment.appointment_id}/status`,
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ to_status: 'confirmed' }),
        }),
      ),
    )
  })

  it('gates the cancel transition behind a confirmation dialog', async () => {
    renderPage([sampleAppointment])
    await screen.findByText('Asha Rao')

    openStatusMenu(screen.getByRole('button', { name: 'Change status for appointment #0007' }))
    fireEvent.click(screen.getByRole('menuitem', { name: 'Mark Cancelled' }))

    expect(mockedApiFetch).not.toHaveBeenCalledWith(
      expect.stringContaining('/status'),
      expect.anything(),
    )
    expect(await screen.findByRole('alertdialog')).toBeInTheDocument()
    expect(screen.getByText('Cancel appointment #0007?')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Cancel appointment' }))

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        `/api/v1/appointments/${sampleAppointment.appointment_id}/status`,
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ to_status: 'cancelled' }),
        }),
      ),
    )
  })

  it('navigates to the appointment detail page when a row is clicked', async () => {
    renderPage([sampleAppointment])
    await screen.findByText('Asha Rao')

    fireEvent.click(screen.getByText('Asha Rao'))

    expect(await screen.findByText('Appointment detail page')).toBeInTheDocument()
  })

  it('preserves the selected status tab across a List -> Calendar -> List switch', async () => {
    const confirmedAppointment: AppointmentOut = {
      ...sampleAppointment,
      appointment_id: '99999999-9999-9999-9999-999999999999',
      appointment_number: 9,
      name: 'Ravi Kumar',
      status: 'confirmed',
    }
    renderPage([sampleAppointment, confirmedAppointment])
    await screen.findByText('Asha Rao')

    // Radix's Tabs Trigger selects on `mousedown`, not `click`.
    fireEvent.mouseDown(screen.getByRole('tab', { name: /Confirmed/ }), { button: 0 })
    expect(screen.getByRole('tab', { name: /Confirmed/ })).toHaveAttribute('aria-selected', 'true')
    expect(screen.queryByText('Asha Rao')).not.toBeInTheDocument()
    expect(screen.getByText('Ravi Kumar')).toBeInTheDocument()

    fireEvent.mouseDown(screen.getByRole('tab', { name: 'Calendar' }), { button: 0 })
    await waitFor(() =>
      expect(screen.getByRole('tab', { name: 'Calendar' })).toHaveAttribute(
        'aria-selected',
        'true',
      ),
    )

    fireEvent.mouseDown(screen.getByRole('tab', { name: 'List' }), { button: 0 })
    await waitFor(() =>
      expect(screen.getByRole('tab', { name: 'List' })).toHaveAttribute('aria-selected', 'true'),
    )

    expect(screen.getByRole('tab', { name: /Confirmed/ })).toHaveAttribute('aria-selected', 'true')
    await waitFor(() => expect(screen.getByText('Ravi Kumar')).toBeInTheDocument())
    expect(screen.queryByText('Asha Rao')).not.toBeInTheDocument()
  })

  it('reflects the active view and status selections in ARIA state', async () => {
    renderPage([sampleAppointment])
    await screen.findByText('Asha Rao')

    expect(screen.getByRole('tab', { name: 'List' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'Calendar' })).toHaveAttribute('aria-selected', 'false')
    expect(screen.getByRole('tab', { name: /^All/ })).toHaveAttribute('aria-selected', 'true')

    fireEvent.mouseDown(screen.getByRole('tab', { name: /Requested/ }), { button: 0 })
    expect(screen.getByRole('tab', { name: /Requested/ })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: /^All/ })).toHaveAttribute('aria-selected', 'false')

    fireEvent.mouseDown(screen.getByRole('tab', { name: 'Calendar' }), { button: 0 })
    await waitFor(() =>
      expect(screen.getByRole('tab', { name: 'Calendar' })).toHaveAttribute(
        'aria-selected',
        'true',
      ),
    )
    expect(screen.getByRole('tab', { name: 'List' })).toHaveAttribute('aria-selected', 'false')
  })
})
