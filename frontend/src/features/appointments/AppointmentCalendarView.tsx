import { endOfWeek, format, getDay, parse, startOfWeek } from 'date-fns'
import { enUS } from 'date-fns/locale/en-US'
import { useMemo, useState } from 'react'
import { Calendar as BigCalendar, dateFnsLocalizer, type View, Views } from 'react-big-calendar'
import withDragAndDrop, {
  type EventInteractionArgs,
} from 'react-big-calendar/lib/addons/dragAndDrop'
import 'react-big-calendar/lib/css/react-big-calendar.css'
import 'react-big-calendar/lib/addons/dragAndDrop/styles.css'
import './appointmentCalendar.css'

import { TONE_CLASSES } from '@/components/ui/badge'
import { Sheet } from '@/components/ui/sheet'
import type { AppointmentOut } from '@/shared/api/types'
import { formatAppointmentNumber } from '@/shared/lib/appointmentNumber'
import { formatPhoneNumber } from '@/shared/lib/phoneNumber'

import { AppointmentDetailCard } from './AppointmentDetailCard'
import { APPOINTMENT_STATUS_TONE } from './AppointmentStatusBadge'
import { useRescheduleAppointment } from './useRescheduleAppointment'

const locales = { 'en-US': enUS }
const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek: () => startOfWeek(new Date(), { weekStartsOn: 1 }),
  getDay,
  locales,
})

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

export function AppointmentCalendarView({
  appointments,
  onRangeChange,
}: {
  appointments: AppointmentOut[]
  onRangeChange: (range: CalendarRange) => void
}) {
  const [view, setView] = useState<View>(Views.WEEK)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const reschedule = useRescheduleAppointment()

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
      <div className="rbc-theme-wrapper" style={{ height: '38rem' }}>
        <DragAndDropCalendar
          localizer={localizer}
          events={events}
          view={view}
          onView={setView}
          views={[Views.WEEK, Views.DAY, Views.MONTH]}
          defaultDate={new Date()}
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
          popup
        />
      </div>

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
