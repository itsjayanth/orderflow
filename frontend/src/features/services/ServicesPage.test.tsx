import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/shared/api/client'
import type { AppointmentServiceSettingsOut } from '@/shared/api/types'

import { ServicesPage } from './ServicesPage'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return {
    ...actual,
    apiFetch: vi.fn(),
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const sampleServices: AppointmentServiceSettingsOut[] = [
  {
    service_id: '11111111-1111-1111-1111-111111111111',
    name: 'Haircut',
    duration_minutes: 30,
    price: '500.00',
    is_active: true,
  },
]

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ServicesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ServicesPage', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('renders services from the list query', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleServices)

    renderPage()

    expect(await screen.findByText('Haircut')).toBeInTheDocument()
    expect(screen.getByText('30 min · 500.00')).toBeInTheDocument()
  })

  it('shows an empty state when there are no services yet', async () => {
    mockedApiFetch.mockResolvedValueOnce([])

    renderPage()

    expect(await screen.findByText(/no services yet/i)).toBeInTheDocument()
  })

  it('submitting the add-service form calls the create mutation with the right payload', async () => {
    mockedApiFetch.mockResolvedValueOnce([])
    mockedApiFetch.mockResolvedValueOnce(sampleServices[0])

    renderPage()
    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith('/api/v1/auth/appointment-services'),
    )

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Haircut' } })
    fireEvent.change(screen.getByLabelText('Duration (minutes)'), { target: { value: '30' } })
    fireEvent.change(screen.getByLabelText('Price (optional)'), { target: { value: '500.00' } })
    fireEvent.click(screen.getByRole('button', { name: /add service/i }))

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith('/api/v1/auth/appointment-services', {
        method: 'POST',
        body: JSON.stringify({ name: 'Haircut', duration_minutes: 30, price: '500.00' }),
      }),
    )
  })
})
