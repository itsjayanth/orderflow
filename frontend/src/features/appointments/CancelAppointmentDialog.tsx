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
// (StatusActionsMenu) and detail-page cancel paths -- mirrors
// orders/CancelOrderDialog.tsx exactly, just for appointments.
interface CancelAppointmentDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  appointmentLabel?: string
  onConfirm: () => void
  // See orders/CancelOrderDialog.tsx's identical comment -- StatusActionsMenu
  // opens this from a DropdownMenuItem's onSelect, which unmounts the
  // instant its menu closes, so Radix's default close-focus restoration has
  // nothing left to return to.
  restoreFocusRef?: RefObject<HTMLElement | null>
}

export function CancelAppointmentDialog({
  open,
  onOpenChange,
  appointmentLabel,
  onConfirm,
  restoreFocusRef,
}: CancelAppointmentDialogProps) {
  const subject = appointmentLabel ? `appointment ${appointmentLabel}` : 'this appointment'

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
          {/* Stop propagation here too -- see CancelOrderDialog.tsx's identical
              comment: an unguarded click would otherwise bubble up to a
              containing row's onClick and toggle its expansion. */}
          <AlertDialogCancel onClick={(e) => e.stopPropagation()}>
            Keep appointment
          </AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            onClick={(e) => {
              e.stopPropagation()
              onConfirm()
            }}
          >
            Cancel appointment
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
