import { zodResolver } from '@hookform/resolvers/zod'
import { Info } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { ConnectWhatsAppButton } from '@/features/onboarding/ConnectWhatsAppButton'
import type { NotificationTemplateOut } from '@/shared/api/types'
import { PageHeader } from '@/shared/components/PageHeader'
import { SavedIndicator } from '@/shared/components/SavedIndicator'

import { AppointmentFlowSetupCard } from './AppointmentFlowSetupCard'
import { TestWhatsAppMessageCard } from './TestWhatsAppMessageCard'
import {
  useAppointmentAvailability,
  useUpdateAppointmentAvailability,
} from './useAppointmentAvailability'
import { useAppointmentSettings, useUpdateAppointmentSettings } from './useAppointmentSettings'
import { useNotificationTemplates, useUpdateNotificationTemplate } from './useNotificationTemplates'
import { usePaymentSettings, useUpdatePaymentSettings } from './usePaymentSettings'
import { useWhatsAppSettings } from './useWhatsAppSettings'
import { WhatsAppFlowSetupCard } from './WhatsAppFlowSetupCard'

const paymentSchema = z.object({
  razorpay_key_id: z.string().min(1, 'Required'),
  razorpay_key_secret: z.string().min(1, 'Required'),
})
type PaymentForm = z.infer<typeof paymentSchema>

function PaymentSettingsSection() {
  const { data, isLoading } = usePaymentSettings()
  const update = useUpdatePaymentSettings()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<PaymentForm>({ resolver: zodResolver(paymentSchema) })

  const onSubmit = (values: PaymentForm) => {
    update.mutate(values, { onSuccess: () => reset() })
  }

  return (
    <Card className="space-y-4 p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-medium">Payments (Razorpay)</h2>
          <p className="text-muted-foreground text-sm">
            Used to generate payment links for online orders.
          </p>
        </div>
        {!isLoading && data && (
          <Badge tone={data.using_real_gateway ? 'green' : 'amber'}>
            {data.using_real_gateway ? 'Live keys' : 'Test mode (dummy)'}
          </Badge>
        )}
      </div>

      {!isLoading && data && (
        <p className="text-muted-foreground text-sm">
          Current key ID: {data.razorpay_key_id ?? 'not set'} · Secret:{' '}
          {data.razorpay_key_secret_set ? 'configured' : 'not set'}
        </p>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="max-w-md space-y-4">
        <div className="space-y-2">
          <div className="flex items-center gap-1.5">
            <Label htmlFor="razorpay_key_id">Key ID</Label>
            <Tooltip>
              <TooltipTrigger>
                <Info className="text-muted-foreground size-3.5" aria-label="Key ID help" />
              </TooltipTrigger>
              <TooltipContent>
                Found in your Razorpay Dashboard under Settings → API Keys.
              </TooltipContent>
            </Tooltip>
          </div>
          <Input
            id="razorpay_key_id"
            placeholder="rzp_test_xxxxxxxx"
            {...register('razorpay_key_id')}
          />
          {errors.razorpay_key_id && (
            <p className="text-destructive text-sm">{errors.razorpay_key_id.message}</p>
          )}
        </div>
        <div className="space-y-2">
          <div className="flex items-center gap-1.5">
            <Label htmlFor="razorpay_key_secret">Key secret</Label>
            <Tooltip>
              <TooltipTrigger>
                <Info className="text-muted-foreground size-3.5" aria-label="Key secret help" />
              </TooltipTrigger>
              <TooltipContent>
                Generated alongside the Key ID in the same place -- Razorpay only shows it once, so
                you may need to regenerate it if you've lost it.
              </TooltipContent>
            </Tooltip>
          </div>
          <Input
            id="razorpay_key_secret"
            type="password"
            placeholder="Leave any value for now if you don't have real keys yet"
            {...register('razorpay_key_secret')}
          />
          {errors.razorpay_key_secret && (
            <p className="text-destructive text-sm">{errors.razorpay_key_secret.message}</p>
          )}
        </div>
        {update.isError && (
          <p className="text-destructive text-sm">Failed to save. Please try again.</p>
        )}
        <Button type="submit" disabled={update.isPending}>
          {update.isPending ? 'Saving…' : 'Save payment settings'}
        </Button>
      </form>
    </Card>
  )
}

function WhatsAppSettingsSection() {
  const { data, isLoading } = useWhatsAppSettings()
  const { data: appointmentSettings } = useAppointmentSettings()
  const [justSaved, setJustSaved] = useState(false)

  const handleSaved = () => {
    setJustSaved(true)
    setTimeout(() => setJustSaved(false), 4000)
  }

  const tone = data?.connection_status === 'connected' ? 'green' : 'gray'

  return (
    <Card className="space-y-4 p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-medium">WhatsApp</h2>
          <p className="text-muted-foreground text-sm">
            Connects your WhatsApp Business phone number for customer chat.
          </p>
        </div>
        {!isLoading && data && <Badge tone={tone}>{data.connection_status}</Badge>}
      </div>

      {!isLoading && data && (
        <p className="text-muted-foreground text-sm">
          Phone number ID: {data.phone_number_id ?? 'not set'} · Access token:{' '}
          {data.access_token_set ? 'configured' : 'not set'}
        </p>
      )}

      <div className="flex items-center gap-3">
        <ConnectWhatsAppButton data={data} onSaved={handleSaved} />
      </div>
      {justSaved && <SavedIndicator message="Saved and connected" />}

      <TestWhatsAppMessageCard disabled={!data?.access_token_set} />
      <WhatsAppFlowSetupCard disabled={!data?.access_token_set} />
      {appointmentSettings?.appointment_booking_enabled && (
        <AppointmentFlowSetupCard disabled={!data?.access_token_set} />
      )}
    </Card>
  )
}

function AppointmentBookingSettingsSection() {
  const { data, isLoading } = useAppointmentSettings()
  const update = useUpdateAppointmentSettings()
  const [justSaved, setJustSaved] = useState(false)

  const onCheckedChange = (checked: boolean) => {
    update.mutate(checked, {
      onSuccess: () => {
        setJustSaved(true)
        setTimeout(() => setJustSaved(false), 4000)
      },
    })
  }

  return (
    <Card className="space-y-4 p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-medium">Appointment booking</h2>
          <p className="text-muted-foreground text-sm">
            Let customers book a time slot on WhatsApp instead of -- or alongside -- placing an
            order.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Switch
            id="appointment_booking_enabled"
            aria-label="Enable appointment booking"
            checked={data?.appointment_booking_enabled ?? false}
            disabled={isLoading || update.isPending}
            onCheckedChange={onCheckedChange}
          />
        </div>
      </div>

      {update.isError && (
        <p className="text-destructive text-sm">Failed to save. Please try again.</p>
      )}
      {justSaved && !update.isPending && <SavedIndicator message="Saved" />}
    </Card>
  )
}

const DAY_LABELS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

interface DayRow {
  enabled: boolean
  start_time: string
  end_time: string
  slot_duration_minutes: number
  buffer_minutes: number
}

function defaultDayRow(): DayRow {
  return {
    enabled: false,
    start_time: '09:00',
    end_time: '17:00',
    slot_duration_minutes: 30,
    buffer_minutes: 0,
  }
}

// react-hook-form-free on purpose: 7 independent rows toggled in and out
// of the submitted payload is simpler as plain local state than a form
// array, and nothing here needs field-level validation beyond the native
// <input type="time"> constraint.
function AppointmentAvailabilitySettingsSection() {
  const { data, isLoading } = useAppointmentAvailability()
  const update = useUpdateAppointmentAvailability()
  const [timezone, setTimezone] = useState('Asia/Kolkata')
  const [days, setDays] = useState<DayRow[]>(() => Array.from({ length: 7 }, defaultDayRow))
  const [justSaved, setJustSaved] = useState(false)

  useEffect(() => {
    if (!data) return
    setTimezone(data.timezone)
    setDays((prev) =>
      prev.map((_row, dayOfWeek) => {
        const window = data.windows.find((w) => w.day_of_week === dayOfWeek)
        if (!window) return { ...defaultDayRow() }
        return {
          enabled: true,
          start_time: window.start_time.slice(0, 5),
          end_time: window.end_time.slice(0, 5),
          slot_duration_minutes: window.slot_duration_minutes,
          buffer_minutes: window.buffer_minutes,
        }
      }),
    )
  }, [data])

  function updateDay(index: number, patch: Partial<DayRow>) {
    setDays((prev) => prev.map((row, i) => (i === index ? { ...row, ...patch } : row)))
  }

  function onSave() {
    update.mutate(
      {
        timezone,
        windows: days
          .map((row, day_of_week) => ({ row, day_of_week }))
          .filter(({ row }) => row.enabled)
          .map(({ row, day_of_week }) => ({
            day_of_week,
            start_time: `${row.start_time}:00`,
            end_time: `${row.end_time}:00`,
            slot_duration_minutes: row.slot_duration_minutes,
            buffer_minutes: row.buffer_minutes,
          })),
      },
      {
        onSuccess: () => {
          setJustSaved(true)
          setTimeout(() => setJustSaved(false), 4000)
        },
      },
    )
  }

  return (
    <Card className="space-y-4 p-6">
      <div>
        <h2 className="text-lg font-medium">Appointment availability</h2>
        <p className="text-muted-foreground text-sm">
          Working hours the booking page and WhatsApp Flow offer slots from. A day left off (toggle
          disabled) shows no slots at all -- customers can't book a time you haven't opened up.
        </p>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground text-sm">Loading…</p>
      ) : (
        <div className="space-y-4">
          <div className="max-w-xs space-y-2">
            <Label htmlFor="appointment_timezone">Timezone (IANA name)</Label>
            <Input
              id="appointment_timezone"
              placeholder="Asia/Kolkata"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            {days.map((row, index) => (
              // Fixed 7-day week -- DAY_LABELS[index] is a stable, unique key.
              <div
                key={DAY_LABELS[index]}
                className="flex flex-wrap items-center gap-3 border-t pt-3 first:border-t-0 first:pt-0"
              >
                <div className="flex w-32 items-center gap-2">
                  <Switch
                    id={`day_${index}_enabled`}
                    checked={row.enabled}
                    onCheckedChange={(checked) => updateDay(index, { enabled: checked })}
                  />
                  <Label htmlFor={`day_${index}_enabled`} className="text-sm">
                    {DAY_LABELS[index]}
                  </Label>
                </div>
                {row.enabled && (
                  <div className="flex flex-wrap items-center gap-2">
                    <Input
                      type="time"
                      aria-label={`${DAY_LABELS[index]} start time`}
                      value={row.start_time}
                      onChange={(e) => updateDay(index, { start_time: e.target.value })}
                      className="h-8 w-28"
                    />
                    <span className="text-muted-foreground text-sm">to</span>
                    <Input
                      type="time"
                      aria-label={`${DAY_LABELS[index]} end time`}
                      value={row.end_time}
                      onChange={(e) => updateDay(index, { end_time: e.target.value })}
                      className="h-8 w-28"
                    />
                    <Input
                      type="number"
                      min={5}
                      aria-label={`${DAY_LABELS[index]} slot duration minutes`}
                      value={row.slot_duration_minutes}
                      onChange={(e) =>
                        updateDay(index, { slot_duration_minutes: Number(e.target.value) || 5 })
                      }
                      className="h-8 w-24"
                    />
                    <span className="text-muted-foreground text-sm">min slots</span>
                    <Input
                      type="number"
                      min={0}
                      aria-label={`${DAY_LABELS[index]} buffer minutes`}
                      value={row.buffer_minutes}
                      onChange={(e) =>
                        updateDay(index, { buffer_minutes: Number(e.target.value) || 0 })
                      }
                      className="h-8 w-24"
                    />
                    <span className="text-muted-foreground text-sm">min buffer</span>
                  </div>
                )}
              </div>
            ))}
          </div>

          {update.isError && (
            <p className="text-destructive text-sm">Failed to save. Please try again.</p>
          )}
          <div className="flex items-center gap-3">
            <Button type="button" onClick={onSave} disabled={update.isPending}>
              {update.isPending ? 'Saving…' : 'Save availability'}
            </Button>
            {justSaved && !update.isPending && <SavedIndicator message="Saved" />}
          </div>
        </div>
      )}
    </Card>
  )
}

const templateSchema = z.object({
  template_name: z.string().min(1, 'Required'),
  language_code: z.string().min(1, 'Required'),
  body: z.string().min(1, 'Required'),
})
type TemplateForm = z.infer<typeof templateSchema>

const KIND_LABELS: Record<NotificationTemplateOut['notification_kind'], string> = {
  order_confirmed: 'Order confirmed',
  order_processing: 'Order processing',
  order_ready: 'Order ready',
  order_completed: 'Order completed',
  appointment_confirmed: 'Appointment confirmed',
  appointment_cancelled: 'Appointment cancelled',
}

const KIND_DESCRIPTIONS: Record<NotificationTemplateOut['notification_kind'], string> = {
  order_confirmed: "Sent right after checkout, once the customer's order is placed.",
  order_processing: 'Sent the moment staff mark the order Processing.',
  order_ready: 'Sent the moment staff mark the order Ready for pickup/delivery.',
  order_completed: 'Sent once staff mark the order Completed.',
  appointment_confirmed: 'Sent when staff confirm a requested appointment.',
  appointment_cancelled: 'Sent when staff cancel an appointment.',
}

const ORDER_TEMPLATE_VARIABLES = [
  '{{business_name}}',
  '{{customer_name}}',
  '{{order_id}}',
  '{{total}}',
  '{{currency}}',
]

const APPOINTMENT_TEMPLATE_VARIABLES = [
  '{{business_name}}',
  '{{customer_name}}',
  '{{appointment_date}}',
  '{{appointment_time}}',
]

function templateVariablesFor(kind: NotificationTemplateOut['notification_kind']): string[] {
  return kind === 'appointment_confirmed' || kind === 'appointment_cancelled'
    ? APPOINTMENT_TEMPLATE_VARIABLES
    : ORDER_TEMPLATE_VARIABLES
}

function TemplateRow({ template }: { template: NotificationTemplateOut }) {
  const update = useUpdateNotificationTemplate()
  const [isActive, setIsActive] = useState(template.is_active)
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<TemplateForm>({
    resolver: zodResolver(templateSchema),
    values: {
      template_name: template.template_name,
      language_code: template.language_code || 'en',
      body: template.body,
    },
  })

  const onSubmit = (values: TemplateForm) => {
    update.mutate({ notification_kind: template.notification_kind, ...values, is_active: isActive })
  }

  const badgeTone = !template.is_configured ? 'gray' : template.is_active ? 'green' : 'amber'
  const badgeLabel = !template.is_configured
    ? 'Using default'
    : template.is_active
      ? 'Active'
      : 'Inactive'

  return (
    <div className="space-y-3 border-t pt-6 first:border-t-0 first:pt-0">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="font-medium">{KIND_LABELS[template.notification_kind]}</h3>
          <p className="text-muted-foreground text-xs">
            {KIND_DESCRIPTIONS[template.notification_kind]}
          </p>
        </div>
        <Badge tone={badgeTone}>{badgeLabel}</Badge>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="max-w-lg space-y-3">
        <div className="grid grid-cols-[1fr_100px] gap-3">
          <div className="space-y-1.5">
            <Label htmlFor={`${template.notification_kind}_template_name`}>Template name</Label>
            <Input
              id={`${template.notification_kind}_template_name`}
              placeholder={`${template.notification_kind}_v1`}
              {...register('template_name')}
            />
            {errors.template_name && (
              <p className="text-destructive text-sm">{errors.template_name.message}</p>
            )}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={`${template.notification_kind}_language_code`}>Language</Label>
            <Input
              id={`${template.notification_kind}_language_code`}
              {...register('language_code')}
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor={`${template.notification_kind}_body`}>Message</Label>
          <Textarea id={`${template.notification_kind}_body`} rows={3} {...register('body')} />
          {errors.body && <p className="text-destructive text-sm">{errors.body.message}</p>}
          <p className="text-muted-foreground text-xs">
            Variables: {templateVariablesFor(template.notification_kind).join(', ')}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Switch
            id={`${template.notification_kind}_is_active`}
            checked={isActive}
            onCheckedChange={setIsActive}
          />
          <Label htmlFor={`${template.notification_kind}_is_active`}>
            Use this template instead of the default message
          </Label>
        </div>

        {update.isError && (
          <p className="text-destructive text-sm">Failed to save. Please try again.</p>
        )}
        <Button type="submit" size="sm" disabled={update.isPending}>
          {update.isPending ? 'Saving…' : 'Save'}
        </Button>
      </form>
    </div>
  )
}

function TemplatesSettingsSection() {
  const { data: templates, isLoading } = useNotificationTemplates()

  return (
    <Card className="space-y-6 p-6">
      <div>
        <h2 className="text-lg font-medium">Message templates</h2>
        <p className="text-muted-foreground text-sm">
          Customize what customers receive over WhatsApp for each order event. Leave a template
          inactive to keep using the built-in default message.
        </p>
      </div>

      {isLoading && <p className="text-muted-foreground text-sm">Loading…</p>}
      {templates?.map((template) => (
        <TemplateRow key={template.notification_kind} template={template} />
      ))}
    </Card>
  )
}

export function SettingsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings"
        description="Test/dummy values work fine for now -- switching to real credentials later doesn't require any code changes."
      />
      <PaymentSettingsSection />
      <WhatsAppSettingsSection />
      <AppointmentBookingSettingsSection />
      <AppointmentAvailabilitySettingsSection />
      <TemplatesSettingsSection />
    </div>
  )
}
