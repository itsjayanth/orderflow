import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import type { NotificationTemplateOut } from '@/shared/api/types'

import { useNotificationTemplates, useUpdateNotificationTemplate } from './useNotificationTemplates'
import { usePaymentSettings, useUpdatePaymentSettings } from './usePaymentSettings'
import { useUpdateWhatsAppSettings, useWhatsAppSettings } from './useWhatsAppSettings'

const paymentSchema = z.object({
  razorpay_key_id: z.string().min(1, 'Required'),
  razorpay_key_secret: z.string().min(1, 'Required'),
})
type PaymentForm = z.infer<typeof paymentSchema>

const whatsappSchema = z.object({
  phone_number_id: z.string().min(1, 'Required'),
  access_token: z.string().min(1, 'Required'),
  display_phone_number: z.string().optional(),
})
type WhatsAppForm = z.infer<typeof whatsappSchema>

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
      <div className="flex items-center justify-between">
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
          <Label htmlFor="razorpay_key_id">Key ID</Label>
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
          <Label htmlFor="razorpay_key_secret">Key secret</Label>
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
  const update = useUpdateWhatsAppSettings()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<WhatsAppForm>({ resolver: zodResolver(whatsappSchema) })

  const onSubmit = (values: WhatsAppForm) => {
    update.mutate(values, { onSuccess: () => reset() })
  }

  const tone = data?.connection_status === 'connected' ? 'green' : 'gray'

  return (
    <Card className="space-y-4 p-6">
      <div className="flex items-center justify-between">
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

      <form onSubmit={handleSubmit(onSubmit)} className="max-w-md space-y-4">
        <div className="space-y-2">
          <Label htmlFor="phone_number_id">Phone number ID</Label>
          <Input id="phone_number_id" {...register('phone_number_id')} />
          {errors.phone_number_id && (
            <p className="text-destructive text-sm">{errors.phone_number_id.message}</p>
          )}
        </div>
        <div className="space-y-2">
          <Label htmlFor="display_phone_number">Display phone number (optional)</Label>
          <Input
            id="display_phone_number"
            placeholder="+91 90000 00000"
            {...register('display_phone_number')}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="access_token">Access token</Label>
          <Input
            id="access_token"
            type="password"
            placeholder="Leave any value for now if you don't have a real token yet"
            {...register('access_token')}
          />
          {errors.access_token && (
            <p className="text-destructive text-sm">{errors.access_token.message}</p>
          )}
        </div>
        {update.isError && (
          <p className="text-destructive text-sm">Failed to save. Please try again.</p>
        )}
        <Button type="submit" disabled={update.isPending}>
          {update.isPending ? 'Saving…' : 'Save WhatsApp settings'}
        </Button>
      </form>
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
  order_ready: 'Order ready',
  order_completed: 'Order completed',
}

const KIND_DESCRIPTIONS: Record<NotificationTemplateOut['notification_kind'], string> = {
  order_confirmed: "Sent right after checkout, once the customer's order is placed.",
  order_ready: 'Sent the moment staff mark the order Ready for pickup/delivery.',
  order_completed: 'Sent once staff mark the order Completed.',
}

const TEMPLATE_VARIABLES = [
  '{{business_name}}',
  '{{customer_name}}',
  '{{order_id}}',
  '{{total}}',
  '{{currency}}',
]

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
      <div className="flex items-center justify-between gap-4">
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
            Variables: {TEMPLATE_VARIABLES.join(', ')}
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
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-muted-foreground text-sm">
          Test/dummy values work fine for now -- switching to real credentials later doesn't require
          any code changes.
        </p>
      </div>
      <PaymentSettingsSection />
      <WhatsAppSettingsSection />
      <TemplatesSettingsSection />
    </div>
  )
}
