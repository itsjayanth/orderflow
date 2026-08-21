import '@testing-library/jest-dom/vitest'

// jsdom doesn't implement ResizeObserver, which Radix's Switch (and other
// size-aware primitives) read on mount -- a minimal no-op stub is enough
// since tests never assert on layout measurements.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver

// jsdom doesn't implement scrollIntoView either -- the checkout page uses
// it for the "back to menu" / "continue to checkout" jump links.
Element.prototype.scrollIntoView ??= () => {}

// jsdom doesn't implement matchMedia either -- ThemeProvider (Phase 2's
// dashboard shell) reads it on mount to resolve the "system" theme option.
// A minimal stub reporting "no preference" is enough since no test asserts
// on live OS-theme-change behavior.
window.matchMedia ??= (query: string) =>
  ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }) as unknown as MediaQueryList
