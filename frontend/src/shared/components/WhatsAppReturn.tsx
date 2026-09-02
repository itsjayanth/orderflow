import { useCallback, useEffect, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { trackEvent } from '@/shared/lib/analytics'
import {
  buildWaMeUrl,
  buildWhatsAppSchemeUrl,
  getWhatsAppReturnDelayMs,
  isWhatsAppReturnEnabled,
  normalizeWhatsAppNumber,
} from '@/shared/lib/whatsappReturn'

export type WhatsAppReturnFlow = 'order' | 'appointment'

interface WhatsAppReturnProps {
  /** The merchant's own WhatsApp Business number, as stored (human
   *  formatting is fine -- it gets normalised to digits here). Null
   *  before the merchant has connected WhatsApp in onboarding, in which
   *  case there is nowhere to send anyone and nothing renders. */
  phoneNumber: string | null | undefined
  flow: WhatsAppReturnFlow
  /** Prefilled first message. Kept short; some clients truncate. */
  text?: string
  /** Set false to keep the manual link but suppress the automatic
   *  navigation -- used when the screen still has work for the customer
   *  to do (an unpaid order's payment link). */
  autoRedirect?: boolean
  /** Extra fields attached to every event from this screen, e.g. an
   *  order number, so the funnel can be reconstructed per flow. */
  analyticsProps?: Record<string, unknown>
}

/**
 * Confirmation-screen footer that sends the customer back to the
 * WhatsApp chat they came from.
 *
 * Nothing here is load-bearing: the order/appointment is already
 * persisted and its WhatsApp confirmation already dispatched from the
 * backend by the time this renders, so a redirect that never fires
 * costs the customer a tap on the manual link, nothing more.
 */
export function WhatsAppReturn({
  phoneNumber,
  flow,
  text,
  autoRedirect = true,
  analyticsProps,
}: WhatsAppReturnProps) {
  const digits = normalizeWhatsAppNumber(phoneNumber)
  const delayMs = getWhatsAppReturnDelayMs()
  const shouldAutoRedirect = autoRedirect && isWhatsAppReturnEnabled() && digits !== null

  const [secondsLeft, setSecondsLeft] = useState(() => Math.ceil(delayMs / 1000))

  // StrictMode double-invokes effects in dev, and a re-render must not
  // re-arm a redirect that already fired -- both would double-count the
  // attempt and re-navigate.
  const hasRedirected = useRef(false)
  const hasTrackedView = useRef(false)

  // Stable across renders so the effects below don't need `analyticsProps`
  // (a fresh object literal at every call site) in their dependencies.
  const eventProps = useRef({ flow, ...analyticsProps })
  eventProps.current = { flow, ...analyticsProps }

  useEffect(() => {
    if (hasTrackedView.current) return
    hasTrackedView.current = true
    trackEvent('success_page_viewed', {
      ...eventProps.current,
      whatsapp_return_enabled: isWhatsAppReturnEnabled(),
      whatsapp_number_available: digits !== null,
      auto_redirect_armed: shouldAutoRedirect,
    })
  }, [digits, shouldAutoRedirect])

  useEffect(() => {
    if (!shouldAutoRedirect || digits === null || hasRedirected.current) return

    const timers: ReturnType<typeof setTimeout>[] = []
    // Tracked so unmount can remove them directly -- clearing the removal
    // timer below is not enough on its own and would leak the node.
    const frames: HTMLIFrameElement[] = []
    const tick = setInterval(() => {
      setSecondsLeft((current) => (current > 0 ? current - 1 : 0))
    }, 1000)

    const redirect = setTimeout(() => {
      if (hasRedirected.current) return
      hasRedirected.current = true

      const waMeUrl = buildWaMeUrl(digits, text)
      trackEvent('whatsapp_return_auto_redirect_attempted', {
        ...eventProps.current,
        delay_ms: delayMs,
        target: waMeUrl,
      })

      // Custom scheme first, in a throwaway iframe: where it works it
      // hands off to the app directly, and where it doesn't the iframe
      // swallows the failure instead of surfacing an "address invalid"
      // dialog over the confirmation. The wa.me navigation right after
      // is what actually carries the browsers that ignore it.
      try {
        const frame = document.createElement('iframe')
        frame.style.display = 'none'
        frame.src = buildWhatsAppSchemeUrl(digits, text)
        document.body.appendChild(frame)
        frames.push(frame)
        timers.push(setTimeout(() => frame.remove(), 1000))
      } catch {
        // Non-fatal: wa.me below is the real path.
      }

      window.location.href = waMeUrl

      // A no-op unless this webview was itself script-opened, but free
      // to attempt: closing the tab lands the customer back in the chat
      // even where the redirect above was ignored. Deferred so it can't
      // race the navigation it is backstopping.
      timers.push(
        setTimeout(() => {
          try {
            window.close()
          } catch {
            // Expected in a normal tab; nothing to recover from.
          }
        }, 250),
      )
    }, delayMs)

    return () => {
      clearInterval(tick)
      clearTimeout(redirect)
      for (const timer of timers) clearTimeout(timer)
      for (const frame of frames) frame.remove()
    }
  }, [shouldAutoRedirect, digits, text, delayMs])

  const handleManualClick = useCallback(() => {
    trackEvent('whatsapp_return_manual_fallback_clicked', {
      ...eventProps.current,
      auto_redirect_armed: shouldAutoRedirect,
      // True when the automatic attempt has already run and left them
      // here anyway -- the number this whole exercise exists to measure.
      after_auto_redirect_attempt: hasRedirected.current,
    })
  }, [shouldAutoRedirect])

  if (digits === null) return null

  return (
    <div className="space-y-3">
      {shouldAutoRedirect && (
        <p
          className="text-muted-foreground flex items-center justify-center gap-2 text-sm"
          aria-live="polite"
        >
          <span
            className="border-muted-foreground/30 border-t-muted-foreground size-3.5 shrink-0 rounded-full border-2 motion-safe:animate-spin"
            aria-hidden="true"
          />
          Redirecting you back to WhatsApp
          {secondsLeft > 0 ? ` in ${secondsLeft}s…` : '…'}
        </p>
      )}
      <Button asChild variant={shouldAutoRedirect ? 'outline' : 'default'} className="w-full">
        {/* Same tab deliberately: inside WhatsApp's in-app browser a
            target="_blank" stacks another webview on an already-embedded
            view instead of handing back to the chat. */}
        <a href={buildWaMeUrl(digits, text)} onClick={handleManualClick}>
          Tap here to return to WhatsApp
        </a>
      </Button>
    </div>
  )
}
