import { Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'

// Generic "this needs a paid plan" upsell -- drop it in anywhere a Starter
// merchant hits a Growth-gated feature (e.g. native WhatsApp Flow ordering).
// Kept feature-agnostic (just a name string) so new gated features don't
// need their own bespoke component.
interface UpgradePromptProps {
  featureName: string
  className?: string
}

export function UpgradePrompt({ featureName, className }: UpgradePromptProps) {
  return (
    <Card className={cn('space-y-3 p-6 text-center', className)}>
      <Badge tone="gold" className="mx-auto">
        <Sparkles className="mr-1 size-3" />
        Growth feature
      </Badge>
      <p className="text-sm font-medium">{featureName} requires the Growth plan</p>
      <p className="text-muted-foreground text-sm">
        Upgrade to unlock {featureName.toLowerCase()} and more, including native WhatsApp ordering
        and no "Powered by Orderflow" badge.
      </p>
      <Button asChild size="sm">
        <Link to="/pricing">See plans</Link>
      </Button>
    </Card>
  )
}
