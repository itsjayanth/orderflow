import { Check, Sparkles, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { OrderflowLogo } from '@/assets/logo'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { useMe } from '@/features/auth/useAuth'
import type { BillingInterval, PlanOut, PlanTier } from '@/shared/api/types'

import { usePlans } from './usePlans'
import { useSubscribe } from './useSubscribe'

const TIER_ORDER: PlanTier[] = ['starter', 'growth', 'pro']

const TIER_TAGLINES: Record<PlanTier, string> = {
  starter: 'Get started on WhatsApp ordering.',
  growth: 'Native WhatsApp Flow ordering, no branding.',
  pro: 'Unlimited orders for busy, growing businesses.',
}

function formatPrice(priceInr: string, interval: BillingInterval): string {
  const amount = Number(priceInr)
  const formatted = Number.isFinite(amount) ? amount.toLocaleString('en-IN') : priceInr
  return `INR ${formatted} / ${interval === 'monthly' ? 'month' : 'year'}`
}

function PlanCard({
  plan,
  isAuthenticated,
  onSubscribe,
  isSubscribing,
}: {
  plan: PlanOut
  isAuthenticated: boolean
  onSubscribe: (planId: string) => void
  isSubscribing: boolean
}) {
  const highlighted = plan.tier === 'growth'

  return (
    <Card
      className={
        highlighted
          ? 'border-primary/40 ring-primary/15 relative flex h-full flex-col gap-5 p-6 shadow-lg ring-2'
          : 'flex h-full flex-col gap-5 p-6'
      }
    >
      {highlighted && (
        <Badge tone="gold" className="absolute -top-3 left-6">
          Most popular
        </Badge>
      )}
      <div className="space-y-1">
        <h3 className="font-serif text-xl font-semibold capitalize">{plan.display_name}</h3>
        <p className="text-muted-foreground text-sm">{TIER_TAGLINES[plan.tier]}</p>
      </div>

      <p className="font-serif text-2xl font-semibold">
        {formatPrice(plan.price_inr, plan.billing_interval)}
      </p>

      <ul className="space-y-2.5 text-sm">
        <li className="flex items-start gap-2">
          <Check className="text-primary mt-0.5 size-4 shrink-0" />
          <span>
            {plan.order_cap === null ? 'Unlimited orders' : `Up to ${plan.order_cap} orders/month`}
          </span>
        </li>
        <li className="flex items-start gap-2">
          {plan.whatsapp_flow_enabled ? (
            <Check className="text-primary mt-0.5 size-4 shrink-0" />
          ) : (
            <X className="text-muted-foreground/60 mt-0.5 size-4 shrink-0" />
          )}
          <span className={plan.whatsapp_flow_enabled ? '' : 'text-muted-foreground'}>
            Native WhatsApp ordering (Flow)
          </span>
        </li>
        <li className="flex items-start gap-2">
          {plan.branding_required ? (
            <X className="text-muted-foreground/60 mt-0.5 size-4 shrink-0" />
          ) : (
            <Check className="text-primary mt-0.5 size-4 shrink-0" />
          )}
          <span className={plan.branding_required ? 'text-muted-foreground' : ''}>
            {plan.branding_required
              ? '"Powered by Orderflow" badge shown'
              : 'No "Powered by Orderflow" badge'}
          </span>
        </li>
      </ul>

      <div className="mt-auto pt-2">
        {isAuthenticated ? (
          <Button
            type="button"
            className="w-full"
            variant={highlighted ? 'default' : 'outline'}
            disabled={isSubscribing}
            onClick={() => onSubscribe(plan.plan_id)}
          >
            {isSubscribing ? 'Redirecting…' : 'Subscribe'}
          </Button>
        ) : (
          <Button asChild className="w-full" variant={highlighted ? 'default' : 'outline'}>
            <Link to="/register">Get started</Link>
          </Button>
        )}
      </div>
    </Card>
  )
}

export function PricingPage() {
  // useMe()'s query only runs while authenticated (see useAuth.ts) -- it's
  // always safe to call here, logged in or out, same as HomePage avoids
  // calling it at all and other authenticated pages call it unconditionally.
  const { data: me } = useMe()
  const { data: plans, isLoading, isError } = usePlans()
  const subscribe = useSubscribe()
  const [billingInterval, setBillingInterval] = useState<BillingInterval>('monthly')
  const [subscribingPlanId, setSubscribingPlanId] = useState<string | null>(null)

  const visiblePlans = useMemo(() => {
    if (!plans) return []
    const byTier = new Map(
      plans.filter((p) => p.billing_interval === billingInterval).map((p) => [p.tier, p]),
    )
    return TIER_ORDER.map((tier) => byTier.get(tier)).filter((p): p is PlanOut => Boolean(p))
  }, [plans, billingInterval])

  const handleSubscribe = (planId: string) => {
    setSubscribingPlanId(planId)
    subscribe.mutate(
      { plan_id: planId },
      {
        onSuccess: (data) => {
          window.location.href = data.checkout_url
        },
        onSettled: () => setSubscribingPlanId(null),
      },
    )
  }

  return (
    <div className="min-h-svh">
      <header className="border-border/70 bg-background/85 sticky top-0 z-10 border-b backdrop-blur-sm">
        <nav className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <Link to={me ? '/dashboard' : '/'} className="flex shrink-0 items-center gap-2">
            <OrderflowLogo className="size-6" />
            <span className="text-primary font-serif text-lg tracking-tight">Orderflow</span>
          </Link>
          <div className="flex shrink-0 items-center gap-2">
            {me ? (
              <Button asChild variant="ghost" size="sm">
                <Link to="/dashboard">Dashboard</Link>
              </Button>
            ) : (
              <>
                <Button asChild variant="ghost" size="sm">
                  <Link to="/login">Log in</Link>
                </Button>
                <Button asChild size="sm">
                  <Link to="/register">Get started</Link>
                </Button>
              </>
            )}
          </div>
        </nav>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-20">
        <div className="mx-auto max-w-2xl space-y-3 text-center">
          <span className="border-brand-gold/40 bg-brand-gold/15 text-brand-gold-foreground mx-auto inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium">
            <Sparkles className="size-3.5" />
            Simple, transparent pricing
          </span>
          <h1 className="font-serif text-3xl font-semibold tracking-tight sm:text-4xl">
            Pick the plan that fits your business
          </h1>
          <p className="text-muted-foreground text-lg">
            Every plan includes WhatsApp ordering, a merchant dashboard, and automatic customer
            status updates.
          </p>
        </div>

        <div className="mt-8 flex justify-center">
          <div className="bg-secondary/60 inline-flex items-center rounded-full border p-1 text-sm">
            <button
              type="button"
              onClick={() => setBillingInterval('monthly')}
              className={
                billingInterval === 'monthly'
                  ? 'bg-card rounded-full px-4 py-1.5 font-medium shadow-sm'
                  : 'text-muted-foreground px-4 py-1.5 font-medium'
              }
            >
              Monthly
            </button>
            <button
              type="button"
              onClick={() => setBillingInterval('annual')}
              className={
                billingInterval === 'annual'
                  ? 'bg-card rounded-full px-4 py-1.5 font-medium shadow-sm'
                  : 'text-muted-foreground px-4 py-1.5 font-medium'
              }
            >
              Annual
            </button>
          </div>
        </div>

        <div className="mt-12">
          {isLoading && (
            <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
              {[0, 1, 2].map((i) => (
                <Card key={i} className="motion-safe:animate-pulse space-y-4 p-6">
                  <div className="bg-muted h-6 w-2/3 rounded" />
                  <div className="bg-muted h-4 w-full rounded" />
                  <div className="bg-muted h-8 w-1/2 rounded" />
                  <div className="bg-muted h-24 w-full rounded" />
                </Card>
              ))}
            </div>
          )}

          {isError && (
            <Card className="p-8 text-center">
              <p className="text-muted-foreground text-sm">
                Couldn't load pricing right now. Please try again shortly.
              </p>
            </Card>
          )}

          {!isLoading && !isError && visiblePlans.length === 0 && (
            <Card className="p-8 text-center">
              <p className="text-muted-foreground text-sm">No plans are available right now.</p>
            </Card>
          )}

          {!isLoading && !isError && visiblePlans.length > 0 && (
            <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
              {visiblePlans.map((plan) => (
                <PlanCard
                  key={plan.plan_id}
                  plan={plan}
                  isAuthenticated={Boolean(me)}
                  onSubscribe={handleSubscribe}
                  isSubscribing={subscribingPlanId === plan.plan_id && subscribe.isPending}
                />
              ))}
            </div>
          )}

          {subscribe.isError && (
            <p className="text-destructive mt-4 text-center text-sm">
              Something went wrong starting checkout. Please try again.
            </p>
          )}
        </div>
      </main>
    </div>
  )
}
