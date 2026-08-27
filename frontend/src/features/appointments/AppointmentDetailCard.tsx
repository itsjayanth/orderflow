import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import type { AppointmentOut } from '@/shared/api/types'
import { formatCustomerNumber } from '@/shared/lib/customerNumber'
import { formatPhoneNumber } from '@/shared/lib/phoneNumber'

import { AppointmentStatusBadge } from './AppointmentStatusBadge'
import { legalNextStatuses, STATUS_LABELS } from './statusTransitions'
import { useUpdateAppointmentDetails } from './useUpdateAppointmentDetails'
import { useUpdateAppointmentStatus } from './useUpdateAppointmentStatus'

// Left-column label cell shared by every row -- same convention as
// orders/OrderDetailCard.tsx's FieldLabel.
function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <TableCell className="text-muted-foreground w-40 align-top text-xs font-medium tracking-wide uppercase">
      {children}
    </TableCell>
  )
}

function NotesEditor({ appointmentId, notes }: { appointmentId: string; notes: string | null }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(notes ?? '')
  const updateDetails = useUpdateAppointmentDetails()

  const save = () => {
    updateDetails.mutate(
      { appointmentId, notes: draft.trim() },
      { onSuccess: () => setEditing(false) },
    )
  }

  if (!editing) {
    return (
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          setDraft(notes ?? '')
          setEditing(true)
        }}
        className="group text-left"
      >
        <p
          className={
            notes
              ? 'text-sm'
              : 'text-muted-foreground group-hover:text-foreground text-sm italic transition-colors duration-150'
          }
        >
          {notes || 'Add a note…'}
        </p>
      </button>
    )
  }

  return (
    <div className="space-y-2">
      <Textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        autoFocus
        placeholder="Add a note…"
        aria-label="Appointment notes"
        className="min-h-16 text-sm"
      />
      <div className="flex gap-2">
        <Button type="button" size="sm" onClick={save} disabled={updateDetails.isPending}>
          Save
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={() => setEditing(false)}>
          Cancel
        </Button>
      </div>
    </div>
  )
}

function formatDate(value: string): string {
  // "YYYY-MM-DD" -- parsed with an explicit local-midnight time so it
  // doesn't shift a day backwards in timezones behind UTC.
  return new Date(`${value}T00:00:00`).toLocaleDateString(undefined, {
    weekday: 'short',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function formatTime(value: string): string {
  // "HH:MM:SS" -- render on an arbitrary reference date purely to reuse
  // Intl's locale-aware time formatting.
  return new Date(`2000-01-01T${value}`).toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  })
}

// Shared by AppointmentsPage (row expansion) and AppointmentDetailPage
// (full page) -- mirrors orders/OrderDetailCard.tsx's role/shape.
export function AppointmentDetailCard({
  appointment,
  showStatusActions = true,
}: {
  appointment: AppointmentOut
  showStatusActions?: boolean
}) {
  const updateStatus = useUpdateAppointmentStatus()

  const nextStatuses = legalNextStatuses(appointment.status)
  const showActionsRow = showStatusActions && nextStatuses.length > 0
  const showNoActionsFallback = showStatusActions && nextStatuses.length === 0

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <p className="text-base font-semibold">
          {appointment.customer_name ?? formatPhoneNumber(appointment.customer_whatsapp_number)}{' '}
          <span className="text-muted-foreground font-normal">
            ({formatCustomerNumber(appointment.customer_number)})
          </span>
        </p>
      </div>

      <div className="border-border overflow-hidden rounded-lg border">
        <Table>
          <TableBody>
            <TableRow>
              <FieldLabel>Requested</FieldLabel>
              <TableCell className="text-sm">
                {new Date(appointment.requested_at).toLocaleString()}
              </TableCell>
            </TableRow>
            <TableRow>
              <FieldLabel>Status</FieldLabel>
              <TableCell>
                <AppointmentStatusBadge status={appointment.status} />
              </TableCell>
            </TableRow>
            <TableRow>
              <FieldLabel>Date</FieldLabel>
              <TableCell className="text-sm">{formatDate(appointment.appointment_date)}</TableCell>
            </TableRow>
            <TableRow>
              <FieldLabel>Time</FieldLabel>
              <TableCell className="text-sm">{formatTime(appointment.appointment_time)}</TableCell>
            </TableRow>
            <TableRow>
              <FieldLabel>Name</FieldLabel>
              <TableCell className="text-sm">{appointment.name}</TableCell>
            </TableRow>
            <TableRow>
              <FieldLabel>Email</FieldLabel>
              <TableCell className="text-sm">{appointment.email}</TableCell>
            </TableRow>
            <TableRow>
              <FieldLabel>WhatsApp number</FieldLabel>
              <TableCell className="text-sm">
                {formatPhoneNumber(appointment.customer_whatsapp_number)}
              </TableCell>
            </TableRow>
            <TableRow>
              <FieldLabel>Notes</FieldLabel>
              <TableCell className="whitespace-normal">
                <NotesEditor appointmentId={appointment.appointment_id} notes={appointment.notes} />
              </TableCell>
            </TableRow>
            {appointment.confirmed_at && (
              <TableRow>
                <FieldLabel>Confirmed</FieldLabel>
                <TableCell className="text-sm">
                  {new Date(appointment.confirmed_at).toLocaleString()}
                </TableCell>
              </TableRow>
            )}
            {appointment.completed_at && (
              <TableRow>
                <FieldLabel>Completed</FieldLabel>
                <TableCell className="text-sm">
                  {new Date(appointment.completed_at).toLocaleString()}
                </TableCell>
              </TableRow>
            )}
            {appointment.cancelled_at && (
              <TableRow>
                <FieldLabel>Cancelled</FieldLabel>
                <TableCell className="text-sm">
                  {new Date(appointment.cancelled_at).toLocaleString()}
                </TableCell>
              </TableRow>
            )}
            {(showActionsRow || showNoActionsFallback) && (
              <TableRow>
                <FieldLabel>Actions</FieldLabel>
                <TableCell className="whitespace-normal">
                  {showActionsRow && (
                    <div className="flex flex-wrap items-center gap-2">
                      {nextStatuses.map((status) => (
                        <Button
                          key={status}
                          type="button"
                          size="sm"
                          variant={status === 'cancelled' ? 'outline' : 'default'}
                          disabled={updateStatus.isPending}
                          onClick={() =>
                            updateStatus.mutate({
                              appointmentId: appointment.appointment_id,
                              toStatus: status,
                            })
                          }
                        >
                          Mark {STATUS_LABELS[status]}
                        </Button>
                      ))}
                    </div>
                  )}
                  {showNoActionsFallback && (
                    <p className="text-muted-foreground text-sm">
                      No further actions -- this appointment is in a final state.
                    </p>
                  )}
                  {updateStatus.isError && (
                    <p className="text-destructive mt-2 text-sm">
                      Failed to update status. Please try again.
                    </p>
                  )}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
