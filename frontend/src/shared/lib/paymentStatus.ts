// Mirrors backend/src/orders/domain/state_machine.py's PAYMENT_STATUSES --
// shared between OrdersPage's list and OrderDetailPage so the same label
// and color always mean the same thing everywhere in the dashboard.
export const PAYMENT_STATUS_LABELS: Record<string, string> = {
  awaiting_payment: 'Awaiting payment',
  paid: 'Paid online',
  payment_failed: 'Payment failed',
  cancelled: 'Cancelled',
  cod_pending: 'COD — pending',
  cod_collected: 'COD — collected',
}

export type PaymentStatusTone = 'green' | 'amber' | 'red' | 'gray'

export function paymentStatusTone(status: string): PaymentStatusTone {
  if (status === 'paid' || status === 'cod_collected') return 'green'
  if (status === 'cod_pending' || status === 'awaiting_payment') return 'amber'
  if (status === 'payment_failed' || status === 'cancelled') return 'red'
  return 'gray'
}
