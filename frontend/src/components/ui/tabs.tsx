import * as TabsPrimitive from '@radix-ui/react-tabs'
import type * as React from 'react'

import { cn } from '@/lib/utils'

// Thin wrapper around Radix's Tabs primitive -- replaces the hand-rolled
// button-tab-bars in Orders/Customers (call-site migration is a later
// phase). TabsList scrolls horizontally instead of wrapping/overflowing
// once there are more tabs than fit, matching what those pages' existing
// tab bars already do.

function Tabs({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Root>) {
  return (
    <TabsPrimitive.Root
      data-slot="tabs"
      className={cn('flex flex-col gap-4', className)}
      {...props}
    />
  )
}

function TabsList({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      className={cn(
        'text-muted-foreground inline-flex w-full items-center gap-1 overflow-x-auto border-b',
        className,
      )}
      {...props}
    />
  )
}

function TabsTrigger({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      data-slot="tabs-trigger"
      className={cn(
        'relative inline-flex shrink-0 items-center justify-center gap-1.5 px-3 py-2 text-sm font-medium whitespace-nowrap transition-colors duration-150 outline-none',
        'text-muted-foreground hover:text-foreground',
        'data-[state=active]:text-foreground',
        "after:absolute after:inset-x-2 after:-bottom-px after:h-0.5 after:rounded-full after:bg-transparent after:content-['']",
        'data-[state=active]:after:bg-primary',
        'focus-visible:ring-ring/30 focus-visible:ring-4',
        'disabled:pointer-events-none disabled:opacity-50',
        className,
      )}
      {...props}
    />
  )
}

function TabsContent({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      data-slot="tabs-content"
      className={cn('outline-none', className)}
      {...props}
    />
  )
}

export { Tabs, TabsContent, TabsList, TabsTrigger }
