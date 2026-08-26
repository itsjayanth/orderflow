import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'

const STATS: { label: string; value: number; tone?: 'gold' }[] = [
  { label: 'Today', value: 18 },
  { label: 'New', value: 3, tone: 'gold' },
  { label: 'Processing', value: 5 },
  { label: 'Ready', value: 2 },
]

const ORDERS: { total: string; time: string; status: string; tone: 'gold' | 'gray' | 'green' }[] = [
  { total: 'INR 220.00', time: '2 minutes ago', status: 'New', tone: 'gold' },
  { total: 'INR 540.00', time: '11 minutes ago', status: 'Processing', tone: 'gray' },
  { total: 'INR 180.00', time: '24 minutes ago', status: 'Ready', tone: 'green' },
]

/**
 * A decorative, non-interactive mockup of the merchant dashboard --
 * illustrative only, styled to match the real DashboardHomePage so
 * prospective merchants can see what they're getting.
 */
export function DashboardPreview() {
  return (
    <div className="relative mx-auto w-full max-w-sm" aria-hidden="true">
      <div className="bg-brand-gold/20 absolute -inset-8 -z-10 rounded-[2.5rem] blur-3xl" />
      <Card className="overflow-hidden shadow-2xl">
        <div className="border-border/70 flex items-center justify-between border-b px-5 py-3">
          <span className="text-primary font-serif text-sm tracking-tight">Orderflow</span>
          <span className="bg-primary text-primary-foreground flex size-6 items-center justify-center rounded-full text-[10px] font-semibold">
            CA
          </span>
        </div>
        <div className="space-y-5 p-5">
          <div>
            <p className="text-sm font-medium">Welcome back, Café Aroma</p>
            <p className="text-muted-foreground text-xs">Here's what's happening today.</p>
          </div>

          <div className="grid grid-cols-4 gap-2">
            {STATS.map((s) => (
              <div
                key={s.label}
                className={cn(
                  'rounded-lg p-2 text-center',
                  s.tone === 'gold' ? 'bg-brand-gold/20' : 'bg-muted/60',
                )}
              >
                <p
                  className={cn(
                    'text-[9px] leading-tight',
                    s.tone === 'gold' ? 'text-brand-gold-foreground/80' : 'text-muted-foreground',
                  )}
                >
                  {s.label}
                </p>
                <p
                  className={cn(
                    'font-serif text-base leading-tight',
                    s.tone === 'gold' && 'text-brand-gold-foreground',
                  )}
                >
                  {s.value}
                </p>
              </div>
            ))}
          </div>

          <div className="divide-border/70 border-border/70 divide-y overflow-hidden rounded-lg border">
            {ORDERS.map((o) => (
              <div
                key={o.total + o.time}
                className="flex items-center justify-between gap-3 px-3 py-2.5"
              >
                <div>
                  <p className="text-xs font-medium">{o.total}</p>
                  <p className="text-muted-foreground text-[10px]">{o.time}</p>
                </div>
                <Badge tone={o.tone}>{o.status}</Badge>
              </div>
            ))}
          </div>
        </div>
      </Card>
    </div>
  )
}
