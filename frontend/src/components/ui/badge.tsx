import type * as React from 'react'

import { cn } from '@/lib/utils'

const TONE_CLASSES = {
  green: 'bg-primary/10 text-primary border-primary/25',
  gold: 'bg-brand-gold/20 text-brand-gold-foreground border-brand-gold/40',
  amber: 'bg-amber-500/10 text-amber-700 border-amber-500/25 dark:text-amber-300',
  gray: 'bg-muted text-muted-foreground border-border',
  red: 'bg-destructive/10 text-destructive border-destructive/25',
} as const

type Tone = keyof typeof TONE_CLASSES

function Badge({
  tone = 'gray',
  className,
  ...props
}: React.ComponentProps<'span'> & { tone?: Tone }) {
  return (
    <span
      data-slot="badge"
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap',
        TONE_CLASSES[tone],
        className,
      )}
      {...props}
    />
  )
}

export { Badge }
