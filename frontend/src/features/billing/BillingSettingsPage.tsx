import { useState } from 'react'

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Badge, type Tone } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import type { PlanOut, PlanTier } from '@/shared/api/types'
import { PageHeader } from '@/shared/components/PageHeader'

import { SUBSCRIPTION_STATUS_LABELS } from './subscriptionTransitions'
import { useCancelSubscription } from './useCancelSubscription'
import { useChangePlan } from './useChangePlan'
import { usePlans } from './usePlans'
import { useSubscription } from './useSubscription'

const TIER_BADGE_TONE: Record<PlanTier, Tone> = {
  starter: 'gray',
  growth: 'gold',
  pro: 'gold',
}

function daysRemaining(trialEndsAt: string): number {
  const diffMs = new Date(trialEndsAt).getTime() - Date.now()
  return Math.max(0, Math.ceil(diffMs / (1000 * 60 * 60 * 24)))
}

function PlanPicker({
  plans,
  currentPlanId,
  onPick,
  isPending,
}: {
  plans: PlanOut[]
  currentPlanId: string
  onPick: (planId: string) => void
  isPending: boolean
}) {
  return (
    <div className="space-y-2">
      {plans.map((plan) => (
        <button
          key={plan.plan_id}
          type="button"
          disabled={isPending || plan.plan_id === currentPlanId}
          onClick={() => onPick(plan.plan_id)}
          className="border-input hover:border-ring/30 disabled:hover:border-input flex w-full items-center justify-between rounded-lg border px-4 py-2.5 text-left text-sm transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <span>
            <span className="font-medium capitalize">{plan.display_name}</span>{' '}
            <span className="text-muted-foreground">
              ({plan.billing_interval === 'monthly' ? 'Monthly' : 'Annual'})
            </span>
          </span>
          <span className="text-muted-foreground">
            {plan.plan_id === currentPlanId ? 'Current plan' : `INR ${plan.price_inr}`}
          </span>
        </button>
      ))}
    </div>
  )
}

export function BillingSettingsPage() {
  const { data: subscription, isLoading } = useSubscription()
  const { data: plans } = usePlans()
  const changePlan = useChangePlan()
  const cancelSubscription = useCancelSubscription()
  const [pickerOpen, setPickerOpen] = useState(false)
  const [cancelConfirmOpen, setCancelConfirmOpen] = useState(false)

  return (
    <div className="space-y-6">
      <PageHeader
        title="Billing"
        description="Manage your Orderflow subscription plan and payment status."
      />

      <Card className="space-y-5 p-6">
        {isLoading && <p className="text-muted-foreground text-sm">Loading…</p>}

        {!isLoading && !subscription && (
          <p className="text-muted-foreground text-sm">
            Couldn't load your subscription right now. Please try again shortly.
          </p>
        )}

        {!isLoading && subscription && (
          <>
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-medium capitalize">
                  {subscription.plan.display_name} plan
                </h2>
                <p className="text-muted-foreground text-sm">
                  {subscription.plan.billing_interval === 'monthly'
                    ? 'Billed monthly'
                    : 'Billed annually'}{' '}
                  · INR {subscription.plan.price_inr}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone={TIER_BADGE_TONE[subscription.plan.tier]}>
                  {subscription.plan.display_name}
                </Badge>
                <Badge tone={subscription.status === 'active' ? 'green' : 'amber'}>
                  {SUBSCRIPTION_STATUS_LABELS[subscription.status]}
                </Badge>
              </div>
            </div>

            {subscription.status === 'trialing' && subscription.trial_ends_at && (
              <p className="bg-secondary/40 rounded-md border p-3 text-sm">
                {daysRemaining(subscription.trial_ends_at)} day
                {daysRemaining(subscription.trial_ends_at) === 1 ? '' : 's'} left in your free
                trial.
              </p>
            )}

            {subscription.status === 'past_due' && (
              <p className="bg-destructive/10 text-destructive rounded-md border p-3 text-sm">
                Your last payment didn't go through. Please update your payment method to avoid
                losing access to your current plan.
              </p>
            )}

            <div className="space-y-1.5">
              <p className="text-sm font-medium">Usage this cycle</p>
              <p className="text-muted-foreground text-sm">
                {subscription.orders_used_this_cycle} order
                {subscription.orders_used_this_cycle === 1 ? '' : 's'} used
                {subscription.order_cap === null ? ' · Unlimited' : ` of ${subscription.order_cap}`}
              </p>
              {subscription.order_cap !== null && (
                <div className="bg-muted h-2 w-full max-w-sm overflow-hidden rounded-full">
                  <div
                    className="bg-primary h-full rounded-full transition-all duration-300"
                    style={{
                      width: `${Math.min(
                        100,
                        (subscription.orders_used_this_cycle / subscription.order_cap) * 100,
                      )}%`,
                    }}
                  />
                </div>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-3 border-t pt-4">
              <Button type="button" variant="outline" onClick={() => setPickerOpen((v) => !v)}>
                {pickerOpen ? 'Hide plans' : 'Upgrade / downgrade'}
              </Button>
              {subscription.status !== 'canceled' && !subscription.cancel_at_period_end && (
                <Button
                  type="button"
                  variant="ghost"
                  className="text-destructive hover:text-destructive"
                  onClick={() => setCancelConfirmOpen(true)}
                >
                  Cancel subscription
                </Button>
              )}
              {subscription.cancel_at_period_end && (
                <p className="text-muted-foreground text-sm">
                  Your subscription will end at the close of the current billing period.
                </p>
              )}
            </div>

            {pickerOpen && plans && plans.length > 0 && (
              <PlanPicker
                plans={plans}
                currentPlanId={subscription.plan.plan_id}
                isPending={changePlan.isPending}
                onPick={(planId) =>
                  changePlan.mutate({ plan_id: planId }, { onSuccess: () => setPickerOpen(false) })
                }
              />
            )}
            {changePlan.isError && (
              <p className="text-destructive text-sm">Failed to change plan. Please try again.</p>
            )}
            {cancelSubscription.isError && (
              <p className="text-destructive text-sm">
                Failed to cancel subscription. Please try again.
              </p>
            )}
          </>
        )}
      </Card>

      <AlertDialog open={cancelConfirmOpen} onOpenChange={setCancelConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel subscription?</AlertDialogTitle>
            <AlertDialogDescription>
              You'll keep access through the end of your current billing period, then drop to
              Starter limits. You can re-subscribe any time.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep subscription</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={() => cancelSubscription.mutate()}>
              Cancel subscription
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
