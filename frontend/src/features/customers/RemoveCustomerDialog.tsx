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

// Shared remove-confirmation dialog for both the single-row and bulk
// "Remove selected" paths on CustomersPage -- same shape as orders'
// CancelOrderDialog, but the copy is deliberately softer: removing a
// customer here just flips `is_active` to false (a row filter, not a
// delete), and the existing per-row/bulk Restore action already undoes it,
// so the dialog should read as "hide, reversible" rather than "gone".
interface RemoveCustomerDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  count: number
  customerLabel?: string
  onConfirm: () => void
}

export function RemoveCustomerDialog({
  open,
  onOpenChange,
  count,
  customerLabel,
  onConfirm,
}: RemoveCustomerDialogProps) {
  const subject =
    count === 1 && customerLabel ? customerLabel : `${count} customer${count === 1 ? '' : 's'}`

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Remove {subject}?</AlertDialogTitle>
          <AlertDialogDescription>
            They'll be hidden from the active customer list but can be restored later.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          {/* Stop propagation here too: AlertDialogContent renders via a
              Portal, but React replays synthetic events through the
              *component* tree, not the DOM tree -- when this dialog is
              triggered from inside a table row (the single-customer case),
              an unguarded click on either button would otherwise still
              bubble up to that row's own click handlers. */}
          <AlertDialogCancel onClick={(e) => e.stopPropagation()}>
            Keep {count === 1 ? 'customer' : 'customers'}
          </AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            onClick={(e) => {
              e.stopPropagation()
              onConfirm()
            }}
          >
            Remove {count === 1 ? 'customer' : 'customers'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
