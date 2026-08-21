import { Badge, type Tone } from '@/components/ui/badge'
import { STATUS_LABELS } from '@/features/orders/statusTransitions'
import type { FulfillmentStatus } from '@/shared/api/types'

// The one place FulfillmentStatus values map onto Badge's tone system --
// badge.tsx's TONE_CLASSES is the single source of truth for the actual
// colors, this is just which tone each status uses. Exported so other
// status-colored call-sites (StatusActionsMenu's dropdown-trigger pill)
// reuse the same mapping instead of keeping a parallel one.
export const FULFILLMENT_STATUS_TONE: Record<FulfillmentStatus, Tone> = {
  new: 'gold',
  preparing: 'blue',
  ready: 'green',
  completed: 'gray',
  cancelled: 'red',
}

export function StatusBadge({ status }: { status: FulfillmentStatus }) {
  return <Badge tone={FULFILLMENT_STATUS_TONE[status]}>{STATUS_LABELS[status]}</Badge>
}
