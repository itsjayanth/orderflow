import type { LucideIcon } from 'lucide-react'
import {
  CheckCircle,
  ChevronDown,
  Clock,
  Flame,
  Loader2,
  PackageCheck,
  XCircle,
} from 'lucide-react'
import { useRef, useState } from 'react'

import { TONE_CLASSES } from '@/components/ui/badge'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'
import type { FulfillmentStatus, OrderOut } from '@/shared/api/types'
import { FULFILLMENT_STATUS_TONE } from '@/shared/components/StatusBadge'
import { formatOrderNumber } from '@/shared/lib/orderNumber'

import { CancelOrderDialog } from './CancelOrderDialog'
import { legalNextStatuses, STATUS_LABELS } from './statusTransitions'
import { useUpdateOrderStatus } from './useUpdateOrderStatus'

const STATUS_ICONS: Record<FulfillmentStatus, LucideIcon> = {
  new: Clock,
  processing: Flame,
  ready: CheckCircle,
  completed: PackageCheck,
  cancelled: XCircle,
}

// The icon accent per status -- deliberately just the text-color half of
// StatusBadge's tone (via FULFILLMENT_STATUS_TONE/TONE_CLASSES), so the
// menu item's icon reads as the same color language as the badge/trigger
// pill it lives under.
const STATUS_ICON_CLASSES: Record<FulfillmentStatus, string> = {
  new: 'text-brand-gold-foreground',
  processing: 'text-blue-600 dark:text-blue-300',
  ready: 'text-primary',
  completed: 'text-muted-foreground',
  cancelled: 'text-destructive',
}

// Replaces the old native-<select>-based StatusSelect with a real
// DropdownMenu: the trigger looks like the existing StatusBadge pill (same
// per-status colors) but is unambiguously clickable, and each option gets
// a distinct icon instead of being a flat text list.
export function StatusActionsMenu({ order }: { order: OrderOut }) {
  const updateStatus = useUpdateOrderStatus()
  const [confirmCancelOpen, setConfirmCancelOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)

  if (!order.fulfillment_status) {
    return <span className="text-muted-foreground text-sm">Awaiting payment</span>
  }

  const currentStatus = order.fulfillment_status
  const nextStatuses = legalNextStatuses(currentStatus)
  const isPending = updateStatus.isPending

  function selectStatus(status: FulfillmentStatus) {
    // Cancelling is destructive and irreversible -- gate it behind an
    // explicit confirmation instead of firing the mutation immediately,
    // same as every other transition does.
    if (status === 'cancelled') {
      setConfirmCancelOpen(true)
      return
    }
    updateStatus.mutate({ orderId: order.order_id, toStatus: status })
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            ref={triggerRef}
            type="button"
            aria-label={`Change status for order ${formatOrderNumber(order.order_number)}`}
            disabled={isPending}
            onClick={(e) => e.stopPropagation()}
            className={cn(
              'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap transition-all duration-150 outline-none',
              'hover:brightness-95 focus-visible:ring-4 focus-visible:ring-ring/30',
              'disabled:pointer-events-none disabled:opacity-60',
              TONE_CLASSES[FULFILLMENT_STATUS_TONE[currentStatus]],
            )}
          >
            {isPending ? <Loader2 className="size-3 animate-spin" /> : STATUS_LABELS[currentStatus]}
            {!isPending && <ChevronDown className="size-3" />}
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" onClick={(e) => e.stopPropagation()} className="w-44">
          <DropdownMenuLabel>Current status: {STATUS_LABELS[currentStatus]}</DropdownMenuLabel>
          <DropdownMenuSeparator />
          {nextStatuses.map((status) => {
            const Icon = STATUS_ICONS[status]
            return (
              <DropdownMenuItem
                key={status}
                variant={status === 'cancelled' ? 'destructive' : 'default'}
                disabled={isPending}
                onSelect={() => selectStatus(status)}
              >
                <Icon className={cn(status !== 'cancelled' && STATUS_ICON_CLASSES[status])} />
                Mark {STATUS_LABELS[status]}
              </DropdownMenuItem>
            )
          })}
          {nextStatuses.length === 0 && (
            <p className="text-muted-foreground px-2 py-1.5 text-sm">No further actions.</p>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
      <CancelOrderDialog
        open={confirmCancelOpen}
        onOpenChange={setConfirmCancelOpen}
        count={1}
        orderLabel={formatOrderNumber(order.order_number)}
        onConfirm={() => updateStatus.mutate({ orderId: order.order_id, toStatus: 'cancelled' })}
        restoreFocusRef={triggerRef}
      />
    </>
  )
}
