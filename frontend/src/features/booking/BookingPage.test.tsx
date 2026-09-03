import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/shared/api/client'
import type {
  AppointmentFlowBookingResponse,
  AppointmentFlowCustomerLookupOut,
  AppointmentFlowInfoOut,
  AppointmentFlowServiceOut,
  AppointmentFlowSlotOut,
} from '@/shared/api/types'

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
const bookPath = `/api/v1/appointment-flow/${merchantId}/book`

const sampleInfo: AppointmentFlowInfoOut = {
  business_name: 'Test Business',
  // Null keeps the WhatsApp return block (and its auto-redirect) out of
  // these tests -- it has its own coverage in WhatsAppReturn.test.tsx.
  merchant_whatsapp_number: null,
}

const sampleSlots: AppointmentFlowSlotOut[] = [
  { start_time: '15:00:00', end_time: '15:30:00' },
  { start_time: '15:30:00', end_time: '16:00:00' },
]

function formatSlotTime(value: string): string {
  return new Date(`2000-01-01T${value}`).toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  })
}

// Routes every call by matching the path, independent of which of the two
// initial queries (info, services) React Query happens to fire first.
function installApiMock(options: {
  info?: AppointmentFlowInfoOut | ApiError
  services?: AppointmentFlowServiceOut[]
  slots?: AppointmentFlowSlotOut[]
  book?: AppointmentFlowBookingResponse | ApiError
  customerLookup?: AppointmentFlowCustomerLookupOut | ApiError
}) {
  mockedApiFetch.mockImplementation((path: string) => {
    if (path.includes('/info')) {
      return options.info instanceof ApiError
        ? Promise.reject(options.info)
        : Promise.resolve(options.info ?? sampleInfo)
    }
    if (path.includes('/services')) {
      return Promise.resolve(options.services ?? [])
    }
    if (path.includes('/availability')) {
      return Promise.resolve(options.slots ?? sampleSlots)
    }
    if (path.includes('/customer-lookup')) {
      if (options.customerLookup === undefined) {
        return Promise.reject(new ApiError(404, 'not found'))
      }
      return options.customerLookup instanceof ApiError
        ? Promise.reject(options.customerLookup)
        : Promise.resolve(options.customerLookup)
    }
    if (path === bookPath) {
      return options.book instanceof ApiError
        ? Promise.reject(options.book)
        : Promise.resolve(
            options.book ?? {
              appointment_id: '33333333-3333-3333-3333-333333333333',
              appointment_number: 5,
              status: 'requested',
              appointment_date: '2099-01-01',
              start_time: '15:00:00',
              end_time: '15:30:00',
            },
          )
    }
    throw new Error(`Unexpected apiFetch call: ${path}`)
  })
}

function renderPage(initialPath = `/book/${merchantId}`) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/book/:merchantId" element={<BookingPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

// Drives the wizard from the date step through slot selection, landing on
// the details step. Shared by every test that needs to reach "details".
async function advanceToDetailsStep(slotStartTime = '15:00:00') {
  fireEvent.change(screen.getByLabelText('Date'), { target: { value: '2099-01-01' } })
  fireEvent.click(screen.getByRole('button', { name: 'Next' }))

  const slot = sampleSlots.find((s) => s.start_time === slotStartTime) ?? sampleSlots[0]
  const slotButton = await screen.findByRole('button', { name: formatSlotTime(slot.start_time) })
  fireEvent.click(slotButton)

  // Notes always renders as a normal input regardless of whether name/email
  // are showing as confirmed fields or editable ones, so it's a stable
  // signal that the details step has mounted.
  await screen.findByLabelText('Notes (optional)')
}

describe('BookingPage', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('renders the date step first when the merchant has no configured services', async () => {
    installApiMock({ services: [] })

    renderPage()

    expect(await screen.findByText('Test Business')).toBeInTheDocument()
    expect(screen.getByText('Step 1 of 3')).toBeInTheDocument()
    expect(screen.getByLabelText('Date')).toBeInTheDocument()
  })

  it('shows a not-available message when the merchant 404s (booking not enabled)', async () => {
    installApiMock({ info: new ApiError(404, 'not found') })

    renderPage()

    expect(
      await screen.findByText("This business isn't accepting appointment bookings right now."),
    ).toBeInTheDocument()
  })

  it('walks the date -> slot -> details wizard and submits a booking', async () => {
    installApiMock({})

    renderPage()
    await screen.findByText('Test Business')
    await advanceToDetailsStep()

    fireEvent.change(screen.getByLabelText('Your WhatsApp number'), {
      target: { value: '9876543210' },
    })
    fireEvent.change(screen.getByLabelText('Your name'), { target: { value: 'Asha' } })
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'asha@example.com' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirm & book' }))

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        bookPath,
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"customer_whatsapp_number":"919876543210"'),
        }),
      ),
    )
    const bookCall = mockedApiFetch.mock.calls.find(([path]) => path === bookPath)
    const requestBody = JSON.parse((bookCall?.[1]?.body as string) ?? '{}')
    expect(requestBody.name).toBe('Asha')
    expect(requestBody.email).toBe('asha@example.com')
    expect(requestBody.appointment_date).toBe('2099-01-01')
    expect(requestBody.start_time).toBe('15:00:00')

    expect(await screen.findByText('Appointment #0005 requested!')).toBeInTheDocument()
    expect(
      screen.getByText("We'll message you on WhatsApp once it's confirmed."),
    ).toBeInTheDocument()
  })

  it('offers a WhatsApp return link on the confirmation once the merchant has a number', async () => {
    installApiMock({
      info: { ...sampleInfo, merchant_whatsapp_number: '+91 90000 00000' },
    })

    renderPage()
    await screen.findByText('Test Business')
    await advanceToDetailsStep()

    fireEvent.change(screen.getByLabelText('Your WhatsApp number'), {
      target: { value: '9876543210' },
    })
    fireEvent.change(screen.getByLabelText('Your name'), { target: { value: 'Asha' } })
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'asha@example.com' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirm & book' }))

    expect(await screen.findByText('Appointment #0005 requested!')).toBeInTheDocument()
    // The booking is already persisted and its "request received" message
    // already sent by now, so this screen has nothing left to hold the
    // customer for -- unlike an order still awaiting payment.
    expect(screen.getByText(/redirecting you back to whatsapp/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Tap here to return to WhatsApp' })).toHaveAttribute(
      'href',
      'https://wa.me/919000000000',
    )
  })

  it('prefills the WhatsApp number from the `wa` query param and skips the manual entry field', async () => {
    installApiMock({})

    renderPage(`/book/${merchantId}?wa=919876543210`)
    await screen.findByText('Test Business')
    await advanceToDetailsStep()

    expect(screen.queryByLabelText('Your WhatsApp number')).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Your name'), { target: { value: 'Asha' } })
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'asha@example.com' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirm & book' }))

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        bookPath,
        expect.objectContaining({
          body: expect.stringContaining('"customer_whatsapp_number":"919876543210"'),
        }),
      ),
    )
  })

  it('shows a validation error when the name is left blank', async () => {
    installApiMock({})

    renderPage()
    await screen.findByText('Test Business')
    await advanceToDetailsStep()

    fireEvent.change(screen.getByLabelText('Your WhatsApp number'), {
      target: { value: '9876543210' },
    })
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'asha@example.com' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirm & book' }))

    expect(await screen.findByText('Please enter your name')).toBeInTheDocument()
    expect(mockedApiFetch).not.toHaveBeenCalledWith(bookPath, expect.anything())
  })

  it('sends the user back to the slot step and refreshes availability on a 409 conflict', async () => {
    installApiMock({ book: new ApiError(409, '{"detail":"slot_no_longer_available"}') })

    renderPage()
    await screen.findByText('Test Business')
    await advanceToDetailsStep()

    fireEvent.change(screen.getByLabelText('Your WhatsApp number'), {
      target: { value: '9876543210' },
    })
    fireEvent.change(screen.getByLabelText('Your name'), { target: { value: 'Asha' } })
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'asha@example.com' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirm & book' }))

    expect(await screen.findByText('That time was just taken — pick another.')).toBeInTheDocument()
    expect(screen.getByText('Choose a time')).toBeInTheDocument()
  })

  it('prefills name and email as confirmed fields for a returning customer', async () => {
    installApiMock({
      customerLookup: { display_name: 'Asha', email: 'asha@example.com' },
    })

    renderPage(`/book/${merchantId}?wa=919876543210`)
    await screen.findByText('Test Business')
    await advanceToDetailsStep()

    expect(await screen.findByText('Asha')).toBeInTheDocument()
    expect(screen.getByText('asha@example.com')).toBeInTheDocument()
    expect(screen.getAllByText('✓ Looks right')).toHaveLength(2)
    // No editable name/email inputs while confirmed.
    expect(screen.queryByLabelText('Your name')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Email')).not.toBeInTheDocument()

    expect(screen.getByRole('button', { name: '✓ Confirm & continue' })).toBeInTheDocument()
  })

  it('lets a returning customer edit a confirmed name/email field', async () => {
    installApiMock({
      customerLookup: { display_name: 'Asha', email: 'asha@example.com' },
    })

    renderPage(`/book/${merchantId}?wa=919876543210`)
    await screen.findByText('Test Business')
    await advanceToDetailsStep()
    await screen.findByText('Asha')

    const editButtons = screen.getAllByRole('button', { name: 'Edit' })
    fireEvent.click(editButtons[0]) // name

    const nameInput = screen.getByLabelText('Your name')
    expect(nameInput).toHaveValue('Asha')
    fireEvent.change(nameInput, { target: { value: 'Asha Rao' } })

    // Email is still confirmed/read-only -- editing one field doesn't
    // disturb the other.
    expect(screen.getByText('asha@example.com')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '✓ Confirm & continue' }))

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        bookPath,
        expect.objectContaining({
          body: expect.stringContaining('"name":"Asha Rao"'),
        }),
      ),
    )
  })

  it('shows an empty, fillable email field when the customer has a name but no email on file', async () => {
    installApiMock({
      customerLookup: { display_name: 'Asha', email: null },
    })

    renderPage(`/book/${merchantId}?wa=919876543210`)
    await screen.findByText('Test Business')
    await advanceToDetailsStep()

    expect(await screen.findByText('Asha')).toBeInTheDocument()
    const emailInput = screen.getByLabelText('Email')
    expect(emailInput).toHaveValue('')

    fireEvent.change(emailInput, { target: { value: 'asha@example.com' } })
    fireEvent.click(screen.getByRole('button', { name: '✓ Confirm & continue' }))

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        bookPath,
        expect.objectContaining({
          body: expect.stringContaining('"email":"asha@example.com"'),
        }),
      ),
    )
  })

  it('never renders a phone field or phone edit control, even for a returning customer', async () => {
    installApiMock({
      customerLookup: { display_name: 'Asha', email: 'asha@example.com' },
    })

    renderPage(`/book/${merchantId}?wa=919876543210`)
    await screen.findByText('Test Business')
    await advanceToDetailsStep()
    await screen.findByText('Asha')

    expect(screen.queryByLabelText('Your WhatsApp number')).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/phone/i)).not.toBeInTheDocument()
    // Only two Edit buttons ever render (name, email) -- none for phone.
    expect(screen.getAllByRole('button', { name: 'Edit' })).toHaveLength(2)
  })

  it('falls back to blank fields and "Confirm & book" when the lookup finds no customer', async () => {
    installApiMock({})

    renderPage(`/book/${merchantId}?wa=919876543210`)
    await screen.findByText('Test Business')
    await advanceToDetailsStep()

    expect(screen.queryByText('✓ Looks right')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Your name')).toHaveValue('')
    expect(screen.getByLabelText('Email')).toHaveValue('')
    expect(screen.getByRole('button', { name: 'Confirm & book' })).toBeInTheDocument()
  })
})
