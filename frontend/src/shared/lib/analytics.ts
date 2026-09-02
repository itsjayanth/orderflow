import { logger } from './logger'

/**
 * Thin client-side event sink.
 *
 * orderflow has no analytics vendor wired up yet, so this deliberately
 * does two cheap things and nothing else: it always writes to the
 * console via `logger` (so events are visible in a remote-debugged
 * WhatsApp in-app browser session, which is the only practical way to
 * observe that surface), and it forwards to a vendor global if one has
 * been dropped onto the page. Adding a vendor later means either
 * exposing that global or replacing the body of `dispatch` -- callers
 * don't change.
 */

type AnalyticsProps = Record<string, unknown>

interface AnalyticsWindow {
  // Set by GA4/GTM snippets. Kept structurally typed rather than pulled
  // from a vendor .d.ts so this file has no dependency to install.
  gtag?: (command: 'event', name: string, props?: AnalyticsProps) => void
  dataLayer?: { push: (payload: AnalyticsProps & { event: string }) => void }
}

function dispatch(name: string, props: AnalyticsProps): void {
  if (typeof window === 'undefined') return
  const w = window as AnalyticsWindow

  try {
    if (typeof w.gtag === 'function') {
      w.gtag('event', name, props)
      return
    }
    if (w.dataLayer && typeof w.dataLayer.push === 'function') {
      w.dataLayer.push({ event: name, ...props })
    }
  } catch (error) {
    // Analytics is never allowed to break a checkout or booking screen.
    logger.warn('analytics dispatch failed', error)
  }
}

export function trackEvent(name: string, props: AnalyticsProps = {}): void {
  logger.info(`analytics: ${name}`, props)
  dispatch(name, props)
}
