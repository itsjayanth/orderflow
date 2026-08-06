import { STATUS_LABELS } from '@/features/orders/statusTransitions'
import { cn } from '@/lib/utils'
import type { FulfillmentStatus } from '@/shared/api/types'

const STATUS_STYLES: Record<FulfillmentStatus, string> = {
  new: 'bg-brand-gold/20 text-brand-gold-foreground border-brand-gold/40',
  preparing: 'bg-blue-500/10 text-blue-700 border-blue-500/25 dark:text-blue-300',
  ready: 'bg-primary/10 text-primary border-primary/30',
  completed: 'bg-muted text-muted-foreground border-border',
  cancelled: 'bg-destructive/10 text-destructive border-destructive/25',
}

export function StatusBadge({ status }: { status: FulfillmentStatus }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap',
        STATUS_STYLES[status],
      )}
    >
      {STATUS_LABELS[status]}
    </span>
  )
}
