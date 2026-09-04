import { ChevronLeft } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { Badge, type Tone } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import type { CampaignRecipientCounts, CampaignStatus } from '@/shared/api/types'

import { useCampaign, useCancelCampaign } from './useCampaigns'

const STATUS_TONE: Record<CampaignStatus, Tone> = {
  draft: 'gray',
  scheduled: 'blue',
  sending: 'amber',
  completed: 'green',
  failed: 'red',
}

const STATUS_LABEL: Record<CampaignStatus, string> = {
  draft: 'Draft',
  scheduled: 'Scheduled',
  sending: 'Sending',
  completed: 'Completed',
  failed: 'Failed',
}

const RECIPIENT_COUNT_LABELS: { key: keyof CampaignRecipientCounts; label: string }[] = [
  { key: 'sent', label: 'Sent' },
  { key: 'pending', label: 'Pending' },
  { key: 'failed', label: 'Failed' },
  { key: 'skipped_opted_out', label: 'Opted out' },
  { key: 'skipped_no_number', label: 'No number' },
]

export function CampaignDetailPage() {
  const { campaignId } = useParams<{ campaignId: string }>()
  const { data: campaign, isLoading } = useCampaign(campaignId ?? '')
  const cancelCampaign = useCancelCampaign()

  if (isLoading) {
    return <p className="text-muted-foreground text-sm">Loading…</p>
  }

  if (!campaign) {
    return <p className="text-muted-foreground text-sm">Campaign not found.</p>
  }

  const cancellable = campaign.status === 'scheduled' || campaign.status === 'sending'

  return (
    <div className="space-y-6">
      <div>
        <Link
          to="/campaigns/templates"
          className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-sm transition-colors duration-150"
        >
          <ChevronLeft className="size-4" />
          Back to campaigns
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold">{campaign.name}</h1>
          <Badge tone={STATUS_TONE[campaign.status]}>{STATUS_LABEL[campaign.status]}</Badge>
        </div>
      </div>

      <Card>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
            {RECIPIENT_COUNT_LABELS.map(({ key, label }) => (
              <div key={key}>
                <p className="text-muted-foreground text-xs tracking-wide uppercase">{label}</p>
                <p className="text-xl font-semibold tabular-nums">
                  {campaign.recipient_counts[key]}
                </p>
              </div>
            ))}
          </div>

          {cancellable && (
            <Button
              type="button"
              variant="outline"
              className="hover:text-destructive"
              disabled={cancelCampaign.isPending}
              onClick={() => campaignId && cancelCampaign.mutate(campaignId)}
            >
              Cancel campaign
            </Button>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
