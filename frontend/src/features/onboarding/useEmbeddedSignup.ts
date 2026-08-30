import { useCallback, useEffect, useRef, useState } from 'react'

import { useEmbeddedSignup as useEmbeddedSignupMutation } from '@/features/settings/useWhatsAppSettings'
import { ApiError } from '@/shared/api/client'
import type { EmbeddedSignupResult } from '@/shared/api/types'

import type { FacebookLoginResponse } from './useFacebookSdk'

// Ported from FastFlow's Phase 7 reference implementation
// (fastflow/frontend/src/hooks/useEmbeddedSignup.ts), trimmed to what
// orderflow needs: no Coexistence phase and no phone-number-mismatch
// warning card -- both guard fastflow-specific BYOT-migration concerns
// (see backend/src/onboarding/domain/embedded_signup.py's module
// docstring for why). What's kept: the `message` event listener with a
// strict hostname allowlist (AC2 in fastflow's story 7.6 -- `new
// URL(event.origin).hostname`, not a raw `endsWith` on the origin string,
// which a domain like "evilfacebook.com" would pass) and forwarding the
// popup's code to the backend the instant it arrives, no intervening
// click (a ~30s TTL at Meta means waiting for a second user action can
// lose the race).

export type EmbeddedSignupPhase = 'idle' | 'awaiting_popup' | 'processing' | 'error'

interface EmbeddedSignupSessionData {
  waba_id?: string | null
  phone_number_id?: string | null
  business_id?: string | null
}

const ALLOWED_ORIGIN_HOSTS = (hostname: string) =>
  hostname === 'facebook.com' || hostname.endsWith('.facebook.com')

export function useEmbeddedSignup(onCompleted: (result: EmbeddedSignupResult) => void) {
  const [phase, setPhase] = useState<EmbeddedSignupPhase>('idle')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const mutation = useEmbeddedSignupMutation()

  // Session data captured off the `message` event -- read (not driven) by
  // handleFbResponse when FB.login's own callback fires with the code.
  const sessionRef = useRef<{ event?: string; data?: EmbeddedSignupSessionData } | null>(null)

  useEffect(() => {
    function handleMessage(event: MessageEvent) {
      let hostname: string
      try {
        hostname = new URL(event.origin).hostname
      } catch {
        return
      }
      if (!ALLOWED_ORIGIN_HOSTS(hostname)) return

      let payload: unknown
      try {
        payload = typeof event.data === 'string' ? JSON.parse(event.data) : event.data
      } catch {
        return
      }
      if (!payload || typeof payload !== 'object') return
      const parsed = payload as { type?: string; event?: string; data?: EmbeddedSignupSessionData }
      if (parsed.type !== 'WA_EMBEDDED_SIGNUP') return

      sessionRef.current = { event: parsed.event, data: parsed.data }
    }

    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [])

  const reset = useCallback(() => {
    sessionRef.current = null
    setErrorMessage(null)
    setPhase('idle')
  }, [])

  const submit = useCallback(
    (code: string, data: EmbeddedSignupSessionData | undefined, event: string) => {
      setPhase('processing')
      mutation.mutate(
        {
          code,
          waba_id: data?.waba_id ?? null,
          phone_number_id: data?.phone_number_id ?? null,
          business_id: data?.business_id ?? null,
          event,
          // Same convention as useWhatsAppSettings.ts's useSetupWhatsAppFlow --
          // the WABA webhook subscription needs this deployment's own public
          // URL because the Meta App is shared with fastflow/ORDZO (see
          // backend/src/shared/config.py's meta_app_id docstring).
          backend_base_url: import.meta.env.VITE_API_URL ?? 'http://localhost:8000',
        },
        {
          onSuccess: (result) => {
            if (result.status === 'connected') {
              setPhase('idle')
              onCompleted(result)
            } else {
              // The merchant cancelled server-side, or the event wasn't
              // one we proceed on -- not an error.
              reset()
            }
          },
          onError: (err) => {
            const message =
              err instanceof ApiError
                ? 'Something went wrong completing setup. Please try again.'
                : 'Network error while completing setup. Please try again.'
            setErrorMessage(message)
            setPhase('error')
          },
        },
      )
    },
    [mutation, onCompleted, reset],
  )

  /** Passed to FB.login as its callback. */
  const handleFbResponse = useCallback(
    (response: FacebookLoginResponse) => {
      const code = response?.authResponse?.code
      const captured = sessionRef.current

      if (!code) {
        // Popup closed / CANCEL / SDK unavailable -- not an error.
        reset()
        return
      }

      submit(code, captured?.data, captured?.event ?? 'FINISH')
    },
    [reset, submit],
  )

  const begin = useCallback(() => {
    sessionRef.current = null
    setErrorMessage(null)
    setPhase('awaiting_popup')
  }, [])

  return { phase, errorMessage, begin, handleFbResponse, reset }
}
