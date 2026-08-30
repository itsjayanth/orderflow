import { useCallback, useEffect, useState } from 'react'

// Ported from FastFlow's Phase 7 reference implementation
// (fastflow/frontend/src/hooks/useFacebookSdk.ts) -- lazily loads the
// Facebook JS SDK and exposes a `login()` wrapper around `FB.login`
// shaped for Embedded Signup v4: `config_id`, `response_type: 'code'`,
// `override_default_response_type: true`, `extras: { setup: {} }`. See
// https://developers.facebook.com/docs/whatsapp/embedded-signup for the
// current spec (v2 sunsets 2026-10-15, v3 October 2026 -- this shape is
// v4, not tied to a URL version parameter but to how the config_id itself
// was created in the Meta App Dashboard).
//
// The SDK is injected dynamically (never a static <script> in
// index.html) and only when `appId` is truthy, so a deployment without
// VITE_META_APP_ID configured makes zero requests to connect.facebook.net.

export interface FacebookAuthResponse {
  code?: string
}

export interface FacebookLoginResponse {
  authResponse?: FacebookAuthResponse | null
  status?: string
}

interface FacebookLoginOptions {
  config_id: string
  response_type: 'code'
  override_default_response_type: true
  extras: { setup: Record<string, never> }
}

interface FacebookSdk {
  init: (params: { appId: string; version: string; xfbml: boolean }) => void
  login: (
    callback: (response: FacebookLoginResponse) => void,
    options: FacebookLoginOptions,
  ) => void
}

declare global {
  interface Window {
    FB?: FacebookSdk
    fbAsyncInit?: () => void
  }
}

const SDK_SRC = 'https://connect.facebook.net/en_US/sdk.js'
// Only affects FB.init's own API surface -- independent of the backend's
// META_GRAPH_API_VERSION (shared/config.py), which is what actually
// stamps the REST calls this drives (oauth/access_token, debug_token,
// subscribed_apps, register).
const GRAPH_API_VERSION = 'v22.0'

let sdkLoadPromise: Promise<void> | null = null

function loadFacebookSdk(appId: string): Promise<void> {
  if (typeof window === 'undefined') return Promise.reject(new Error('No window'))
  if (window.FB) return Promise.resolve()
  if (sdkLoadPromise) return sdkLoadPromise

  sdkLoadPromise = new Promise<void>((resolve, reject) => {
    window.fbAsyncInit = () => {
      window.FB?.init({ appId, version: GRAPH_API_VERSION, xfbml: false })
      resolve()
    }

    const existing = document.getElementById('facebook-jssdk')
    if (existing) {
      // Already injected by a previous mount -- fbAsyncInit above will
      // still fire once the SDK finishes loading.
      return
    }

    const script = document.createElement('script')
    script.id = 'facebook-jssdk'
    script.src = SDK_SRC
    script.async = true
    script.defer = true
    script.crossOrigin = 'anonymous'
    script.onerror = () => {
      sdkLoadPromise = null
      reject(new Error('Could not load the Facebook SDK -- check your connection and try again.'))
    }
    document.body.appendChild(script)
  })

  return sdkLoadPromise
}

export function useFacebookSdk(appId: string | undefined) {
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!appId) return
    let cancelled = false
    loadFacebookSdk(appId)
      .then(() => {
        if (cancelled) return
        setReady(true)
        setError(null)
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message)
      })
    return () => {
      cancelled = true
    }
  }, [appId])

  /** Must be invoked synchronously from a click handler -- popup blockers
   * kill `FB.login` calls made after an `await`. */
  const login = useCallback(
    (configId: string, callback: (response: FacebookLoginResponse) => void) => {
      if (!window.FB) {
        callback({ status: 'sdk_unavailable' })
        return
      }
      window.FB.login(callback, {
        config_id: configId,
        response_type: 'code',
        override_default_response_type: true,
        extras: { setup: {} },
      })
    },
    [],
  )

  return { ready, error, login }
}
