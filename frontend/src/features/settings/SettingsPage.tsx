import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

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

function Badge({ tone, children }: { tone: 'green' | 'amber' | 'gray'; children: string }) {
  const toneClasses = {
    green: 'bg-green-100 text-green-800',
    amber: 'bg-amber-100 text-amber-800',
    gray: 'bg-muted text-muted-foreground',
  }[tone]
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${toneClasses}`}>
      {children}
    </span>
  )
}

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
    <section className="space-y-4 rounded-md border p-4">
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
    </section>
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
    <section className="space-y-4 rounded-md border p-4">
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
    </section>
  )
}

export function SettingsPage() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-muted-foreground text-sm">
          Test/dummy values work fine for now -- switching to real credentials later doesn't require
          any code changes.
        </p>
      </div>
      <PaymentSettingsSection />
      <WhatsAppSettingsSection />
    </div>
  )
}
