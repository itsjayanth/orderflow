import { CalendarDays } from 'lucide-react'
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'
import type { AppointmentOut, AppointmentStatus } from '@/shared/api/types'
import { DateRangeFilter, type DateRangeValue } from '@/shared/components/DateRangeFilter'
import { EmptyState } from '@/shared/components/EmptyState'
import { PageHeader } from '@/shared/components/PageHeader'
import { formatAppointmentNumber } from '@/shared/lib/appointmentNumber'
import { formatCustomerNumber } from '@/shared/lib/customerNumber'
import { formatPhoneNumber } from '@/shared/lib/phoneNumber'
import { StatusActionsMenu } from './StatusActionsMenu'
import { STATUS_LABELS } from './statusTransitions'
import { useAppointments } from './useAppointments'

const TABS: (AppointmentStatus | 'all')[] = [
  'all',
  'requested',
  'confirmed',
  'completed',
  'cancelled',
]

const COLUMN_COUNT = 7
const SKELETON_ROW_COUNT = 5

function isAppointmentStatus(value: string | null): value is AppointmentStatus {
  return (
    value === 'requested' || value === 'confirmed' || value === 'completed' || value === 'cancelled'
  )
}

function formatDate(value: string): string {
  return new Date(`${value}T00:00:00`).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function formatTime(value: string): string {
  return new Date(`2000-01-01T${value}`).toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  })
}

function countByStatus(
  appointments: AppointmentOut[] | undefined,
): Record<AppointmentStatus | 'all', number> {
  const counts: Record<AppointmentStatus | 'all', number> = {
    all: appointments?.length ?? 0,
    requested: 0,
    confirmed: 0,
    completed: 0,
    cancelled: 0,
  }
  for (const appointment of appointments ?? []) {
    counts[appointment.status] += 1
  }
  return counts
}

export function AppointmentsPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const statusParam = searchParams.get('status')
  const [tab, setTab] = useState<AppointmentStatus | 'all'>(
    isAppointmentStatus(statusParam) ? statusParam : 'all',
  )
  const from_date = searchParams.get('from_date') ?? undefined
  const to_date = searchParams.get('to_date') ?? undefined
  const range: DateRangeValue = { from_date, to_date }
  const { data: appointments, isLoading } = useAppointments(range)

  function selectTab(next: AppointmentStatus | 'all') {
    setTab(next)
    const params = new URLSearchParams(searchParams)
    if (next === 'all') params.delete('status')
    else params.set('status', next)
    setSearchParams(params)
  }

  function selectRange(next: DateRangeValue) {
    const params = new URLSearchParams(searchParams)
    if (next.from_date) params.set('from_date', next.from_date)
    else params.delete('from_date')
    if (next.to_date) params.set('to_date', next.to_date)
    else params.delete('to_date')
    setSearchParams(params)
  }

  const counts = countByStatus(appointments)
  const visibleAppointments = appointments?.filter(
    (appointment) => tab === 'all' || appointment.status === tab,
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="Appointments"
        description="Requested time slots from WhatsApp -- confirm, complete, or cancel right here."
        actions={<DateRangeFilter value={range} onChange={selectRange} />}
      />

      <Tabs value={tab} onValueChange={(value) => selectTab(value as AppointmentStatus | 'all')}>
        <TabsList>
          {TABS.map((status) => (
            <TabsTrigger key={status} value={status}>
              {status === 'all' ? 'All' : STATUS_LABELS[status]}
              <span
                className={cn(
                  'rounded-full px-1.5 py-0.5 text-xs font-semibold',
                  tab === status ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground',
                )}
              >
                {counts[status]}
              </span>
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <Card className="overflow-hidden py-0">
        <div className="max-h-[32rem] overflow-auto [&>div]:overflow-visible">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="bg-card border-border sticky top-0 z-10 border-b">
                  Appointment
                </TableHead>
                <TableHead className="bg-card border-border sticky top-0 z-10 border-b">
                  Customer
                </TableHead>
                <TableHead className="bg-card border-border sticky top-0 z-10 border-b">
                  Date
                </TableHead>
                <TableHead className="bg-card border-border sticky top-0 z-10 border-b">
                  Time
                </TableHead>
                <TableHead className="bg-card border-border sticky top-0 z-10 border-b">
                  Name
                </TableHead>
                <TableHead className="bg-card border-border sticky top-0 z-10 border-b">
                  Email
                </TableHead>
                <TableHead className="bg-card border-border sticky top-0 z-10 border-b">
                  Status
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading &&
                Array.from({ length: SKELETON_ROW_COUNT }).map((_, i) => (
                  // biome-ignore lint/suspicious/noArrayIndexKey: skeleton placeholders have no stable identity
                  <TableRow key={`appointments-skeleton-${i}`} className="hover:bg-transparent">
                    <TableCell className="py-2.5">
                      <Skeleton className="h-4 w-14" />
                    </TableCell>
                    <TableCell className="py-2.5">
                      <Skeleton className="h-4 w-32" />
                    </TableCell>
                    <TableCell className="py-2.5">
                      <Skeleton className="h-4 w-24" />
                    </TableCell>
                    <TableCell className="py-2.5">
                      <Skeleton className="h-4 w-16" />
                    </TableCell>
                    <TableCell className="py-2.5">
                      <Skeleton className="h-4 w-24" />
                    </TableCell>
                    <TableCell className="py-2.5">
                      <Skeleton className="h-4 w-32" />
                    </TableCell>
                    <TableCell className="py-2.5">
                      <Skeleton className="h-5 w-20 rounded-full" />
                    </TableCell>
                  </TableRow>
                ))}
              {!isLoading && visibleAppointments?.length === 0 && (
                <TableRow className="hover:bg-transparent">
                  <TableCell colSpan={COLUMN_COUNT}>
                    <EmptyState
                      icon={CalendarDays}
                      title={
                        tab === 'all'
                          ? 'No appointments yet.'
                          : `No ${STATUS_LABELS[tab].toLowerCase()} appointments.`
                      }
                    />
                  </TableCell>
                </TableRow>
              )}
              {visibleAppointments?.map((appointment) => (
                <TableRow
                  key={appointment.appointment_id}
                  onClick={() => navigate(`/appointments/${appointment.appointment_id}`)}
                  className="cursor-pointer"
                >
                  <TableCell className="text-primary py-2.5 font-medium">
                    {formatAppointmentNumber(appointment.appointment_number)}
                  </TableCell>
                  <TableCell className="py-2.5 font-medium">
                    {appointment.customer_name ??
                      formatPhoneNumber(appointment.customer_whatsapp_number)}{' '}
                    <span className="text-muted-foreground font-normal">
                      ({formatCustomerNumber(appointment.customer_number)})
                    </span>
                  </TableCell>
                  <TableCell className="text-muted-foreground py-2.5">
                    {formatDate(appointment.appointment_date)}
                  </TableCell>
                  <TableCell className="text-muted-foreground py-2.5">
                    {formatTime(appointment.appointment_time)}
                  </TableCell>
                  <TableCell className="py-2.5">{appointment.name}</TableCell>
                  <TableCell className="text-muted-foreground py-2.5">
                    {appointment.email}
                  </TableCell>
                  <TableCell className="py-2.5" onClick={(e) => e.stopPropagation()}>
                    <StatusActionsMenu appointment={appointment} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </Card>
    </div>
  )
}
