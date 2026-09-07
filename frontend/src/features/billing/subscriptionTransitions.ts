import type { SubscriptionStatus } from '@/shared/api/types'

// Mirrors backend/src/billing/domain/state_machine.py's
// SUBSCRIPTION_TRANSITIONS exactly, so the UI never offers a move the
// server would reject. The server is still the actual authority -- this
// only controls what's clickable.
const SUBSCRIPTION_TRANSITIONS: ReadonlySet<`${SubscriptionStatus}->${SubscriptionStatus}`> =
  new Set([
    'trialing->active',
    'trialing->expired',
    'active->past_due',
    'past_due->active',
    'past_due->canceled',
    'active->canceled',
    'expired->active',
    'canceled->active',
  ])

export function legalNextSubscriptionStatuses(from: SubscriptionStatus): SubscriptionStatus[] {
  const all: SubscriptionStatus[] = ['trialing', 'active', 'past_due', 'canceled', 'expired']
  return all.filter((to) => SUBSCRIPTION_TRANSITIONS.has(`${from}->${to}`))
}

export const SUBSCRIPTION_STATUS_LABELS: Record<SubscriptionStatus, string> = {
  trialing: 'Free trial',
  active: 'Active',
  past_due: 'Payment overdue',
  canceled: 'Canceled',
  expired: 'Trial expired',
}
