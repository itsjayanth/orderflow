import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/shared/api/client'
import type { AppointmentFlowBookingResponse, AppointmentFlowInfoOut } from '@/shared/api/types'

import { BookingPage } from './BookingPage'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return {
    ...actual,
    apiFetch: vi.fn(),
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const merchantId = '11111111-1111-1111-1111-111111111111'

const sampleInfo: AppointmentFlowInfoOut = {
  business_name: 'Test Kitchen',
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/book/${merchantId}`]}>
        <Routes>
          <Route path="/book/:merchantId" element={<BookingPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('BookingPage', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('renders the booking form with the business name', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleInfo)

    renderPage()

    expect(await screen.findByText('Test Kitchen')).toBeInTheDocument()
    expect(screen.getByLabelText('Your WhatsApp number')).toBeInTheDocument()
    expect(screen.getByLabelText('Your name')).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByLabelText('Date')).toBeInTheDocument()
    expect(screen.getByLabelText('Time')).toBeInTheDocument()
  })

  it('shows a not-available message when the merchant 404s (booking not enabled)', async () => {
    mockedApiFetch.mockRejectedValueOnce(new ApiError(404, 'not found'))

    renderPage()

    expect(
      await screen.findByText("This restaurant isn't accepting appointment bookings right now."),
    ).toBeInTheDocument()
  })

  it('submits the booking form and shows a confirmation', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleInfo)
    const bookingResponse: AppointmentFlowBookingResponse = {
      appointment_id: '33333333-3333-3333-3333-333333333333',
      appointment_number: 5,
      status: 'requested',
      appointment_date: '2099-01-01',
      appointment_time: '15:00:00',
    }
    mockedApiFetch.mockResolvedValueOnce(bookingResponse)

    renderPage()
    await screen.findByText('Test Kitchen')

    fireEvent.change(screen.getByLabelText('Your WhatsApp number'), {
      target: { value: '9876543210' },
    })
    fireEvent.change(screen.getByLabelText('Your name'), { target: { value: 'Asha' } })
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'asha@example.com' } })
    fireEvent.change(screen.getByLabelText('Date'), { target: { value: '2099-01-01' } })
    fireEvent.change(screen.getByLabelText('Time'), { target: { value: '15:00' } })
    fireEvent.click(screen.getByRole('button', { name: 'Request appointment' }))

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        `/api/v1/appointment-flow/${merchantId}/book`,
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"customer_whatsapp_number":"919876543210"'),
        }),
      ),
    )
    const bookCall = mockedApiFetch.mock.calls.find(
      ([path]) => path === `/api/v1/appointment-flow/${merchantId}/book`,
    )
    const requestBody = JSON.parse((bookCall?.[1]?.body as string) ?? '{}')
    expect(requestBody.name).toBe('Asha')
    expect(requestBody.email).toBe('asha@example.com')
    expect(requestBody.appointment_date).toBe('2099-01-01')
    expect(requestBody.appointment_time).toBe('15:00')

    expect(await screen.findByText('Appointment #0005 requested!')).toBeInTheDocument()
    expect(
      screen.getByText("We'll message you on WhatsApp once it's confirmed."),
    ).toBeInTheDocument()
  })

  it('shows a validation error when the name is left blank', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleInfo)

    renderPage()
    await screen.findByText('Test Kitchen')

    fireEvent.change(screen.getByLabelText('Your WhatsApp number'), {
      target: { value: '9876543210' },
    })
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'asha@example.com' } })
    fireEvent.change(screen.getByLabelText('Date'), { target: { value: '2099-01-01' } })
    fireEvent.change(screen.getByLabelText('Time'), { target: { value: '15:00' } })
    fireEvent.click(screen.getByRole('button', { name: 'Request appointment' }))

    expect(await screen.findByText('Please enter your name')).toBeInTheDocument()
    expect(mockedApiFetch).not.toHaveBeenCalledWith(
      `/api/v1/appointment-flow/${merchantId}/book`,
      expect.anything(),
    )
  })

  it('shows a validation error for an invalid email', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleInfo)

    renderPage()
    await screen.findByText('Test Kitchen')

    fireEvent.change(screen.getByLabelText('Your WhatsApp number'), {
      target: { value: '9876543210' },
    })
    fireEvent.change(screen.getByLabelText('Your name'), { target: { value: 'Asha' } })
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'not-an-email' } })
    fireEvent.change(screen.getByLabelText('Date'), { target: { value: '2099-01-01' } })
    fireEvent.change(screen.getByLabelText('Time'), { target: { value: '15:00' } })
    fireEvent.click(screen.getByRole('button', { name: 'Request appointment' }))

    expect(await screen.findByText('Enter a valid email')).toBeInTheDocument()
    expect(mockedApiFetch).not.toHaveBeenCalledWith(
      `/api/v1/appointment-flow/${merchantId}/book`,
      expect.anything(),
    )
  })
})
