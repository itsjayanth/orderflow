import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiError } from '@/shared/api/client'
import { SavedIndicator } from '@/shared/components/SavedIndicator'

import { useSetupWhatsAppFlow } from './useWhatsAppSettings'

// apiFetch throws the raw response body as the ApiError message. The backend
// reports which Meta step failed via a JSON `detail` string (400/502) --
// surface that verbatim so a merchant/admin can see what Meta rejected,
// falling back to a generic message if the body isn't JSON for some reason.
function extractErrorDetail(error: unknown): string {
  if (error instanceof ApiError) {
    try {
      const parsed = JSON.parse(error.message) as { detail?: unknown }
      if (typeof parsed.detail === 'string') {
        return parsed.detail
      }
    } catch {
      // Not JSON -- fall through to the generic message below.
    }
  }
  return 'Something went wrong. Please try again.'
}

export function WhatsAppFlowSetupCard({ disabled = false }: { disabled?: boolean }) {
  const [wabaId, setWabaId] = useState('')
  const setupFlow = useSetupWhatsAppFlow()

  const onSetup = () => {
    setupFlow.mutate(wabaId)
  }

  return (
    <div className="max-w-md space-y-3 border-t pt-4">
      <div>
        <h3 className="text-sm font-medium">Enable native WhatsApp ordering</h3>
        <p className="text-muted-foreground text-xs">
          Let customers browse your catalog and order without ever leaving WhatsApp.
        </p>
      </div>

      {setupFlow.isSuccess ? (
        <SavedIndicator message="Native ordering enabled!" />
      ) : (
        <div className="space-y-2">
          <Label htmlFor="meta_waba_id">WhatsApp Business Account ID</Label>
          <div className="flex items-center gap-3">
            <Input
              id="meta_waba_id"
              placeholder="123456789012345"
              value={wabaId}
              onChange={(e) => setWabaId(e.target.value)}
              disabled={disabled}
            />
            <Button
              type="button"
              variant="outline"
              disabled={disabled || !wabaId || setupFlow.isPending}
              onClick={onSetup}
            >
              {setupFlow.isPending ? 'Enabling…' : 'Enable'}
            </Button>
          </div>
          <p className="text-muted-foreground text-xs">
            Find this on Meta's WhatsApp API Setup page, labeled "WhatsApp Business Account ID".
          </p>
        </div>
      )}

      {disabled && (
        <p className="text-muted-foreground text-xs">
          Save your credentials above before enabling native ordering.
        </p>
      )}
      {setupFlow.isError && (
        <p className="text-destructive text-sm">{extractErrorDetail(setupFlow.error)}</p>
      )}
    </div>
  )
}
