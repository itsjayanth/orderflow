import { zodResolver } from '@hookform/resolvers/zod'
import { Controller, useForm } from 'react-hook-form'
import { useParams } from 'react-router-dom'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { formatAppointmentNumber } from '@/shared/lib/appointmentNumber'

import { useAppointmentBooking } from './useAppointmentBooking'
import { useBookingInfo } from './useBookingInfo'

// Same country-code + local-number split OrderingPage.tsx's checkout form
// uses for "Your WhatsApp number" -- Meta's webhook always reports the
// sender as country code + local number concatenated with no separator
// (e.g. "919876543210"), so matching that shape here is what lets a later
// inbound chat message find the same Customer row this booking creates.
const COUNTRY_CODES = [
  { code: '91', label: 'India (+91)' },
  { code: '1', label: 'US/Canada (+1)' },
  { code: '44', label: 'UK (+44)' },
  { code: '971', label: 'UAE (+971)' },
  { code: '65', label: 'Singapore (+65)' },
  { code: '61', label: 'Australia (+61)' },
] as const

function todayISODate(): string {
  return new Date().toISOString().slice(0, 10)
}

const bookingSchema = z.object({
  country_code: z.string().min(1, 'Required'),
  local_number: z
    .string()
    .min(1, 'Required')
    .regex(/^\d{6,12}$/, 'Enter a valid mobile number (digits only)'),
  name: z.string().trim().min(1, 'Please enter your name'),
  email: z.string().trim().min(1, 'Please enter your email').email('Enter a valid email'),
  appointment_date: z
    .string()
    .min(1, 'Please choose a date')
    .refine((value) => value >= todayISODate(), 'Please choose a date from today onward'),
  appointment_time: z.string().min(1, 'Please choose a time'),
  notes: z.string().optional(),
})
type BookingForm = z.infer<typeof bookingSchema>

export function BookingPage() {
  const { merchantId } = useParams<{ merchantId: string }>()
  const { data: info, isLoading, isError } = useBookingInfo(merchantId ?? '')
  const booking = useAppointmentBooking(merchantId ?? '')

  const {
    register,
    handleSubmit,
    control,
    formState: { errors },
  } = useForm<BookingForm>({
    resolver: zodResolver(bookingSchema),
    defaultValues: {
      country_code: COUNTRY_CODES[0].code,
      appointment_date: todayISODate(),
    },
  })

  if (isLoading) {
    return (
      <div className="from-background to-secondary/30 min-h-svh bg-gradient-to-b">
        <div className="mx-auto max-w-md space-y-6 px-4 py-8">
          <div className="motion-safe:animate-pulse space-y-2 text-center">
            <div className="bg-muted mx-auto h-3 w-20 rounded" />
            <div className="bg-muted mx-auto h-7 w-48 rounded" />
          </div>
          <Card className="motion-safe:animate-pulse space-y-4 p-5">
            <div className="bg-muted h-4 w-1/3 rounded" />
            <div className="bg-muted h-10 rounded" />
            <div className="bg-muted h-4 w-1/3 rounded" />
            <div className="bg-muted h-10 rounded" />
          </Card>
        </div>
      </div>
    )
  }

  if (isError || !info) {
    return (
      <div className="flex min-h-svh items-center justify-center p-8">
        <p className="text-muted-foreground max-w-sm text-center text-sm">
          This business isn't accepting appointment bookings right now.
        </p>
      </div>
    )
  }

  const onSubmit = (values: BookingForm) => {
    booking.mutate({
      customer_whatsapp_number: `${values.country_code}${values.local_number}`,
      customer_display_name: values.name,
      name: values.name,
      email: values.email,
      appointment_date: values.appointment_date,
      appointment_time: values.appointment_time,
      notes: values.notes?.trim() || undefined,
    })
  }

  if (booking.isSuccess) {
    return (
      <div className="from-background to-secondary/40 flex min-h-svh items-center justify-center bg-gradient-to-b p-6">
        <Card className="w-full max-w-sm space-y-5 p-8 text-center shadow-lg">
          <span className="bg-primary text-primary-foreground mx-auto flex size-12 items-center justify-center rounded-full text-xl">
            ✓
          </span>
          <div className="space-y-1">
            <h1 className="font-serif text-xl font-semibold">
              Appointment {formatAppointmentNumber(booking.data.appointment_number)} requested!
            </h1>
            <p className="text-muted-foreground text-sm">
              We'll message you on WhatsApp once it's confirmed.
            </p>
          </div>

          <div className="bg-secondary/40 space-y-1.5 rounded-lg border p-4 text-left text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Date</span>
              <span className="font-medium">
                {new Date(`${booking.data.appointment_date}T00:00:00`).toLocaleDateString()}
              </span>
            </div>
            <div className="flex items-center justify-between border-t pt-1.5">
              <span className="text-muted-foreground">Time</span>
              <span className="font-medium">
                {new Date(`2000-01-01T${booking.data.appointment_time}`).toLocaleTimeString(
                  undefined,
                  { hour: 'numeric', minute: '2-digit' },
                )}
              </span>
            </div>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div className="from-background to-secondary/30 min-h-svh bg-gradient-to-b">
      <div className="mx-auto max-w-md space-y-6 px-4 py-8">
        <div className="space-y-1 text-center">
          <p className="text-muted-foreground text-xs tracking-wide uppercase">Book with</p>
          <h1 className="font-serif text-2xl font-semibold">{info.business_name}</h1>
        </div>

        {/* noValidate -- otherwise the browser's own constraint validation
            on type="email"/type="date" blocks the submit event before
            react-hook-form's zod resolver ever runs, so our own error
            messages never get a chance to show. */}
        <form onSubmit={handleSubmit(onSubmit)} noValidate>
          <Card className="space-y-4 p-5">
            <div className="space-y-2">
              <Label htmlFor="local_number">Your WhatsApp number</Label>
              <div className="flex gap-2">
                <Controller
                  name="country_code"
                  control={control}
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger
                        id="country_code"
                        aria-label="Country code"
                        onBlur={field.onBlur}
                        className="w-36 shrink-0"
                      >
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {COUNTRY_CODES.map(({ code, label }) => (
                          <SelectItem key={code} value={code}>
                            {label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
                <Input
                  id="local_number"
                  inputMode="numeric"
                  placeholder="9876543210"
                  {...register('local_number')}
                />
              </div>
              {errors.local_number && (
                <p className="text-destructive text-sm">{errors.local_number.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="name">Your name</Label>
              <Input id="name" {...register('name')} />
              {errors.name && <p className="text-destructive text-sm">{errors.name.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" {...register('email')} />
              {errors.email && <p className="text-destructive text-sm">{errors.email.message}</p>}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="appointment_date">Date</Label>
                <Input
                  id="appointment_date"
                  type="date"
                  min={todayISODate()}
                  {...register('appointment_date')}
                />
                {errors.appointment_date && (
                  <p className="text-destructive text-sm">{errors.appointment_date.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="appointment_time">Time</Label>
                <Input id="appointment_time" type="time" {...register('appointment_time')} />
                {errors.appointment_time && (
                  <p className="text-destructive text-sm">{errors.appointment_time.message}</p>
                )}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="notes">Notes (optional)</Label>
              <Textarea id="notes" placeholder="Anything we should know?" {...register('notes')} />
            </div>

            {booking.isError && (
              <p className="text-destructive text-sm">
                Something went wrong requesting your appointment. Please try again.
              </p>
            )}

            <Button type="submit" size="lg" className="w-full" disabled={booking.isPending}>
              {booking.isPending ? 'Requesting…' : 'Request appointment'}
            </Button>
          </Card>
        </form>
      </div>
    </div>
  )
}
