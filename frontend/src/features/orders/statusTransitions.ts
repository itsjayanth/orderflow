import type { FulfillmentStatus } from '@/shared/api/types'

// Mirrors backend/src/orders/domain/state_machine.py's FULFILLMENT_TRANSITIONS
// exactly, so the UI never offers a move the server would reject. The server
// is still the actual authority -- this only controls what's clickable.
const FULFILLMENT_TRANSITIONS: ReadonlySet<`${FulfillmentStatus}->${FulfillmentStatus}`> = new Set([
  'new->processing',
  'processing->ready',
  'ready->completed',
  'new->cancelled',
  'processing->cancelled',
  'ready->cancelled',
])

export function legalNextStatuses(from: FulfillmentStatus): FulfillmentStatus[] {
  const all: FulfillmentStatus[] = ['new', 'processing', 'ready', 'completed', 'cancelled']
  return all.filter((to) => FULFILLMENT_TRANSITIONS.has(`${from}->${to}`))
}

export const STATUS_LABELS: Record<FulfillmentStatus, string> = {
  new: 'New',
  processing: 'Processing',
  ready: 'Ready',
  completed: 'Completed',
  cancelled: 'Cancelled',
}
