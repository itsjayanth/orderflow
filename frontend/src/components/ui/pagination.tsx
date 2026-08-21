import { ChevronLeft, ChevronRight } from 'lucide-react'
import type * as React from 'react'

import { cn } from '@/lib/utils'

// Kept deliberately simple for this app's scale (small-restaurant order/
// customer volumes) -- previous/next + a page-info slot ("Page 2 of 5" /
// "21-40 of 87"), not a full numbered-page-link list. Call-sites decide
// exact integration; this is just the primitive.

function Pagination({ className, ...props }: React.ComponentProps<'nav'>) {
  return (
    <nav
      data-slot="pagination"
      aria-label="Pagination"
      className={cn('flex items-center justify-between gap-4', className)}
      {...props}
    />
  )
}

function PaginationContent({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="pagination-content"
      className={cn('flex items-center gap-1', className)}
      {...props}
    />
  )
}

function PaginationItem(props: React.ComponentProps<'div'>) {
  return <div data-slot="pagination-item" {...props} />
}

function PaginationInfo({ className, ...props }: React.ComponentProps<'p'>) {
  return (
    <p
      data-slot="pagination-info"
      className={cn('text-muted-foreground text-sm', className)}
      {...props}
    />
  )
}

function PaginationPrevious({ className, disabled, ...props }: React.ComponentProps<'button'>) {
  return (
    <button
      type="button"
      data-slot="pagination-previous"
      aria-label="Go to previous page"
      disabled={disabled}
      className={cn(
        'inline-flex h-9 items-center gap-1 rounded-lg px-3 text-sm font-medium transition-colors duration-150 outline-none',
        'hover:bg-accent hover:text-accent-foreground focus-visible:ring-ring/30 focus-visible:ring-4',
        'disabled:pointer-events-none disabled:opacity-50',
        className,
      )}
      {...props}
    >
      <ChevronLeft className="size-4" />
      Previous
    </button>
  )
}

function PaginationNext({ className, disabled, ...props }: React.ComponentProps<'button'>) {
  return (
    <button
      type="button"
      data-slot="pagination-next"
      aria-label="Go to next page"
      disabled={disabled}
      className={cn(
        'inline-flex h-9 items-center gap-1 rounded-lg px-3 text-sm font-medium transition-colors duration-150 outline-none',
        'hover:bg-accent hover:text-accent-foreground focus-visible:ring-ring/30 focus-visible:ring-4',
        'disabled:pointer-events-none disabled:opacity-50',
        className,
      )}
      {...props}
    >
      Next
      <ChevronRight className="size-4" />
    </button>
  )
}

export {
  Pagination,
  PaginationContent,
  PaginationInfo,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
}
