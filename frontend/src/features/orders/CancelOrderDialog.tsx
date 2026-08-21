import type { RefObject } from 'react'

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'

// Shared cancel-confirmation dialog for both the single-row
// (StatusActionsMenu) and bulk (OrdersPage's selection bar) cancel paths --
// same copy, same structure, parameterized by how many orders are affected
// and an optional label for the single-order case ("#0007" reads better
// than "1 order" when there's exactly one, named, order in view).
interface CancelOrderDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  count: number
  orderLabel?: string
  onConfirm: () => void
  // StatusActionsMenu opens this from a DropdownMenuItem's onSelect -- that
  // item unmounts the instant its menu closes (which happens before this
  // dialog even opens), so Radix's default close-focus restoration has
  // nothing left to return to and silently drops focus on <body>. Passing
  // the still-mounted status-pill trigger button here lets onCloseAutoFocus
  // send focus somewhere a keyboard user can actually see. The bulk-cancel
  // call site (OrdersPage) opens this from a plain, persistently-mounted
  // Button, so it doesn't need this -- Radix's default restoration already
  // works there.
  restoreFocusRef?: RefObject<HTMLElement | null>
}

export function CancelOrderDialog({
  open,
  onOpenChange,
  count,
  orderLabel,
  onConfirm,
  restoreFocusRef,
}: CancelOrderDialogProps) {
  const subject =
    count === 1 && orderLabel ? `order ${orderLabel}` : `${count} order${count === 1 ? '' : 's'}`

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent
        onCloseAutoFocus={(event) => {
          if (restoreFocusRef?.current) {
            event.preventDefault()
            restoreFocusRef.current.focus()
          }
        }}
      >
        <AlertDialogHeader>
          <AlertDialogTitle>Cancel {subject}?</AlertDialogTitle>
          <AlertDialogDescription>
            This can't be undone. The customer won't be notified automatically unless your WhatsApp
            flow does so.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          {/* Stop propagation here too: AlertDialogContent renders via a
              Portal, but React replays synthetic events through the
              *component* tree, not the DOM tree -- when this dialog is
              nested inside a table row (the single-order case), an
              unguarded click on either button would otherwise still
              bubble up to that row's onClick and toggle its expansion. */}
          <AlertDialogCancel onClick={(e) => e.stopPropagation()}>
            Keep {count === 1 ? 'order' : 'orders'}
          </AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            onClick={(e) => {
              e.stopPropagation()
              onConfirm()
            }}
          >
            Cancel {count === 1 ? 'order' : 'orders'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
