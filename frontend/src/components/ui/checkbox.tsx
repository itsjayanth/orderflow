import * as CheckboxPrimitive from '@radix-ui/react-checkbox'
import { CheckIcon, MinusIcon } from 'lucide-react'
import type * as React from 'react'

import { cn } from '@/lib/utils'

// Thin wrapper around Radix's Checkbox primitive, styled to match this
// repo's other form primitives (switch.tsx's border/focus-ring tokens).
// Supports the indeterminate state via `checked="indeterminate"` (Radix
// handles this natively) -- rendered as a dash instead of a check.

function Checkbox({ className, ...props }: React.ComponentProps<typeof CheckboxPrimitive.Root>) {
  return (
    <CheckboxPrimitive.Root
      data-slot="checkbox"
      className={cn(
        'border-input bg-card peer size-4 shrink-0 rounded-[4px] border shadow-xs transition-all duration-150 outline-none',
        'data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground data-[state=checked]:border-primary',
        'data-[state=indeterminate]:bg-primary data-[state=indeterminate]:text-primary-foreground data-[state=indeterminate]:border-primary',
        'focus-visible:border-ring focus-visible:ring-ring/30 focus-visible:ring-4',
        'disabled:cursor-not-allowed disabled:opacity-50',
        'aria-invalid:border-destructive aria-invalid:ring-destructive/20',
        className,
      )}
      {...props}
    >
      <CheckboxPrimitive.Indicator
        data-slot="checkbox-indicator"
        className="flex items-center justify-center text-current"
      >
        {props.checked === 'indeterminate' ? (
          <MinusIcon className="size-3" />
        ) : (
          <CheckIcon className="size-3" />
        )}
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  )
}

export { Checkbox }
