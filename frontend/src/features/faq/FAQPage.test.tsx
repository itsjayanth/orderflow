import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/shared/api/client'
import type { FAQItemOut } from '@/shared/api/types'

import { FAQPage } from './FAQPage'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return {
    ...actual,
    apiFetch: vi.fn(),
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const sampleItems: FAQItemOut[] = [
  {
    faq_item_id: '11111111-1111-1111-1111-111111111111',
    question_text: 'Where are you located?',
    answer_text: "We're at 12 MG Road, Bengaluru.",
    keywords: ['location', 'address'],
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
]

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <FAQPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('FAQPage', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('renders FAQ items from the list query', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleItems)

    renderPage()

    expect(await screen.findByText('Where are you located?')).toBeInTheDocument()
    expect(screen.getByText("We're at 12 MG Road, Bengaluru.")).toBeInTheDocument()
    expect(screen.getByText('location')).toBeInTheDocument()
  })

  it('shows an empty state when there are no FAQs yet', async () => {
    mockedApiFetch.mockResolvedValueOnce([])

    renderPage()

    expect(await screen.findByText('No FAQs yet. Add one below.')).toBeInTheDocument()
  })

  it('submitting the add-FAQ form calls the create mutation with parsed keywords', async () => {
    mockedApiFetch.mockResolvedValueOnce([])
    mockedApiFetch.mockResolvedValueOnce({ ...sampleItems[0] })

    renderPage()
    await waitFor(() => expect(mockedApiFetch).toHaveBeenCalledWith('/api/v1/faq/items'))

    fireEvent.change(screen.getByLabelText('Question'), {
      target: { value: 'Where are you located?' },
    })
    fireEvent.change(screen.getByLabelText('Answer'), {
      target: { value: "We're at 12 MG Road, Bengaluru." },
    })
    fireEvent.change(screen.getByLabelText('Keywords (comma-separated, optional)'), {
      target: { value: 'location, address ,  where' },
    })
    fireEvent.click(screen.getByRole('button', { name: /add faq/i }))

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith('/api/v1/faq/items', {
        method: 'POST',
        body: JSON.stringify({
          question_text: 'Where are you located?',
          answer_text: "We're at 12 MG Road, Bengaluru.",
          keywords: ['location', 'address', 'where'],
        }),
      }),
    )
  })

  it('editing a FAQ item calls the update mutation with the new fields', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleItems)
    mockedApiFetch.mockResolvedValueOnce({ ...sampleItems[0], answer_text: 'Updated answer.' })

    renderPage()
    await screen.findByText('Where are you located?')

    fireEvent.click(screen.getByLabelText('Edit Where are you located?'))
    // The row's own edit form and the "Add FAQ" card below both have an
    // "Answer" field -- the row's is first in the DOM.
    fireEvent.change(screen.getAllByLabelText('Answer')[0], {
      target: { value: 'Updated answer.' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        `/api/v1/faq/items/${sampleItems[0].faq_item_id}`,
        {
          method: 'PATCH',
          body: JSON.stringify({
            question_text: 'Where are you located?',
            answer_text: 'Updated answer.',
            keywords: ['location', 'address'],
          }),
        },
      ),
    )
  })

  it('toggling the active switch (delete) calls the update mutation with is_active: false', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleItems)
    mockedApiFetch.mockResolvedValueOnce({ ...sampleItems[0], is_active: false })

    renderPage()
    await screen.findByText('Where are you located?')

    fireEvent.click(screen.getByLabelText('Toggle active for Where are you located?'))

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        `/api/v1/faq/items/${sampleItems[0].faq_item_id}`,
        {
          method: 'PATCH',
          body: JSON.stringify({ is_active: false }),
        },
      ),
    )
  })
})
