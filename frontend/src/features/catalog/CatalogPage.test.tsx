import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/shared/api/client'
import type { MenuItem } from '@/shared/api/types'

import { CatalogPage } from './CatalogPage'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return {
    ...actual,
    apiFetch: vi.fn(),
  }
})

const mockedApiFetch = vi.mocked(apiFetch)

const sampleItems: MenuItem[] = [
  {
    menu_item_id: '11111111-1111-1111-1111-111111111111',
    item_number: 1,
    category: 'Mains',
    name: 'Butter Chicken',
    price: '349.00',
    is_available: true,
    image_url: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    menu_item_id: '22222222-2222-2222-2222-222222222222',
    item_number: 2,
    category: 'Beverages',
    name: 'Mango Lassi',
    price: '90.00',
    is_available: true,
    image_url: 'https://example.com/mango-lassi.jpg',
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
        <CatalogPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('CatalogPage', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
  })

  it('renders menu items from the list query, including item numbers', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleItems)

    renderPage()

    expect(await screen.findByText('Butter Chicken')).toBeInTheDocument()
    expect(screen.getByText('Mains')).toBeInTheDocument()
    expect(screen.getByText('349.00')).toBeInTheDocument()
    expect(screen.getByText('#0001')).toBeInTheDocument()
    expect(screen.getByText('#0002')).toBeInTheDocument()
  })

  it('groups items into one category card per category', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleItems)

    renderPage()

    expect(await screen.findByText('Butter Chicken')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Mains' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Beverages' })).toBeInTheDocument()
  })

  it('filters items by search query, matching name or item number, hiding empty category cards', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleItems)

    renderPage()
    await screen.findByText('Butter Chicken')
    expect(screen.getByText('Mango Lassi')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Search menu items'), {
      target: { value: 'lassi' },
    })
    expect(screen.queryByText('Butter Chicken')).not.toBeInTheDocument()
    expect(screen.getByText('Mango Lassi')).toBeInTheDocument()
    // The Mains category card has zero matches now, so its heading is gone
    // entirely rather than rendered as an empty section.
    expect(screen.queryByRole('heading', { name: 'Mains' })).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Search menu items'), {
      target: { value: '#0001' },
    })
    expect(screen.getByText('Butter Chicken')).toBeInTheDocument()
    expect(screen.queryByText('Mango Lassi')).not.toBeInTheDocument()
  })

  it('editing an item image URL calls the update mutation with the new image_url', async () => {
    mockedApiFetch.mockResolvedValueOnce(sampleItems)
    mockedApiFetch.mockResolvedValueOnce({
      ...sampleItems[0],
      image_url: 'https://example.com/butter-chicken.jpg',
    })

    renderPage()
    await screen.findByText('Butter Chicken')

    fireEvent.click(screen.getByLabelText('Edit image for Butter Chicken'))
    fireEvent.change(screen.getByLabelText('Image URL for Butter Chicken'), {
      target: { value: 'https://example.com/butter-chicken.jpg' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        `/api/v1/catalog/items/${sampleItems[0].menu_item_id}`,
        {
          method: 'PATCH',
          body: JSON.stringify({ image_url: 'https://example.com/butter-chicken.jpg' }),
        },
      ),
    )
  })

  it('submitting the add-item form calls the create mutation with the right payload', async () => {
    mockedApiFetch.mockResolvedValueOnce([])
    mockedApiFetch.mockResolvedValueOnce({ ...sampleItems[0] })

    renderPage()
    await waitFor(() => expect(mockedApiFetch).toHaveBeenCalledWith('/api/v1/catalog/items'))

    fireEvent.change(screen.getByLabelText('Category'), { target: { value: 'Mains' } })
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Butter Chicken' } })
    fireEvent.change(screen.getByLabelText('Price'), { target: { value: '349.00' } })
    fireEvent.click(screen.getByRole('button', { name: /add item/i }))

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith('/api/v1/catalog/items', {
        method: 'POST',
        body: JSON.stringify({ category: 'Mains', name: 'Butter Chicken', price: '349.00' }),
      }),
    )
  })

  it('includes the image URL in the create payload when provided', async () => {
    mockedApiFetch.mockResolvedValueOnce([])
    mockedApiFetch.mockResolvedValueOnce({ ...sampleItems[0] })

    renderPage()
    await waitFor(() => expect(mockedApiFetch).toHaveBeenCalledWith('/api/v1/catalog/items'))

    fireEvent.change(screen.getByLabelText('Category'), { target: { value: 'Mains' } })
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Butter Chicken' } })
    fireEvent.change(screen.getByLabelText('Price'), { target: { value: '349.00' } })
    fireEvent.change(screen.getByLabelText('Image URL (optional)'), {
      target: { value: 'https://example.com/butter-chicken.jpg' },
    })
    fireEvent.click(screen.getByRole('button', { name: /add item/i }))

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith('/api/v1/catalog/items', {
        method: 'POST',
        body: JSON.stringify({
          category: 'Mains',
          name: 'Butter Chicken',
          price: '349.00',
          image_url: 'https://example.com/butter-chicken.jpg',
        }),
      }),
    )
  })
})
