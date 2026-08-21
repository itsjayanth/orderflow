import type * as React from 'react'

import { cn } from '@/lib/utils'

// Shared "✓ {message}" success-confirmation pattern -- previously hardcoded
// separately in SettingsPage.tsx's WhatsAppSettingsSection, OnboardingPage.tsx's
// ConnectWhatsAppStep, and WhatsAppFlowSetupCard.tsx (all three: a raw
// `bg-green-600`/`text-[10px]` checkmark circle next to `text-green-700
// dark:text-green-400` text). Pulled onto the app's `--primary` token (the
// same forest-green used for Badge's "green" tone) instead of a one-off
// hardcoded green, so this now tracks the app palette instead of drifting
// from it independently.
interface SavedIndicatorProps {
  message: React.ReactNode
  className?: string
}

export function SavedIndicator({ message, className }: SavedIndicatorProps) {
  return (
    <p className={cn('text-primary flex items-center gap-1.5 text-sm font-medium', className)}>
      <span
        className="bg-primary text-primary-foreground flex size-4 items-center justify-center rounded-full text-[10px]"
        aria-hidden
      >
        ✓
      </span>
      {message}
    </p>
  )
}
