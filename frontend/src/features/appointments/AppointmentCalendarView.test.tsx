import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { AppointmentAvailabilityWindow } from '@/shared/api/types'

import { getWorkingHoursForDate, HourBand } from './AppointmentCalendarView'

// Full react-big-calendar renders are brittle in jsdom (no real layout,
// heavy internal measurement logic) -- coverage here is scoped to the
// pure day-of-week matching helper and the isolated HourBand control,
// which is where the actual new logic in this file lives.

const WINDOWS: AppointmentAvailabilityWindow[] = [
  // Monday
  { day_of_week: 0, start_time: '09:00:00', end_time: '17:00:00', slot_duration_minutes: 30, buffer_minutes: 0 },
  // Saturday
  { day_of_week: 5, start_time: '10:00:00', end_time: '14:00:00', slot_duration_minutes: 30, buffer_minutes: 0 },
]

describe('getWorkingHoursForDate', () => {
  it('matches a Monday date (JS getDay()=1) to day_of_week=0', () => {
    const monday = new Date(2026, 8, 7) // 2026-09-07 is a Monday
    expect(getWorkingHoursForDate(monday, WINDOWS)).toEqual({
      start: '09:00:00',
      end: '17:00:00',
    })
  })

  it('matches a Saturday date (JS getDay()=6) to day_of_week=5', () => {
    const saturday = new Date(2026, 8, 12) // 2026-09-12 is a Saturday
    expect(getWorkingHoursForDate(saturday, WINDOWS)).toEqual({
      start: '10:00:00',
      end: '14:00:00',
    })
  })

  it('returns null for a day with no configured window', () => {
    const tuesday = new Date(2026, 8, 8) // 2026-09-08 is a Tuesday
    expect(getWorkingHoursForDate(tuesday, WINDOWS)).toBeNull()
  })

  it('returns null when there are no windows at all', () => {
    const monday = new Date(2026, 8, 7)
    expect(getWorkingHoursForDate(monday, [])).toBeNull()
  })
})

describe('HourBand', () => {
  it('renders collapsed by default and toggles aria-expanded on click', () => {
    const onToggle = vi.fn()
    const { rerender } = render(
      <HourBand rangeLabel="12:00 AM – 8:00 AM" expanded={false} onToggle={onToggle} />,
    )

    const button = screen.getByRole('button', { name: /12:00 AM – 8:00 AM · no bookings/ })
    expect(button).toHaveAttribute('aria-expanded', 'false')

    fireEvent.click(button)
    expect(onToggle).toHaveBeenCalledTimes(1)

    rerender(<HourBand rangeLabel="12:00 AM – 8:00 AM" expanded={true} onToggle={onToggle} />)
    expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'true')
  })
})
