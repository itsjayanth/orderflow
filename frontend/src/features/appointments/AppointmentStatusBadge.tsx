import { Badge, type Tone } from '@/components/ui/badge'
import type { AppointmentStatus } from '@/shared/api/types'

import { STATUS_LABELS } from './statusTransitions'

// The one place AppointmentStatus values map onto Badge's tone system --
// badge.tsx's TONE_CLASSES is the single source of truth for the actual
// colors, this is just which tone each status uses. Exported so other
// status-colored call-sites (StatusActionsMenu's dropdown-trigger pill)
// reuse the same mapping instead of keeping a parallel one. Mirrors
// shared/components/StatusBadge.tsx's role for FulfillmentStatus.
export const APPOINTMENT_STATUS_TONE: Record<AppointmentStatus, Tone> = {
  requested: 'amber',
  confirmed: 'blue',
  completed: 'green',
  cancelled: 'red',
}

export function AppointmentStatusBadge({ status }: { status: AppointmentStatus }) {
  return <Badge tone={APPOINTMENT_STATUS_TONE[status]}>{STATUS_LABELS[status]}</Badge>
}
