import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { trackEvent } from '@/shared/lib/analytics'

import { WhatsAppReturn } from './WhatsAppReturn'

vi.mock('@/shared/lib/analytics', () => ({ trackEvent: vi.fn() }))

const mockedTrackEvent = vi.mocked(trackEvent)

// jsdom refuses a real cross-document navigation ("Not implemented"), so
// window.location is swapped for a plain object whose href we can assert
// on -- that assignment is the whole mechanism under test.
let assignedHref: string | null = null
let closeSpy: ReturnType<typeof vi.fn<() => void>>

beforeEach(() => {
  vi.useFakeTimers()
  mockedTrackEvent.mockClear()
  assignedHref = null
  // jsdom actually implements window.close() -- letting it run tears the
  // document down and breaks RTL's cleanup. Stub it so the attempt is
  // observable without destroying the test environment.
  closeSpy = vi.fn<() => void>()
  window.close = closeSpy
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: {
      get href() {
        return assignedHref ?? 'http://localhost/'
      },
      set href(value: string) {
        assignedHref = value
      },
    },
  })
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllEnvs()
})

// Timer-driven state updates (the countdown) re-render outside React's
// own batching, so the advance has to happen inside act() for the DOM to
// reflect it before the assertions run.
async function advance(ms: number): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

function eventNames(): string[] {
  return mockedTrackEvent.mock.calls.map((call) => call[0])
}

function propsFor(name: string): Record<string, unknown> {
  const call = mockedTrackEvent.mock.calls.find((entry) => entry[0] === name)
  return (call?.[1] ?? {}) as Record<string, unknown>
}

describe('WhatsAppReturn', () => {
  it('renders nothing when the merchant has no WhatsApp number', () => {
    const { container } = render(<WhatsAppReturn phoneNumber={null} flow="order" />)

    expect(container).toBeEmptyDOMElement()
    // The view is still worth recording -- a success page with no number
    // is exactly the onboarding gap this metric should surface.
    expect(propsFor('success_page_viewed').whatsapp_number_available).toBe(false)
  })

  it('strips human formatting out of the stored display number', () => {
    render(<WhatsAppReturn phoneNumber="+91 90000 00000" flow="order" />)

    expect(screen.getByRole('link', { name: /return to whatsapp/i })).toHaveAttribute(
      'href',
      'https://wa.me/919000000000',
    )
  })

  it('navigates to wa.me after the delay and reports the attempt', async () => {
    render(<WhatsAppReturn phoneNumber="919000000000" flow="appointment" text="Thanks!" />)

    expect(screen.getByText(/redirecting you back to whatsapp/i)).toBeInTheDocument()
    expect(assignedHref).toBeNull()

    await advance(2000)

    expect(assignedHref).toBe('https://wa.me/919000000000?text=Thanks!')
    expect(eventNames()).toContain('whatsapp_return_auto_redirect_attempted')
    expect(propsFor('whatsapp_return_auto_redirect_attempted').flow).toBe('appointment')
  })

  it('also attempts the whatsapp:// scheme alongside wa.me', async () => {
    render(<WhatsAppReturn phoneNumber="919000000000" flow="order" />)
    await advance(2000)

    const frame = document.querySelector('iframe')
    expect(frame?.getAttribute('src')).toBe('whatsapp://send?phone=919000000000')
  })

  it('attempts window.close() as a harmless backstop after navigating', async () => {
    render(<WhatsAppReturn phoneNumber="919000000000" flow="order" />)
    await advance(2000)

    // Deferred so it cannot race the navigation it backs up.
    expect(closeSpy).not.toHaveBeenCalled()
    await advance(250)
    expect(closeSpy).toHaveBeenCalled()
  })

  it('counts down rather than redirecting instantly', async () => {
    render(<WhatsAppReturn phoneNumber="919000000000" flow="order" />)

    expect(screen.getByText(/in 2s/i)).toBeInTheDocument()
    await advance(1000)
    expect(screen.getByText(/in 1s/i)).toBeInTheDocument()
    expect(assignedHref).toBeNull()
  })

  it('does not auto-redirect when autoRedirect is false, but keeps the manual link', async () => {
    render(<WhatsAppReturn phoneNumber="919000000000" flow="order" autoRedirect={false} />)

    await advance(5000)

    expect(assignedHref).toBeNull()
    expect(screen.queryByText(/redirecting you back to whatsapp/i)).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /return to whatsapp/i })).toBeInTheDocument()
    expect(eventNames()).not.toContain('whatsapp_return_auto_redirect_attempted')
  })

  it('honours the VITE_WHATSAPP_RETURN_REDIRECT kill switch', async () => {
    vi.stubEnv('VITE_WHATSAPP_RETURN_REDIRECT', 'false')

    render(<WhatsAppReturn phoneNumber="919000000000" flow="order" />)
    await advance(5000)

    expect(assignedHref).toBeNull()
    expect(screen.getByRole('link', { name: /return to whatsapp/i })).toBeInTheDocument()
    expect(propsFor('success_page_viewed').auto_redirect_armed).toBe(false)
  })

  it('reports a manual click, and whether the auto attempt had already run', async () => {
    render(<WhatsAppReturn phoneNumber="919000000000" flow="order" />)

    fireEvent.click(screen.getByRole('link', { name: /return to whatsapp/i }))
    expect(propsFor('whatsapp_return_manual_fallback_clicked').after_auto_redirect_attempt).toBe(
      false,
    )

    mockedTrackEvent.mockClear()
    await advance(2000)
    fireEvent.click(screen.getByRole('link', { name: /return to whatsapp/i }))

    expect(propsFor('whatsapp_return_manual_fallback_clicked').after_auto_redirect_attempt).toBe(
      true,
    )
  })

  it('fires the redirect once even though StrictMode double-mounts effects', async () => {
    render(<WhatsAppReturn phoneNumber="919000000000" flow="order" />)
    await advance(6000)

    const attempts = eventNames().filter((n) => n === 'whatsapp_return_auto_redirect_attempted')
    expect(attempts).toHaveLength(1)
    expect(eventNames().filter((n) => n === 'success_page_viewed')).toHaveLength(1)
  })
})
