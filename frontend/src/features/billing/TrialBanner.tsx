import { X } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { useSubscription } from './useSubscription'

function daysRemaining(trialEndsAt: string): number {
  const diffMs = new Date(trialEndsAt).getTime() - Date.now()
  return Math.max(0, Math.ceil(diffMs / (1000 * 60 * 60 * 24)))
}

// Dismissible for the current page session only (component-local state, no
// persistence) -- reappears on the next full load/navigation away and back,
// which is fine: it's a reminder, not a one-time notice.
export function TrialBanner() {
  const { data: subscription } = useSubscription()
  const [dismissed, setDismissed] = useState(false)

  if (dismissed || !subscription) {
    return null
  }

  if (subscription.status !== 'trialing' && subscription.status !== 'expired') {
    return null
  }

  const message =
    subscription.status === 'trialing' && subscription.trial_ends_at
      ? `${daysRemaining(subscription.trial_ends_at)} day${
          daysRemaining(subscription.trial_ends_at) === 1 ? '' : 's'
        } left in your ${subscription.plan.display_name} trial`
      : subscription.status === 'trialing'
        ? `You're on a free trial of ${subscription.plan.display_name}`
        : "Your trial has ended -- you're on Starter limits"

  return (
    <div className="bg-brand-gold/15 border-brand-gold/30 flex items-center gap-3 rounded-lg border px-4 py-2.5 text-sm">
      <p className="text-brand-gold-foreground flex-1">
        {message}
        {' — '}
        <Link to="/settings/billing" className="font-medium underline underline-offset-2">
          {subscription.status === 'trialing' ? 'Upgrade now' : 'View plans'}
        </Link>
      </p>
      <button
        type="button"
        aria-label="Dismiss"
        onClick={() => setDismissed(true)}
        className="text-brand-gold-foreground/70 hover:text-brand-gold-foreground shrink-0"
      >
        <X className="size-4" />
      </button>
    </div>
  )
}
