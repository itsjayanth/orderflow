import { zodResolver } from '@hookform/resolvers/zod'
import { CalendarClock, Plus, Trash2 } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import {
  useAppointmentServices,
  useCreateAppointmentService,
  useDeleteAppointmentService,
  useUpdateAppointmentService,
} from '@/features/settings/useAppointmentServices'
import type { AppointmentServiceSettingsOut } from '@/shared/api/types'
import { EmptyState } from '@/shared/components/EmptyState'
import { PageHeader } from '@/shared/components/PageHeader'

function ServiceRow({ service }: { service: AppointmentServiceSettingsOut }) {
  const update = useUpdateAppointmentService()
  const remove = useDeleteAppointmentService()

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t px-5 py-4 first:border-t-0">
      <div>
        <p className="text-sm font-medium">{service.name}</p>
        <p className="text-muted-foreground text-xs">
          {service.duration_minutes} min{service.price ? ` · ${service.price}` : ''}
        </p>
      </div>
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <Switch
            id={`service_${service.service_id}_active`}
            checked={service.is_active}
            onCheckedChange={(checked) =>
              update.mutate({ serviceId: service.service_id, is_active: checked })
            }
          />
          <Label htmlFor={`service_${service.service_id}_active`} className="text-xs">
            Active
          </Label>
        </div>
        <Button
          type="button"
          size="icon"
          variant="outline"
          aria-label={`Delete ${service.name}`}
          disabled={remove.isPending}
          onClick={() => remove.mutate(service.service_id)}
        >
          <Trash2 className="size-4" />
        </Button>
      </div>
    </div>
  )
}

const newServiceSchema = z.object({
  name: z.string().trim().min(1, 'Required'),
  duration_minutes: z.number().int().positive('Must be greater than 0'),
  price: z.string().trim().optional(),
})
type NewServiceForm = z.infer<typeof newServiceSchema>

export function ServicesPage() {
  const { data: services, isLoading } = useAppointmentServices()
  const create = useCreateAppointmentService()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<NewServiceForm>({ resolver: zodResolver(newServiceSchema) })

  const onSubmit = (values: NewServiceForm) => {
    create.mutate(
      {
        name: values.name,
        duration_minutes: values.duration_minutes,
        price: values.price || null,
      },
      { onSuccess: () => reset() },
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Services"
        description={
          'Optional -- shown as a "what are you booking?" step before the customer picks a time. ' +
          'Leave this empty and customers can still book a generic time slot with you.'
        }
      />

      {!isLoading && services?.length === 0 && (
        <EmptyState icon={CalendarClock} title="No services yet. Add one below." />
      )}

      {services && services.length > 0 && (
        <Card className="overflow-hidden py-0">
          {services.map((service) => (
            <ServiceRow key={service.service_id} service={service} />
          ))}
        </Card>
      )}

      <Card className="max-w-md">
        <CardHeader>
          <CardTitle>Add service</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="new_service_name">Name</Label>
              <Input id="new_service_name" placeholder="Haircut" {...register('name')} />
              {errors.name && <p className="text-destructive text-sm">{errors.name.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="new_service_duration">Duration (minutes)</Label>
              <Input
                id="new_service_duration"
                type="number"
                min={5}
                {...register('duration_minutes', { valueAsNumber: true })}
              />
              {errors.duration_minutes && (
                <p className="text-destructive text-sm">{errors.duration_minutes.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="new_service_price">Price (optional)</Label>
              <Input id="new_service_price" placeholder="500.00" {...register('price')} />
            </div>
            {create.isError && (
              <p className="text-destructive text-sm">Failed to add. Please try again.</p>
            )}
            <Button type="submit" disabled={create.isPending}>
              <Plus className="size-4" />
              {create.isPending ? 'Adding…' : 'Add service'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
