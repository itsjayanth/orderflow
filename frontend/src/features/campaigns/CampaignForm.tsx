import { zodResolver } from '@hookform/resolvers/zod'
import { Controller, useForm } from 'react-hook-form'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { ApiError } from '@/shared/api/client'
import type { AudienceFilter, MessageTemplateOut } from '@/shared/api/types'

import { useCreateCampaign } from './useCampaigns'
import { useTemplates } from './useTemplates'

type AudienceKind = AudienceFilter['kind']
type ScheduleKind = 'now' | 'later'

const campaignFormSchema = z
  .object({
    name: z.string().min(1, 'Required').max(255),
    template_id: z.string().min(1, 'Select a template'),
    audience_kind: z.enum(['all', 'ordered_within_days', 'no_order_within_days']),
    audience_days: z.string().optional(),
    schedule_kind: z.enum(['now', 'later']),
    scheduled_at: z.string().optional(),
  })
  .refine(
    (data) =>
      data.audience_kind === 'all' || (!!data.audience_days && Number(data.audience_days) > 0),
    { message: 'Enter a number of days', path: ['audience_days'] },
  )
  .refine((data) => data.schedule_kind === 'now' || !!data.scheduled_at, {
    message: 'Pick a date and time',
    path: ['scheduled_at'],
  })

type CampaignFormValues = z.infer<typeof campaignFormSchema>

export function buildAudienceFilter(values: CampaignFormValues): AudienceFilter {
  if (values.audience_kind === 'all') return { kind: 'all' }
  return { kind: values.audience_kind, days: Number(values.audience_days) }
}

export function isTemplateSelectable(template: MessageTemplateOut): boolean {
  return template.meta_approval_status === 'approved'
}

export function templateDisabledReason(template: MessageTemplateOut): string {
  if (template.meta_approval_status === 'pending') return 'Still awaiting Meta approval'
  if (template.meta_approval_status === 'rejected') return 'Rejected by Meta'
  return 'Not currently sendable'
}

export function CampaignForm({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { data: templates } = useTemplates()
  const createCampaign = useCreateCampaign()

  const {
    register,
    control,
    handleSubmit,
    watch,
    reset,
    formState: { errors },
  } = useForm<CampaignFormValues>({
    resolver: zodResolver(campaignFormSchema),
    defaultValues: { audience_kind: 'all', schedule_kind: 'now' },
  })
  const audienceKind: AudienceKind = watch('audience_kind')
  const scheduleKind: ScheduleKind = watch('schedule_kind')

  const onSubmit = (data: CampaignFormValues) => {
    createCampaign.mutate(
      {
        name: data.name,
        template_id: data.template_id,
        audience_filter: buildAudienceFilter(data),
        scheduled_at:
          data.schedule_kind === 'later' && data.scheduled_at
            ? new Date(data.scheduled_at).toISOString()
            : undefined,
      },
      {
        onSuccess: () => {
          reset({ audience_kind: 'all', schedule_kind: 'now' })
          onOpenChange(false)
        },
      },
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New campaign</DialogTitle>
          <DialogDescription>
            Send an approved WhatsApp template to a segment of your customers.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="campaign_name">Campaign name</Label>
            <Input id="campaign_name" placeholder="e.g. Weekend Promo" {...register('name')} />
            {errors.name && <p className="text-destructive text-sm">{errors.name.message}</p>}
          </div>

          <div className="space-y-2">
            <Label htmlFor="template_id">Template</Label>
            <Controller
              name="template_id"
              control={control}
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="template_id" onBlur={field.onBlur}>
                    <SelectValue placeholder="Select an approved template…" />
                  </SelectTrigger>
                  <SelectContent>
                    {templates?.map((template) => {
                      const selectable = isTemplateSelectable(template)
                      const item = (
                        <SelectItem
                          key={template.template_id}
                          value={template.template_id}
                          disabled={!selectable}
                        >
                          {template.name}
                        </SelectItem>
                      )
                      if (selectable) return item
                      return (
                        <Tooltip key={template.template_id}>
                          <TooltipTrigger asChild>
                            <span>{item}</span>
                          </TooltipTrigger>
                          <TooltipContent>{templateDisabledReason(template)}</TooltipContent>
                        </Tooltip>
                      )
                    })}
                  </SelectContent>
                </Select>
              )}
            />
            {errors.template_id && (
              <p className="text-destructive text-sm">{errors.template_id.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="audience_kind">Audience</Label>
            <Controller
              name="audience_kind"
              control={control}
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="audience_kind" onBlur={field.onBlur}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All customers</SelectItem>
                    <SelectItem value="ordered_within_days">Ordered in the last N days</SelectItem>
                    <SelectItem value="no_order_within_days">
                      No order in the last N days
                    </SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
            {audienceKind !== 'all' && (
              <div className="pt-1">
                <Input
                  type="number"
                  min={1}
                  placeholder="Days"
                  aria-label="Number of days"
                  {...register('audience_days')}
                />
                {errors.audience_days && (
                  <p className="text-destructive text-sm">{errors.audience_days.message}</p>
                )}
              </div>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="schedule_kind">Send</Label>
            <Controller
              name="schedule_kind"
              control={control}
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="schedule_kind" onBlur={field.onBlur}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="now">Send now</SelectItem>
                    <SelectItem value="later">Schedule for later</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
            {scheduleKind === 'later' && (
              <div className="pt-1">
                <Input
                  type="datetime-local"
                  aria-label="Scheduled date and time"
                  {...register('scheduled_at')}
                />
                {errors.scheduled_at && (
                  <p className="text-destructive text-sm">{errors.scheduled_at.message}</p>
                )}
              </div>
            )}
          </div>

          {createCampaign.isError && (
            <p className="text-destructive text-sm">
              {createCampaign.error instanceof ApiError
                ? createCampaign.error.message || 'Something went wrong. Please try again.'
                : 'Something went wrong.'}
            </p>
          )}

          <DialogFooter>
            <Button type="submit" disabled={createCampaign.isPending}>
              {createCampaign.isPending ? 'Creating…' : 'Create campaign'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
