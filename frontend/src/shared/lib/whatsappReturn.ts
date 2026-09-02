/**
 * Returning the customer to the WhatsApp chat after they finish in the
 * browser-mode ordering/booking webview.
 *
 * The whole behaviour sits behind VITE_WHATSAPP_RETURN_REDIRECT because
 * Meta documents none of it: whether navigating to a wa.me URL from
 * inside WhatsApp's own in-app browser pops back to the chat (rather
 * than opening yet another webview) is an implementation detail that
 * has changed between WhatsApp versions and differs between Android and
 * iOS. Flipping that flag to "false" reverts to a plain manual link
 * with no automatic navigation.
 */

const DEFAULT_DELAY_MS = 2000
const MAX_DELAY_MS = 10_000

function readEnv(key: string): string | undefined {
  const value = (import.meta.env as Record<string, string | undefined>)[key]
  return value?.trim() || undefined
}

/** Anything but an explicit opt-out counts as enabled, so an unset var in
 *  an existing deployment keeps the feature rather than silently dropping it. */
export function isWhatsAppReturnEnabled(): boolean {
  const raw = readEnv('VITE_WHATSAPP_RETURN_REDIRECT')?.toLowerCase()
  return raw !== 'false' && raw !== '0' && raw !== 'off' && raw !== 'no'
}

/** How long the confirmation stays on screen before the redirect fires.
 *  Long enough to read the order/appointment number, short enough not to
 *  feel stuck. Clamped so a typo in the env can't hang the page. */
export function getWhatsAppReturnDelayMs(): number {
  const parsed = Number(readEnv('VITE_WHATSAPP_RETURN_DELAY_MS'))
  if (!Number.isFinite(parsed) || parsed < 0) return DEFAULT_DELAY_MS
  return Math.min(parsed, MAX_DELAY_MS)
}

/** wa.me and the whatsapp:// scheme both want bare digits -- country code
 *  and local number, no "+", spaces or dashes. The stored display phone
 *  number is formatted for humans, so strip it down. */
export function normalizeWhatsAppNumber(raw: string | null | undefined): string | null {
  const digits = (raw ?? '').replace(/\D/g, '')
  return digits.length > 0 ? digits : null
}

export function buildWaMeUrl(digits: string, text?: string): string {
  const query = text ? `?text=${encodeURIComponent(text)}` : ''
  return `https://wa.me/${digits}${query}`
}

/** Some in-app browser builds hand off on the custom scheme when they
 *  won't on an https wa.me link, so it's worth trying alongside. */
export function buildWhatsAppSchemeUrl(digits: string, text?: string): string {
  const params = new URLSearchParams({ phone: digits })
  if (text) params.set('text', text)
  return `whatsapp://send?${params.toString()}`
}
