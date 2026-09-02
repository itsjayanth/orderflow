import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useMemo, useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { useParams, useSearchParams } from 'react-router-dom'
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
import { cn } from '@/lib/utils'
import { ApiError } from '@/shared/api/client'
import type { AppointmentFlowSlotOut } from '@/shared/api/types'
import { formatAppointmentNumber } from '@/shared/lib/appointmentNumber'

import { useAppointmentBooking } from './useAppointmentBooking'
import { useAppointmentServices } from './useAppointmentServices'
import { useAvailableSlots } from './useAvailableSlots'
import { useBookingInfo } from './useBookingInfo'

// Same country-code + local-number split OrderingPage.tsx's checkout form
// uses for "Your WhatsApp number" -- Meta's webhook always reports the
// sender as country code + local number concatenated with no separator
// (e.g. "919876543210"), so matching that shape here is what lets a later
// inbound chat message find the same Customer row this booking creates.
// Only shown as a fallback when the page wasn't opened with a `wa` param
// (see waPhone below).
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

function formatSlotTime(value: string): string {
  return new Date(`2000-01-01T${value}`).toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  })
}

type Step = 'service' | 'date' | 'slot' | 'details'

const bookingSchema = z.object({
  country_code: z.string().min(1, 'Required'),
  local_number: z
    .string()
    .optional()
    .refine(
      (value) => !value || /^\d{6,12}$/.test(value),
      'Enter a valid mobile number (digits only)',
    ),
  name: z.string().trim().min(1, 'Please enter your name'),
  email: z.string().trim().min(1, 'Please enter your email').email('Enter a valid email'),
  appointment_date: z
    .string()
    .min(1, 'Please choose a date')
    .refine((value) => value >= todayISODate(), 'Please choose a date from today onward'),
  start_time: z.string().min(1, 'Please choose a time'),
  service_id: z.string().optional(),
  notes: z.string().optional(),
})
type BookingForm = z.infer<typeof bookingSchema>

export function BookingPage() {
  const { merchantId } = useParams<{ merchantId: string }>()
  const [searchParams] = useSearchParams()
  // The WhatsApp CTA link this page is opened from carries the customer's
  // own number as `?wa=...` (conversation/domain/handler.py's
  // _send_browser_link_reply) -- when present, skip asking for it again;
  // only fall back to the manual phone-entry step if the page was opened
  // some other way (outside WhatsApp).
  const waPhone = searchParams.get('wa')

  const { data: info, isLoading, isError } = useBookingInfo(merchantId ?? '')
  const servicesQuery = useAppointmentServices(merchantId ?? '')
  const booking = useAppointmentBooking(merchantId ?? '')

  const [stepIndex, setStepIndex] = useState(0)
  const [selectedSlot, setSelectedSlot] = useState<AppointmentFlowSlotOut | null>(null)
  const [conflictMessage, setConflictMessage] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    control,
    watch,
    setValue,
    trigger,
    setError,
    formState: { errors },
  } = useForm<BookingForm>({
    resolver: zodResolver(bookingSchema),
    defaultValues: {
      country_code: COUNTRY_CODES[0].code,
      appointment_date: todayISODate(),
    },
  })

  const services = servicesQuery.data ?? []
  const showServiceStep = services.length >= 2
  const selectedServiceId = watch('service_id')
  const appointmentDate = watch('appointment_date')

  // Auto-select the one service a merchant has, if there's exactly one --
  // no picker needed, matches "0 or 1 service = skip this step" below.
  useEffect(() => {
    if (services.length === 1 && !selectedServiceId) {
      setValue('service_id', services[0].service_id)
    }
  }, [services, selectedServiceId, setValue])

  const steps: Step[] = useMemo(() => {
    const list: Step[] = []
    if (showServiceStep) list.push('service')
    list.push('date', 'slot', 'details')
    return list
  }, [showServiceStep])

  const currentStep = steps[stepIndex]

  const slotsQuery = useAvailableSlots(merchantId ?? '', appointmentDate, selectedServiceId)

  // A previously picked slot is only valid for the date/service it was
  // fetched against -- clear it whenever either changes so a stale
  // start_time never rides along to a new date's slot list. appointmentDate/
  // selectedServiceId are deliberately in the deps array purely to
  // re-trigger this effect, not because the body reads them.
  // biome-ignore lint/correctness/useExhaustiveDependencies: deps intentionally re-trigger the effect, not read in its body
  useEffect(() => {
    setSelectedSlot(null)
    setValue('start_time', '')
  }, [appointmentDate, selectedServiceId, setValue])

  const goNext = async (fieldsToValidate: (keyof BookingForm)[] = []) => {
    if (fieldsToValidate.length > 0) {
      const valid = await trigger(fieldsToValidate)
      if (!valid) return
    }
    setStepIndex((i) => Math.min(i + 1, steps.length - 1))
  }
  const goBack = () => setStepIndex((i) => Math.max(i - 1, 0))
  const goToStep = (step: Step) => {
    const idx = steps.indexOf(step)
    if (idx >= 0) setStepIndex(idx)
  }

  const handleSelectSlot = (slot: AppointmentFlowSlotOut) => {
    setSelectedSlot(slot)
    setValue('start_time', slot.start_time)
    setConflictMessage(null)
    void goNext()
  }

  const onDetailsSubmit = handleSubmit((values) => {
    if (!waPhone && !values.local_number) {
      setError('local_number', { message: 'Required' })
      return
    }
    setConflictMessage(null)
    const customerWhatsappNumber = waPhone ?? `${values.country_code}${values.local_number ?? ''}`
    booking.mutate(
      {
        customer_whatsapp_number: customerWhatsappNumber,
        customer_display_name: values.name,
        name: values.name,
        email: values.email,
        appointment_date: values.appointment_date,
        start_time: values.start_time,
        service_id: values.service_id || undefined,
        notes: values.notes?.trim() || undefined,
      },
      {
        onError: (error) => {
          if (error instanceof ApiError && error.status === 409) {
            setConflictMessage('That time was just taken — pick another.')
            setSelectedSlot(null)
            setValue('start_time', '')
            void slotsQuery.refetch()
            goToStep('slot')
            return
          }
          if (error instanceof ApiError && error.status === 400) {
            setConflictMessage('That date is no longer available — please choose another.')
            goToStep('date')
          }
        },
      },
    )
  })

  if (isLoading || servicesQuery.isLoading) {
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
                {formatSlotTime(booking.data.start_time)} – {formatSlotTime(booking.data.end_time)}
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
          <p className="text-muted-foreground text-xs">
            Step {stepIndex + 1} of {steps.length}
          </p>
        </div>

        {currentStep === 'service' && (
          <Card className="space-y-4 p-5">
            <p className="text-sm font-medium">Choose a service</p>
            <div className="space-y-2">
              {services.map((service) => (
                <button
                  key={service.service_id}
                  type="button"
                  onClick={() => {
                    setValue('service_id', service.service_id)
                    void goNext()
                  }}
                  className={cn(
                    'w-full rounded-lg border p-3 text-left transition-colors',
                    selectedServiceId === service.service_id
                      ? 'border-primary bg-primary/5'
                      : 'hover:bg-secondary/40',
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{service.name}</span>
                    <span className="text-muted-foreground text-sm">
                      {service.duration_minutes} min
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </Card>
        )}

        {currentStep === 'date' && (
          <Card className="space-y-4 p-5">
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
            <div className="flex gap-2 pt-2">
              {stepIndex > 0 && (
                <Button type="button" variant="outline" onClick={goBack} className="flex-1">
                  Back
                </Button>
              )}
              <Button
                type="button"
                onClick={() => void goNext(['appointment_date'])}
                className="flex-1"
              >
                Next
              </Button>
            </div>
          </Card>
        )}

        {currentStep === 'slot' && (
          <Card className="space-y-4 p-5">
            <p className="text-sm font-medium">Choose a time</p>
            {conflictMessage && <p className="text-destructive text-sm">{conflictMessage}</p>}
            {slotsQuery.isLoading && (
              <p className="text-muted-foreground text-sm">Loading available times…</p>
            )}
            {slotsQuery.isError && (
              <p className="text-destructive text-sm">
                Couldn't load available times. Try a different date.
              </p>
            )}
            {slotsQuery.data && slotsQuery.data.length === 0 && (
              <p className="text-muted-foreground text-sm">
                No times available that day — try another date.
              </p>
            )}
            {slotsQuery.data && slotsQuery.data.length > 0 && (
              <div className="grid grid-cols-3 gap-2">
                {slotsQuery.data.map((slot) => (
                  <Button
                    key={slot.start_time}
                    type="button"
                    variant={selectedSlot?.start_time === slot.start_time ? 'default' : 'outline'}
                    className="h-11"
                    onClick={() => handleSelectSlot(slot)}
                  >
                    {formatSlotTime(slot.start_time)}
                  </Button>
                ))}
              </div>
            )}
            {errors.start_time && (
              <p className="text-destructive text-sm">{errors.start_time.message}</p>
            )}
            <div className="flex gap-2 pt-2">
              <Button type="button" variant="outline" onClick={goBack} className="flex-1">
                Back
              </Button>
            </div>
          </Card>
        )}

        {currentStep === 'details' && (
          // noValidate -- otherwise the browser's own constraint validation
          // on type="email" blocks the submit event before react-hook-form's
          // zod resolver ever runs, so our own error messages never get a
          // chance to show.
          <form onSubmit={onDetailsSubmit} noValidate>
            <Card className="space-y-4 p-5">
              {selectedSlot && (
                <div className="bg-secondary/40 space-y-1 rounded-lg border p-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Date</span>
                    <span className="font-medium">
                      {new Date(`${appointmentDate}T00:00:00`).toLocaleDateString()}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Time</span>
                    <span className="font-medium">
                      {formatSlotTime(selectedSlot.start_time)} –{' '}
                      {formatSlotTime(selectedSlot.end_time)}
                    </span>
                  </div>
                </div>
              )}

              {!waPhone && (
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
              )}

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

              <div className="space-y-2">
                <Label htmlFor="notes">Notes (optional)</Label>
                <Textarea
                  id="notes"
                  placeholder="Anything we should know?"
                  {...register('notes')}
                />
              </div>

              {conflictMessage && <p className="text-destructive text-sm">{conflictMessage}</p>}
              {booking.isError && !conflictMessage && (
                <p className="text-destructive text-sm">
                  Something went wrong requesting your appointment. Please try again.
                </p>
              )}

              <div className="flex gap-2">
                <Button type="button" variant="outline" onClick={goBack} className="flex-1">
                  Back
                </Button>
                <Button type="submit" size="lg" className="flex-1" disabled={booking.isPending}>
                  {booking.isPending ? 'Requesting…' : 'Confirm & book'}
                </Button>
              </div>
            </Card>
          </form>
        )}
      </div>
    </div>
  )
}
