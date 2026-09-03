import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useMe } from '@/features/auth/useAuth'
import { ApiError } from '@/shared/api/client'
import { SavedIndicator } from '@/shared/components/SavedIndicator'

import { useUpdateWebsiteLink, useWebsiteLinkClickStats } from './useWebsiteLink'

// apiFetch throws the raw response body as the ApiError message. A 422 from
// a malformed URL carries a JSON `detail` string from the backend -- surface
// that verbatim rather than a generic failure message.
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
  return 'Failed to save. Please try again.'
}

// Renders for every merchant regardless of vertical (unlike the
// appointment-only availability section) -- the "Visit website" WhatsApp
// menu option applies equally to restaurant and appointment merchants.
export function WebsiteLinkSettingsSection() {
  const { data: me } = useMe()
  const updateWebsiteLink = useUpdateWebsiteLink()
  const [websiteUrl, setWebsiteUrl] = useState('')
  const [justSaved, setJustSaved] = useState(false)

  useEffect(() => {
    if (!me) return
    setWebsiteUrl(me.merchant.website_url ?? '')
  }, [me])

  const hasSavedUrl = Boolean(me?.merchant.website_url)
  const clickStats = useWebsiteLinkClickStats(7, hasSavedUrl)

  function onSave() {
    updateWebsiteLink.mutate(
      { website_url: websiteUrl.trim() || null },
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
        <h2 className="text-lg font-medium">Website link</h2>
        <p className="text-muted-foreground text-sm">
          Optional. When set, customers see a "Visit website" option in the WhatsApp menu. Changes
          take effect immediately -- no republish step.
        </p>
      </div>

      <div className="max-w-md space-y-2">
        <Label htmlFor="website_url">Website link</Label>
        <Input
          id="website_url"
          type="text"
          placeholder="https://yourbusiness.com"
          value={websiteUrl}
          onChange={(e) => setWebsiteUrl(e.target.value)}
        />
      </div>

      {hasSavedUrl && clickStats.data && (
        <p className="text-muted-foreground text-sm">
          {clickStats.data.count} people tapped your website link in the last {clickStats.data.days}{' '}
          days.
        </p>
      )}

      {updateWebsiteLink.isError && (
        <p className="text-destructive text-sm">{extractErrorDetail(updateWebsiteLink.error)}</p>
      )}
      <div className="flex items-center gap-3">
        <Button type="button" onClick={onSave} disabled={updateWebsiteLink.isPending}>
          {updateWebsiteLink.isPending ? 'Saving…' : 'Save website link'}
        </Button>
        {justSaved && !updateWebsiteLink.isPending && <SavedIndicator message="Saved" />}
      </div>
    </Card>
  )
}
