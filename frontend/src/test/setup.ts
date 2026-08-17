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
