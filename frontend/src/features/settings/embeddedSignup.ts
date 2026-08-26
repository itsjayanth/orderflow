export interface EmbeddedSignupResult {
  code: string
  wabaId: string
  phoneNumberId: string
}

declare global {
  interface Window {
    FB?: {
      init: (params: {
        appId: string
        autoLogAppEvents: boolean
        xfbml: boolean
        version: string
      }) => void
      login: (
        callback: (response: { authResponse?: { code?: string } }) => void,
        params: Record<string, unknown>,
      ) => void
    }
    fbAsyncInit?: () => void
  }
}

const SDK_SRC = 'https://connect.facebook.net/en_US/sdk.js'
const SDK_ELEMENT_ID = 'facebook-jssdk'

let sdkLoadPromise: Promise<void> | null = null

function loadFacebookSdk(appId: string, graphApiVersion: string): Promise<void> {
  if (window.FB) return Promise.resolve()
  if (sdkLoadPromise) return sdkLoadPromise

  sdkLoadPromise = new Promise((resolve, reject) => {
    window.fbAsyncInit = () => {
      window.FB?.init({ appId, autoLogAppEvents: true, xfbml: true, version: graphApiVersion })
      resolve()
    }
    if (document.getElementById(SDK_ELEMENT_ID)) return
    const script = document.createElement('script')
    script.id = SDK_ELEMENT_ID
    script.src = SDK_SRC
    script.async = true
    script.defer = true
    script.onerror = () => reject(new Error('Failed to load the Facebook SDK'))
    document.body.appendChild(script)
  })
  return sdkLoadPromise
}

interface SignupMessageData {
  type?: string
  event?: 'FINISH' | 'CANCEL' | 'ERROR'
  data?: {
    phone_number_id?: string
    waba_id?: string
    error_message?: string
    current_step?: string
  }
}

const FACEBOOK_MESSAGE_ORIGINS = new Set(['https://www.facebook.com', 'https://web.facebook.com'])

/**
 * Launches Meta's Facebook Login for Business / WhatsApp Embedded Signup
 * popup and resolves once both halves of the flow -- FB.login's own
 * `code` callback and the SDK's WA_EMBEDDED_SIGNUP postMessage event
 * carrying waba_id/phone_number_id -- have arrived. Meta delivers these on
 * two independent channels with no guaranteed order, so this waits for
 * both before resolving.
 */
export function launchEmbeddedSignup(params: {
  appId: string
  configId: string
  graphApiVersion: string
}): Promise<EmbeddedSignupResult> {
  return loadFacebookSdk(params.appId, params.graphApiVersion).then(
    () =>
      new Promise<EmbeddedSignupResult>((resolve, reject) => {
        let code: string | undefined
        let wabaId: string | undefined
        let phoneNumberId: string | undefined
        let settled = false

        const finish = () => {
          if (settled || !code || !wabaId || !phoneNumberId) return
          settled = true
          window.removeEventListener('message', onMessage)
          resolve({ code, wabaId, phoneNumberId })
        }

        const fail = (message: string) => {
          if (settled) return
          settled = true
          window.removeEventListener('message', onMessage)
          reject(new Error(message))
        }

        const onMessage = (event: MessageEvent) => {
          if (!FACEBOOK_MESSAGE_ORIGINS.has(event.origin)) return
          let data: SignupMessageData
          try {
            data = JSON.parse(event.data as string)
          } catch {
            return
          }
          if (data.type !== 'WA_EMBEDDED_SIGNUP') return
          if (data.event === 'FINISH') {
            wabaId = data.data?.waba_id
            phoneNumberId = data.data?.phone_number_id
            finish()
          } else if (data.event === 'CANCEL') {
            fail('WhatsApp connection cancelled.')
          } else if (data.event === 'ERROR') {
            fail(data.data?.error_message ?? 'WhatsApp connection failed.')
          }
        }
        window.addEventListener('message', onMessage)

        if (!window.FB) {
          fail('The Facebook SDK failed to load.')
          return
        }

        window.FB.login(
          (response) => {
            if (!response.authResponse?.code) {
              fail('Facebook login was cancelled or did not return an authorization code.')
              return
            }
            code = response.authResponse.code
            finish()
          },
          {
            config_id: params.configId,
            response_type: 'code',
            override_default_response_type: true,
            extras: { setup: {}, featureType: '', sessionInfoVersion: '3' },
          },
        )
      }),
  )
}
