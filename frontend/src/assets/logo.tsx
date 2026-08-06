/**
 * The Orderflow brand mark: a rounded chat-bubble (the WhatsApp conversation
 * the order happens in) holding a fork whose tines flow into a single
 * ribbon-like curve (the "flow" from order to kitchen to customer), capped
 * with a small accent dot. Deliberately not a literal WhatsApp glyph.
 *
 * Colors are wired to the `--primary` / `--brand-gold` CSS custom properties
 * (see `frontend/index.css`) rather than hardcoded hex, so the mark re-tints
 * automatically between light and dark theme -- the same pattern used by
 * `ChatMockup` and `DashboardPreview` for brand-colored surfaces.
 */
export function OrderflowLogo({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      className={className}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="Orderflow"
    >
      <rect x="3" y="4" width="26" height="19" rx="8" fill="var(--primary)" />
      <path d="M9 23 L9 28 Q9 29 10 28.2 L15.5 23 Z" fill="var(--primary)" />
      <g stroke="var(--brand-gold)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
        <line x1="11.5" y1="9.5" x2="11.5" y2="14.5" />
        <line x1="13.7" y1="8.5" x2="13.7" y2="14.5" />
        <line x1="15.9" y1="9.5" x2="15.9" y2="14.5" />
        <path d="M13.7 14.8 C13.7 16.6 13.5 18 15.3 18.4 C18 19 20.8 17.6 22.8 15 C23.6 14 24.1 12.8 24.4 11.6" />
      </g>
      <circle cx="24.7" cy="11" r="1.15" fill="var(--brand-gold)" />
    </svg>
  )
}
