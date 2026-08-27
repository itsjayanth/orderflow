import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

function ChatBubble({
  from,
  tone,
  children,
}: {
  from: 'me' | 'them'
  tone?: 'gold'
  children: ReactNode
}) {
  return (
    <div className={cn('flex', from === 'me' ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[85%] rounded-2xl px-3 py-2 text-xs leading-relaxed shadow-sm',
          from === 'me' && 'bg-primary text-primary-foreground rounded-br-sm',
          from === 'them' &&
            tone === 'gold' &&
            'bg-brand-gold/25 text-brand-gold-foreground rounded-bl-sm',
          from === 'them' && !tone && 'bg-card text-card-foreground rounded-bl-sm',
        )}
      >
        {children}
      </div>
    </div>
  )
}

function ItemChip({ name, price }: { name: string; price: string }) {
  return (
    <div className="bg-card border-border/70 ml-1 flex w-fit items-center gap-2 rounded-full border px-3 py-1.5 text-xs shadow-sm">
      <span className="font-medium">{name}</span>
      <span className="text-muted-foreground">{price}</span>
    </div>
  )
}

function PayChip() {
  return (
    <div className="flex justify-start">
      <div className="bg-brand-gold text-brand-gold-foreground ml-1 flex items-center gap-1.5 rounded-full px-4 py-2 text-xs font-semibold shadow-sm">
        Pay ₹220 securely →
      </div>
    </div>
  )
}

/**
 * A decorative, non-interactive mockup of the customer-facing WhatsApp
 * ordering flow -- purely illustrative for the marketing hero, not a real
 * chat surface. Hidden from assistive tech; the surrounding copy carries
 * the actual content.
 */
export function ChatMockup() {
  return (
    <div className="relative mx-auto w-full max-w-[300px]" aria-hidden="true">
      <div className="bg-primary/25 absolute -inset-8 -z-10 rounded-[3rem] blur-3xl" />
      <div className="bg-brand-gold/20 absolute -inset-8 -z-10 rounded-[3rem] blur-3xl" />
      <div className="border-border/70 bg-card relative overflow-hidden rounded-[2.25rem] border shadow-2xl">
        <div className="bg-primary text-primary-foreground flex items-center gap-2.5 px-4 py-3.5">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/15 text-sm font-semibold">
            CA
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm leading-tight font-medium">Café Aroma</p>
            <p className="text-primary-foreground/70 truncate text-[11px] leading-tight">
              via Orderflow · online
            </p>
          </div>
        </div>

        <div className="bg-muted/60 flex flex-col gap-2.5 px-3 py-4">
          <ChatBubble from="them">
            Namaste! 👋 Here's what's available — tap an item to add it to your order.
          </ChatBubble>
          <ItemChip name="Classic Combo" price="₹220" />
          <ItemChip name="Deluxe Pack" price="₹120" />
          <ChatBubble from="me">Added Classic Combo ×1 to cart</ChatBubble>
          <ChatBubble from="them">
            <span className="font-medium">Order summary</span>
            <br />
            1× Classic Combo — ₹220
            <br />
            <span className="font-semibold">Total: ₹220</span>
          </ChatBubble>
          <PayChip />
          <ChatBubble from="them" tone="gold">
            ✅ Payment received — your order is confirmed!
          </ChatBubble>
          <ChatBubble from="them" tone="gold">
            🔄 Processing your order…
          </ChatBubble>
        </div>
      </div>
    </div>
  )
}
