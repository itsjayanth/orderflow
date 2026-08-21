import type * as React from 'react'

import { cn } from '@/lib/utils'

// A pulsing placeholder block, sized via `className` at each call-site
// (e.g. `<Skeleton className="h-4 w-32" />`).
function Skeleton({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="skeleton"
      className={cn('bg-muted animate-pulse rounded-md', className)}
      {...props}
    />
  )
}

export { Skeleton }
