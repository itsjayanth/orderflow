import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { ApiError } from '@/shared/api/client'
import { SavedIndicator } from '@/shared/components/SavedIndicator'

import { launchEmbeddedSignup } from './embeddedSignup'
import { useCompleteEmbeddedSignup, useEmbeddedSignupConfig } from './useWhatsAppSettings'

function extractErrorDetail(error: unknown): string {
  if (error instanceof ApiError) {
    try {
      const parsed = JSON.parse(error.message) as { detail?: unknown }
      if (typeof parsed.detail === 'string') return parsed.detail
    } catch {
      // Not JSON -- fall through to the generic message below.
    }
  }
  if (error instanceof Error) return error.message
  return 'Something went wrong. Please try again.'
}

/**
 * "Connect WhatsApp" via Meta's Embedded Signup -- an alternative to the
 * manual phone_number_id/access_token form below it, not a replacement.
 * Launches Facebook Login for Business in a popup; on success, hands the
 * returned code + waba_id + phone_number_id to the backend, which does the
 * token exchange and persists credentials onto the same WhatsApp connection
 * record the manual form writes.
 */
export function EmbeddedSignupButton() {
  const { data: config, isLoading: isConfigLoading } = useEmbeddedSignupConfig()
  const completeSignup = useCompleteEmbeddedSignup()
  const [launchError, setLaunchError] = useState<string | null>(null)
  const [isLaunching, setIsLaunching] = useState(false)

  const onConnect = async () => {
    if (!config) return
    setLaunchError(null)
    setIsLaunching(true)
    try {
      const result = await launchEmbeddedSignup({
        appId: config.app_id,
        configId: config.config_id,
        graphApiVersion: config.graph_api_version,
      })
      await completeSignup.mutateAsync({
        code: result.code,
        waba_id: result.wabaId,
        phone_number_id: result.phoneNumberId,
      })
    } catch (error) {
      setLaunchError(error instanceof Error ? error.message : 'WhatsApp connection failed.')
    } finally {
      setIsLaunching(false)
    }
  }

  if (!isConfigLoading && !config?.configured) {
    return (
      <p className="text-muted-foreground text-xs">
        Embedded Signup isn't configured on this server (needs META_APP_ID/META_APP_SECRET/
        META_CONFIGURATION_ID). Use the manual form below instead.
      </p>
    )
  }

  return (
    <div className="space-y-2">
      <Button
        type="button"
        onClick={onConnect}
        disabled={isConfigLoading || isLaunching || completeSignup.isPending}
      >
        {isLaunching || completeSignup.isPending ? 'Connecting…' : 'Connect WhatsApp'}
      </Button>
      {completeSignup.isSuccess && <SavedIndicator message="WhatsApp connected!" />}
      {launchError && <p className="text-destructive text-sm">{launchError}</p>}
      {completeSignup.isError && (
        <p className="text-destructive text-sm">{extractErrorDetail(completeSignup.error)}</p>
      )}
    </div>
  )
}
