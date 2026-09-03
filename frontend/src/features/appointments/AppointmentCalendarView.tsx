import { endOfWeek, format, getDay, parse, startOfWeek } from 'date-fns'
import { enUS } from 'date-fns/locale/en-US'
import { ChevronDown } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import {
  Calendar as BigCalendar,
  dateFnsLocalizer,
  type SlotPropGetter,
  type View,
  Views,
} from 'react-big-calendar'
import withDragAndDropImport, {
  type EventInteractionArgs,
} from 'react-big-calendar/lib/addons/dragAndDrop'
import 'react-big-calendar/lib/css/react-big-calendar.css'
import 'react-big-calendar/lib/addons/dragAndDrop/styles.css'
import './appointmentCalendar.css'

import { TONE_CLASSES } from '@/components/ui/badge'
import { Sheet } from '@/components/ui/sheet'
import type { AppointmentAvailabilityWindow, AppointmentOut } from '@/shared/api/types'
import { formatAppointmentNumber } from '@/shared/lib/appointmentNumber'
import { formatPhoneNumber } from '@/shared/lib/phoneNumber'
import { useAppointmentAvailability } from '../settings/useAppointmentAvailability'
import { AppointmentDetailCard } from './AppointmentDetailCard'
import { APPOINTMENT_STATUS_TONE } from './AppointmentStatusBadge'
import { CalendarToolbar } from './CalendarToolbar'
import { useRescheduleAppointment } from './useRescheduleAppointment'

const locales = { 'en-US': enUS }
const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek: () => startOfWeek(new Date(), { weekStartsOn: 1 }),
  getDay,
  locales,
})

// react-big-calendar's dragAndDrop addon is CJS; depending on the bundler's
// interop handling, `withDragAndDropImport` can end up as either the HOC
// function itself or `{ default: <the HOC> }` (esbuild/Rollup don't always
// unwrap a nested `exports.default` reassignment the same way) -- this
// caused a hard crash (`withDragAndDrop is not a function`) on every route
// in production, not just the calendar view, since the whole app is one
// bundle. Unwrap defensively so it works under either shape.
const withDragAndDrop =
  (withDragAndDropImport as unknown as { default?: typeof withDragAndDropImport }).default ??
  withDragAndDropImport

const DragAndDropCalendar = withDragAndDrop<CalendarEvent>(BigCalendar)

interface CalendarEvent {
  id: string
  title: string
  start: Date
  end: Date
  resource: AppointmentOut
}

// "YYYY-MM-DD" + "HH:MM:SS" -> local Date. Appointment times are stored and
// rendered in wall-clock terms (no timezone math client-side, matching how
// AppointmentDetailCard/AppointmentsPage already format these two fields).
function combineDateTime(date: string, time: string): Date {
  return new Date(`${date}T${time}`)
}

function toDateParam(date: Date): string {
  return format(date, 'yyyy-MM-dd')
}

function toTimeParam(date: Date): string {
  return format(date, 'HH:mm:ss')
}

export interface CalendarRange {
  from_date: string
  to_date: string
}

function defaultWeekRange(): CalendarRange {
  const now = new Date()
  return {
    from_date: toDateParam(startOfWeek(now, { weekStartsOn: 1 })),
    to_date: toDateParam(endOfWeek(now, { weekStartsOn: 1 })),
  }
}

export { defaultWeekRange }

// Fallback working-hours window for a day with no configured availability
// window at all -- this is a "show something reasonable" default, not a
// design choice about what hours restaurants should keep.
const DEFAULT_WORKING_HOURS = { start: '09:00:00', end: '18:00:00' }

/** Matches a displayed date against the merchant's configured availability
 * windows (day_of_week: 0=Monday..6=Sunday) and returns that day's
 * start/end times, or null if the day has no configured window at all. */
export function getWorkingHoursForDate(
  date: Date,
  windows: AppointmentAvailabilityWindow[],
): { start: string; end: string } | null {
  const dayOfWeek = (date.getDay() + 6) % 7
  const window = windows.find((w) => w.day_of_week === dayOfWeek)
  if (!window) return null
  return { start: window.start_time, end: window.end_time }
}

// Only the time-of-day components of these Date objects matter -- RBC's
// TimeGrid min/max/slot comparisons only read getHours()/getMinutes(), any
// year/month/day works as the base.
function timeOfDay(time: string): Date {
  const [hours, minutes] = time.split(':').map(Number)
  return new Date(0, 0, 0, hours, minutes, 0)
}

const START_OF_DAY = new Date(0, 0, 0, 0, 0, 0)
const END_OF_DAY = new Date(0, 0, 0, 23, 59, 59)

// 23:59:59 is really "midnight, the next day" for display purposes.
function formatDayBoundary(date: Date): string {
  if (date.getHours() === 23 && date.getMinutes() === 59) return '12:00 AM'
  return format(date, 'h:mm a')
}

function minutesSinceMidnight(date: Date): number {
  return date.getHours() * 60 + date.getMinutes()
}

export function HourBand({
  rangeLabel,
  expanded,
  onToggle,
}: {
  rangeLabel: string
  expanded: boolean
  onToggle: () => void
}) {
  return (
    <button
      type="button"
      aria-expanded={expanded}
      onClick={onToggle}
      className="text-muted-foreground hover:bg-accent hover:text-accent-foreground focus-visible:ring-ring/30 flex w-full items-center gap-1.5 rounded-md border border-dashed px-3 py-1.5 text-xs transition-colors duration-150 outline-none focus-visible:ring-4"
    >
      <ChevronDown
        className={`size-3.5 shrink-0 transition-transform duration-150 ${expanded ? 'rotate-180' : ''}`}
      />
      <span>
        {rangeLabel} · no bookings{expanded ? '' : ' (click to show)'}
      </span>
    </button>
  )
}

export function AppointmentCalendarView({
  appointments,
  onRangeChange,
}: {
  appointments: AppointmentOut[]
  onRangeChange: (range: CalendarRange) => void
}) {
  const [view, setView] = useState<View>(Views.WEEK)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [currentDate, setCurrentDate] = useState(new Date())
  const [beforeExpanded, setBeforeExpanded] = useState(false)
  const [afterExpanded, setAfterExpanded] = useState(false)
  const reschedule = useRescheduleAppointment()
  const { data: availability } = useAppointmentAvailability()

  // Re-collapse the dead-hour bands when the displayed day (or the view)
  // changes, rather than carrying an expanded state from one day to the
  // next as the user navigates.
  // biome-ignore lint/correctness/useExhaustiveDependencies: intentional reset trigger -- these values aren't read in the body, only watched
  useEffect(() => {
    setBeforeExpanded(false)
    setAfterExpanded(false)
  }, [view, currentDate.toDateString()])

  const isDayView = view === Views.DAY
  const workingHours = isDayView
    ? (getWorkingHoursForDate(currentDate, availability?.windows ?? []) ?? DEFAULT_WORKING_HOURS)
    : null
  const workingStart = workingHours ? timeOfDay(workingHours.start) : null
  const workingEnd = workingHours ? timeOfDay(workingHours.end) : null

  const hasBeforeBand = workingStart !== null && minutesSinceMidnight(workingStart) > 0
  const hasAfterBand = workingEnd !== null && minutesSinceMidnight(workingEnd) < 24 * 60 - 1

  const dayViewTimeProps =
    isDayView && workingStart && workingEnd
      ? {
          min: beforeExpanded ? START_OF_DAY : workingStart,
          max: afterExpanded ? END_OF_DAY : workingEnd,
        }
      : {}

  const workingHoursSlotPropGetter: SlotPropGetter | undefined =
    isDayView && workingStart && workingEnd
      ? (date) => {
          const minutes = minutesSinceMidnight(date)
          const startMinutes = minutesSinceMidnight(workingStart)
          const endMinutes = minutesSinceMidnight(workingEnd)
          if (minutes >= startMinutes && minutes < endMinutes) {
            return { className: 'appointment-working-hours-slot' }
          }
          return {}
        }
      : undefined

  const events = useMemo<CalendarEvent[]>(
    () =>
      appointments.map((appointment) => ({
        id: appointment.appointment_id,
        title: `${appointment.customer_name ?? formatPhoneNumber(appointment.customer_whatsapp_number)} · ${formatAppointmentNumber(appointment.appointment_number)}`,
        start: combineDateTime(appointment.appointment_date, appointment.start_time),
        end: combineDateTime(appointment.appointment_date, appointment.end_time),
        resource: appointment,
      })),
    [appointments],
  )

  const selected = appointments.find((a) => a.appointment_id === selectedId) ?? null

  const handleRangeChange = (range: Date[] | { start: Date; end: Date }) => {
    if (Array.isArray(range)) {
      if (range.length === 0) return
      onRangeChange({
        from_date: toDateParam(range[0]),
        to_date: toDateParam(range[range.length - 1]),
      })
    } else {
      onRangeChange({ from_date: toDateParam(range.start), to_date: toDateParam(range.end) })
    }
  }

  // No optimistic cache write here on purpose: react-big-calendar renders
  // strictly from the `events` prop, so a dropped event that the backend
  // rejects (409 slot_no_longer_available) simply stays wherever the
  // still-unchanged query cache says it is -- the drag "snaps back" for
  // free on the next render, no manual revert needed.
  const handleEventDrop = ({ event, start }: EventInteractionArgs<CalendarEvent>) => {
    const startDate = start instanceof Date ? start : new Date(start)
    reschedule.mutate({
      appointmentId: event.id,
      appointmentDate: toDateParam(startDate),
      startTime: toTimeParam(startDate),
    })
  }

  return (
    <div className="space-y-2">
      {isDayView && hasBeforeBand && workingStart && (
        <HourBand
          rangeLabel={`${formatDayBoundary(START_OF_DAY)} – ${formatDayBoundary(workingStart)}`}
          expanded={beforeExpanded}
          onToggle={() => setBeforeExpanded((prev) => !prev)}
        />
      )}

      <div className="rbc-theme-wrapper" style={{ height: '38rem' }}>
        <DragAndDropCalendar
          localizer={localizer}
          events={events}
          view={view}
          onView={setView}
          views={[Views.WEEK, Views.DAY, Views.MONTH]}
          date={currentDate}
          onNavigate={setCurrentDate}
          onRangeChange={handleRangeChange}
          onSelectEvent={(event) => setSelectedId(event.id)}
          onEventDrop={handleEventDrop}
          resizable={false}
          draggableAccessor={() => true}
          startAccessor="start"
          endAccessor="end"
          titleAccessor="title"
          eventPropGetter={(event) => ({
            className: TONE_CLASSES[APPOINTMENT_STATUS_TONE[event.resource.status]],
          })}
          components={{ toolbar: CalendarToolbar }}
          {...dayViewTimeProps}
          slotPropGetter={workingHoursSlotPropGetter}
          popup
        />
      </div>

      {isDayView && hasAfterBand && workingEnd && (
        <HourBand
          rangeLabel={`${formatDayBoundary(workingEnd)} – ${formatDayBoundary(END_OF_DAY)}`}
          expanded={afterExpanded}
          onToggle={() => setAfterExpanded((prev) => !prev)}
        />
      )}

      <Sheet
        open={selected !== null}
        onOpenChange={(open) => !open && setSelectedId(null)}
        title={
          selected ? `Appointment ${formatAppointmentNumber(selected.appointment_number)}` : ''
        }
      >
        {selected && <AppointmentDetailCard appointment={selected} />}
      </Sheet>
    </div>
  )
}
