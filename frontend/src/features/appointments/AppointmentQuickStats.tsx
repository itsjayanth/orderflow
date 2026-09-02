import { useMemo } from 'react'

import { Card } from '@/components/ui/card'
import type { AppointmentOut } from '@/shared/api/types'

function todayISODate(): string {
  return new Date().toISOString().slice(0, 10)
}

function daysFromNowISODate(days: number): string {
  const date = new Date()
  date.setDate(date.getDate() + days)
  return date.toISOString().slice(0, 10)
}

// Computed from whatever's already been fetched for the currently visible
// date range -- not a separate stats endpoint. If the visible range
// (list view's date filter, or the calendar's current page) doesn't cover
// "today" or "next 7 days", these counts are scoped to whatever's actually
// in view rather than firing an extra fetch just for two numbers.
export function AppointmentQuickStats({ appointments }: { appointments: AppointmentOut[] }) {
  const { todayCount, next7DaysCount } = useMemo(() => {
    const today = todayISODate()
    const in7Days = daysFromNowISODate(7)
    let todayCount = 0
    let next7DaysCount = 0
    for (const appointment of appointments) {
      if (appointment.status === 'cancelled') continue
      if (appointment.appointment_date === today) todayCount += 1
      if (appointment.appointment_date >= today && appointment.appointment_date <= in7Days) {
        next7DaysCount += 1
      }
    }
    return { todayCount, next7DaysCount }
  }, [appointments])

  return (
    <div className="grid grid-cols-2 gap-3 sm:max-w-xs">
      <Card className="gap-1 p-4">
        <p className="text-muted-foreground text-xs">Today</p>
        <p className="text-2xl font-semibold">{todayCount}</p>
      </Card>
      <Card className="gap-1 p-4">
        <p className="text-muted-foreground text-xs">Next 7 days</p>
        <p className="text-2xl font-semibold">{next7DaysCount}</p>
      </Card>
    </div>
  )
}
