import { ChevronLeft } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { Card } from '@/components/ui/card'
import { formatAppointmentNumber } from '@/shared/lib/appointmentNumber'

import { AppointmentDetailCard } from './AppointmentDetailCard'
import { useAppointment } from './useAppointment'

export function AppointmentDetailPage() {
  const { appointmentId } = useParams<{ appointmentId: string }>()
  const { data: appointment, isLoading } = useAppointment(appointmentId ?? '')

  if (isLoading) {
    return <p className="text-muted-foreground text-sm">Loading…</p>
  }

  if (!appointment) {
    return <p className="text-muted-foreground text-sm">Appointment not found.</p>
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          to="/appointments"
          className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-sm transition-colors duration-150"
        >
          <ChevronLeft className="size-4" />
          Back to appointments
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">
          Appointment {formatAppointmentNumber(appointment.appointment_number)}
        </h1>
      </div>

      <Card className="p-5">
        <AppointmentDetailCard appointment={appointment} />
      </Card>
    </div>
  )
}
