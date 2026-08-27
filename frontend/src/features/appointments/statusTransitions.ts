import type { AppointmentStatus } from '@/shared/api/types'

// Mirrors backend appointments state machine exactly, so the UI never
// offers a move the server would reject. The server is still the actual
// authority -- this only controls what's clickable.
const APPOINTMENT_TRANSITIONS: ReadonlySet<`${AppointmentStatus}->${AppointmentStatus}`> = new Set([
  'requested->confirmed',
  'requested->cancelled',
  'confirmed->completed',
  'confirmed->cancelled',
])

export function legalNextStatuses(from: AppointmentStatus): AppointmentStatus[] {
  const all: AppointmentStatus[] = ['requested', 'confirmed', 'completed', 'cancelled']
  return all.filter((to) => APPOINTMENT_TRANSITIONS.has(`${from}->${to}`))
}

export const STATUS_LABELS: Record<AppointmentStatus, string> = {
  requested: 'Requested',
  confirmed: 'Confirmed',
  completed: 'Completed',
  cancelled: 'Cancelled',
}
