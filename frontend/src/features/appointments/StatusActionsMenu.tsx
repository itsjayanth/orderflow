import type { LucideIcon } from 'lucide-react'
import {
  CalendarCheck,
  CalendarClock,
  ChevronDown,
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
import type { AppointmentOut, AppointmentStatus } from '@/shared/api/types'
import { formatAppointmentNumber } from '@/shared/lib/appointmentNumber'

import { APPOINTMENT_STATUS_TONE } from './AppointmentStatusBadge'
import { CancelAppointmentDialog } from './CancelAppointmentDialog'
import { legalNextStatuses, STATUS_LABELS } from './statusTransitions'
import { useUpdateAppointmentStatus } from './useUpdateAppointmentStatus'

const STATUS_ICONS: Record<AppointmentStatus, LucideIcon> = {
  requested: CalendarClock,
  confirmed: CalendarCheck,
  completed: PackageCheck,
  cancelled: XCircle,
}

// The icon accent per status -- deliberately just the text-color half of
// AppointmentStatusBadge's tone (via APPOINTMENT_STATUS_TONE/TONE_CLASSES),
// so the menu item's icon reads as the same color language as the badge/
// trigger pill it lives under. Mirrors orders/StatusActionsMenu.tsx.
const STATUS_ICON_CLASSES: Record<AppointmentStatus, string> = {
  requested: 'text-amber-600 dark:text-amber-300',
  confirmed: 'text-blue-600 dark:text-blue-300',
  completed: 'text-primary',
  cancelled: 'text-destructive',
}

// A real DropdownMenu, not a native <select> -- the trigger looks like a
// status badge pill (same per-status colors) but is unambiguously
// clickable, and each option gets a distinct icon. Mirrors
// orders/StatusActionsMenu.tsx exactly.
export function StatusActionsMenu({ appointment }: { appointment: AppointmentOut }) {
  const updateStatus = useUpdateAppointmentStatus()
  const [confirmCancelOpen, setConfirmCancelOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)

  const currentStatus = appointment.status
  const nextStatuses = legalNextStatuses(currentStatus)
  const isPending = updateStatus.isPending

  function selectStatus(status: AppointmentStatus) {
    // Cancelling is destructive and irreversible -- gate it behind an
    // explicit confirmation instead of firing the mutation immediately,
    // same as every other transition does.
    if (status === 'cancelled') {
      setConfirmCancelOpen(true)
      return
    }
    updateStatus.mutate({ appointmentId: appointment.appointment_id, toStatus: status })
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            ref={triggerRef}
            type="button"
            aria-label={`Change status for appointment ${formatAppointmentNumber(appointment.appointment_number)}`}
            disabled={isPending}
            onClick={(e) => e.stopPropagation()}
            className={cn(
              'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap transition-all duration-150 outline-none',
              'hover:brightness-95 focus-visible:ring-4 focus-visible:ring-ring/30',
              'disabled:pointer-events-none disabled:opacity-60',
              TONE_CLASSES[APPOINTMENT_STATUS_TONE[currentStatus]],
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
      <CancelAppointmentDialog
        open={confirmCancelOpen}
        onOpenChange={setConfirmCancelOpen}
        appointmentLabel={formatAppointmentNumber(appointment.appointment_number)}
        onConfirm={() =>
          updateStatus.mutate({ appointmentId: appointment.appointment_id, toStatus: 'cancelled' })
        }
        restoreFocusRef={triggerRef}
      />
    </>
  )
}
