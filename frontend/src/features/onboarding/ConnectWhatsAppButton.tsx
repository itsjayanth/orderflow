import { zodResolver } from '@hookform/resolvers/zod'
import { Info } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useUpdateWhatsAppSettings } from '@/features/settings/useWhatsAppSettings'
import type { WhatsAppSettingsOut } from '@/shared/api/types'

import { useEmbeddedSignup } from './useEmbeddedSignup'
import { useFacebookSdk } from './useFacebookSdk'

// Meta App ID / config_id are not secrets (safe to expose to the browser --
// see frontend/.env.example) -- unset in a deployment that hasn't
// registered a Meta App yet, in which case this whole component falls
// back to manual-entry-only, same as before this flow existed.
const META_APP_ID = import.meta.env.VITE_META_APP_ID as string | undefined
const META_ES_CONFIG_ID = import.meta.env.VITE_META_ES_CONFIG_ID as string | undefined
const EMBEDDED_SIGNUP_CONFIGURED = Boolean(META_APP_ID && META_ES_CONFIG_ID)

const manualSchema = z.object({
  phone_number_id: z.string().min(1, 'Required'),
  access_token: z.string().min(1, 'Required'),
  display_phone_number: z.string().optional(),
})
type ManualForm = z.infer<typeof manualSchema>

function ManualEntryForm({
  data,
  onSaved,
}: {
  data: WhatsAppSettingsOut | undefined
  onSaved: () => void
}) {
  const update = useUpdateWhatsAppSettings()
  const {
    register,
    handleSubmit,
    resetField,
    formState: { errors },
  } = useForm<ManualForm>({
    resolver: zodResolver(manualSchema),
    values: {
      phone_number_id: data?.phone_number_id ?? '',
      display_phone_number: data?.display_phone_number ?? '',
      access_token: '',
    },
  })

  const onSubmit = (values: ManualForm) => {
    update.mutate(values, {
      onSuccess: () => {
        resetField('access_token')
        onSaved()
      },
    })
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="max-w-md space-y-4">
      <p className="text-muted-foreground text-sm">
        Paste your WhatsApp Business phone number ID and access token directly. Test/dummy values
        work fine for now -- switching to real credentials later doesn't require redoing this step.
      </p>
      <div className="space-y-2">
        <div className="flex items-center gap-1.5">
          <Label htmlFor="phone_number_id">Phone number ID</Label>
          <Tooltip>
            <TooltipTrigger>
              <Info className="text-muted-foreground size-3.5" aria-label="Phone number ID help" />
            </TooltipTrigger>
            <TooltipContent>
              Found on Meta's WhatsApp API Setup page, labeled "Phone number ID" -- not the phone
              number itself.
            </TooltipContent>
          </Tooltip>
        </div>
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
        <div className="flex items-center gap-1.5">
          <Label htmlFor="access_token">Access token</Label>
          <Tooltip>
            <TooltipTrigger>
              <Info className="text-muted-foreground size-3.5" aria-label="Access token help" />
            </TooltipTrigger>
            <TooltipContent>
              A permanent or temporary token generated for your WhatsApp Business app in Meta's
              developer console. Never pre-filled here -- re-paste it to rotate.
            </TooltipContent>
          </Tooltip>
        </div>
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
      <Button type="submit" disabled={update.isPending} variant="secondary">
        {update.isPending ? 'Connecting…' : 'Connect & continue'}
      </Button>
    </form>
  )
}

/** Single "Connect your WhatsApp Business account" button running Meta's
 * Embedded Signup popup, with manual phone_number_id/access_token entry
 * available behind an "Advanced" toggle for BYOT merchants or dummy/test
 * setups. When VITE_META_APP_ID/VITE_META_ES_CONFIG_ID aren't configured
 * (no Meta App registered for this deployment yet), the button is hidden
 * entirely and manual entry is the only path -- unchanged from before this
 * flow existed. */
export function ConnectWhatsAppButton({
  data,
  onSaved,
}: {
  data: WhatsAppSettingsOut | undefined
  onSaved: () => void
}) {
  const fb = useFacebookSdk(META_APP_ID)
  const embeddedSignup = useEmbeddedSignup(() => onSaved())

  const handleConnectClick = () => {
    if (!META_ES_CONFIG_ID) return
    embeddedSignup.begin()
    // Must run synchronously from this click handler -- popup blockers
    // kill FB.login calls made after an await.
    fb.login(META_ES_CONFIG_ID, embeddedSignup.handleFbResponse)
  }

  const busy = embeddedSignup.phase === 'awaiting_popup' || embeddedSignup.phase === 'processing'

  return (
    <div className="max-w-md space-y-4">
      {EMBEDDED_SIGNUP_CONFIGURED ? (
        <>
          <p className="text-muted-foreground text-sm">
            Connect your WhatsApp Business account through Meta -- this sets up your phone number
            and access token automatically, no copy-pasting required.
          </p>
          <Button type="button" onClick={handleConnectClick} disabled={busy || fb.error !== null}>
            {embeddedSignup.phase === 'processing'
              ? 'Connecting…'
              : 'Connect your WhatsApp Business account'}
          </Button>
          {fb.error && <p className="text-destructive text-sm">{fb.error}</p>}
          {embeddedSignup.phase === 'error' && embeddedSignup.errorMessage && (
            <p className="text-destructive text-sm">{embeddedSignup.errorMessage}</p>
          )}
        </>
      ) : (
        <p className="text-muted-foreground text-sm">
          One-click WhatsApp connection isn't set up for this deployment yet -- use manual entry
          below.
        </p>
      )}

      <Accordion
        type="single"
        collapsible
        defaultValue={EMBEDDED_SIGNUP_CONFIGURED ? undefined : 'manual'}
      >
        <AccordionItem value="manual">
          <AccordionTrigger>Advanced: connect manually</AccordionTrigger>
          <AccordionContent>
            <ManualEntryForm data={data} onSaved={onSaved} />
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  )
}
