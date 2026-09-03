import { fireEvent, render, screen } from '@testing-library/react'
import type { ToolbarProps } from 'react-big-calendar'
import { Views } from 'react-big-calendar'
import { describe, expect, it, vi } from 'vitest'

import { CalendarToolbar } from './CalendarToolbar'

// Renders the toolbar in isolation with the exact props react-big-calendar
// hands a custom toolbar component -- avoids mounting the full Calendar,
// which is brittle in jsdom (no real layout/scroll measurement).
function baseProps(overrides: Partial<ToolbarProps> = {}): ToolbarProps {
  return {
    date: new Date(2026, 8, 3),
    view: Views.WEEK,
    views: [Views.WEEK, Views.DAY, Views.MONTH],
    label: 'Sep 2026',
    localizer: { messages: {} },
    onNavigate: vi.fn(),
    onView: vi.fn(),
    ...overrides,
  }
}

describe('CalendarToolbar', () => {
  it('calls onNavigate with PREV/NEXT/TODAY from the nav buttons', () => {
    const onNavigate = vi.fn()
    render(<CalendarToolbar {...baseProps({ onNavigate })} />)

    fireEvent.click(screen.getByRole('button', { name: 'Today' }))
    fireEvent.click(screen.getByRole('button', { name: 'Back' }))
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    expect(onNavigate).toHaveBeenNthCalledWith(1, 'TODAY')
    expect(onNavigate).toHaveBeenNthCalledWith(2, 'PREV')
    expect(onNavigate).toHaveBeenNthCalledWith(3, 'NEXT')
  })

  it('switches views through the tabs', () => {
    const onView = vi.fn()
    render(<CalendarToolbar {...baseProps({ onView })} />)

    // Radix's Tabs.Trigger activates on mousedown (not click) so it can
    // switch before the click's focus/blur cycle completes -- see
    // @radix-ui/react-tabs's TabsTrigger.
    fireEvent.mouseDown(screen.getByRole('tab', { name: 'Day' }))
    expect(onView).toHaveBeenCalledWith('day')

    fireEvent.mouseDown(screen.getByRole('tab', { name: 'Month' }))
    expect(onView).toHaveBeenCalledWith('month')
  })

  it('only renders tabs for the views react-big-calendar was given', () => {
    render(<CalendarToolbar {...baseProps({ views: [Views.WEEK, Views.MONTH] })} />)

    expect(screen.getByRole('tab', { name: 'Week' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Month' })).toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: 'Day' })).not.toBeInTheDocument()
  })

  it('jumps to the selected month/year via the quick-jump popover', () => {
    const onNavigate = vi.fn()
    render(<CalendarToolbar {...baseProps({ onNavigate, label: 'Sep 2026' })} />)

    fireEvent.click(screen.getByRole('button', { name: 'Sep 2026' }))
    fireEvent.click(screen.getByRole('button', { name: 'Go' }))

    expect(onNavigate).toHaveBeenCalledWith('DATE', new Date(2026, 8, 1))
  })
})
