import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/shared/api/client'
import type { AppointmentOut } from '@/shared/api/types'

import { AppointmentDetailPage } from './AppointmentDetailPage'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return {
    ...actual,
    apiFetch: vi.fn(),
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const sampleAppointment: AppointmentOut = {
  appointment_id: '11111111-1111-1111-1111-111111111111',
  appointment_number: 42,
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

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/appointments/${sampleAppointment.appointment_id}`]}>
        <Routes>
          <Route path="/appointments/:appointmentId" element={<AppointmentDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('AppointmentDetailPage', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('renders appointment fields and only legal next-status actions', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleAppointment)

    renderPage()

    expect(await screen.findByRole('heading', { name: 'Appointment #0042' })).toBeInTheDocument()
    expect(screen.getByText('Asha Rao')).toBeInTheDocument()
    expect(screen.getByText('asha@example.com')).toBeInTheDocument()
    // "requested" -> only "confirmed" and "cancelled" are legal.
    expect(screen.getByRole('button', { name: 'Mark Confirmed' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Mark Cancelled' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Mark Completed' })).not.toBeInTheDocument()
  })

  it('edits and saves a note', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleAppointment)
    mockedApiFetch.mockResolvedValueOnce({ ...sampleAppointment, notes: 'Prefers a window seat' })

    renderPage()
    await screen.findByText('Asha Rao')

    fireEvent.click(screen.getByText(/Add a note/))
    fireEvent.change(screen.getByLabelText('Appointment notes'), {
      target: { value: 'Prefers a window seat' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        `/api/v1/appointments/${sampleAppointment.appointment_id}`,
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ notes: 'Prefers a window seat' }),
        }),
      ),
    )
  })

  it('advances an appointment to its next status', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleAppointment)
    mockedApiFetch.mockResolvedValueOnce({ ...sampleAppointment, status: 'confirmed' })

    renderPage()
    await screen.findByText('Asha Rao')

    fireEvent.click(screen.getByRole('button', { name: 'Mark Confirmed' }))

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

  it('shows no further actions once an appointment is completed', async () => {
    mockedApiFetch.mockResolvedValueOnce({ ...sampleAppointment, status: 'completed' })

    renderPage()
    await screen.findByText('Asha Rao')

    expect(screen.getByText(/no further actions/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Mark/ })).not.toBeInTheDocument()
  })

  it('hides the History section when there are no events', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleAppointment)

    renderPage()
    await screen.findByText('Asha Rao')

    expect(screen.queryByText(/^History/)).not.toBeInTheDocument()
  })

  it('expands the History accordion to show a reschedule event', async () => {
    mockedApiFetch.mockResolvedValueOnce({
      ...sampleAppointment,
      status_events: [
        {
          event_type: 'requested',
          from_status: null,
          to_status: 'requested',
          from_appointment_date: null,
          from_start_time: null,
          to_appointment_date: '2026-08-30',
          to_start_time: '10:00:00',
          offset_minutes: null,
          changed_by: 'browser',
          changed_by_name: null,
          changed_at: '2026-08-26T12:00:00Z',
        },
        {
          event_type: 'rescheduled',
          from_status: null,
          to_status: null,
          from_appointment_date: '2026-08-30',
          from_start_time: '10:00:00',
          to_appointment_date: '2026-09-01',
          to_start_time: '14:30:00',
          offset_minutes: null,
          changed_by: '33333333-3333-3333-3333-333333333333',
          changed_by_name: 'Priya Staff',
          changed_at: '2026-08-27T09:00:00Z',
        },
      ],
    })

    renderPage()
    await screen.findByText('Asha Rao')

    fireEvent.click(screen.getByText('History (2)'))

    expect(screen.getByText(/Slot requested/)).toBeInTheDocument()
    expect(screen.getByText('Rescheduled')).toBeInTheDocument()
    expect(screen.getByText('Customer, via the booking page')).toBeInTheDocument()
    expect(screen.getByText('Priya Staff')).toBeInTheDocument()
  })

  it('falls back to a generic label when a staff actor has no resolved name', async () => {
    mockedApiFetch.mockResolvedValueOnce({
      ...sampleAppointment,
      status_events: [
        {
          event_type: 'confirmed',
          from_status: 'requested',
          to_status: 'confirmed',
          from_appointment_date: null,
          from_start_time: null,
          to_appointment_date: null,
          to_start_time: null,
          offset_minutes: null,
          changed_by: '44444444-4444-4444-4444-444444444444',
          changed_by_name: null,
          changed_at: '2026-08-27T09:00:00Z',
        },
      ],
    })

    renderPage()
    await screen.findByText('Asha Rao')

    fireEvent.click(screen.getByText('History (1)'))

    expect(screen.getByText('Staff member')).toBeInTheDocument()
  })
})
