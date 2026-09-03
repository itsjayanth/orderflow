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

// jsdom doesn't implement elementFromPoint either -- react-big-calendar's
// Selection helper (used by the appointments calendar view for click/drag
// range selection) calls it from a document-level mousedown listener that's
// live for as long as any calendar is mounted, so it can fire during
// unrelated interactions elsewhere on the page in tests. A stub returning
// null (nothing at that point) is enough since no test asserts on
// drag-to-select behavior.
document.elementFromPoint ??= () => null
