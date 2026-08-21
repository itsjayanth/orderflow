import * as AvatarPrimitive from '@radix-ui/react-avatar'
import type * as React from 'react'

import { cn } from '@/lib/utils'

// Thin wrapper around Radix's Avatar primitive -- a clean primitive for
// Phase 2's nav-shell user avatar. Distinct from shared/components/
// ItemImage.tsx's hand-rolled image-with-fallback-initials pattern
// (catalog item photos, Phase 5 scope) -- that file is untouched here.

function Avatar({ className, ...props }: React.ComponentProps<typeof AvatarPrimitive.Root>) {
  return (
    <AvatarPrimitive.Root
      data-slot="avatar"
      className={cn('relative flex size-9 shrink-0 overflow-hidden rounded-full', className)}
      {...props}
    />
  )
}

function AvatarImage({ className, ...props }: React.ComponentProps<typeof AvatarPrimitive.Image>) {
  return (
    <AvatarPrimitive.Image
      data-slot="avatar-image"
      className={cn('aspect-square size-full object-cover', className)}
      {...props}
    />
  )
}

function AvatarFallback({
  className,
  ...props
}: React.ComponentProps<typeof AvatarPrimitive.Fallback>) {
  return (
    <AvatarPrimitive.Fallback
      data-slot="avatar-fallback"
      className={cn(
        'bg-muted text-muted-foreground flex size-full items-center justify-center rounded-full text-sm font-medium',
        className,
      )}
      {...props}
    />
  )
}

export { Avatar, AvatarFallback, AvatarImage }
